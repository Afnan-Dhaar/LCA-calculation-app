"""Database Layer for Brightway LCA Studio & PCF Platform.

Matches the enterprise schema created by senior in PostgreSQL (pcf_lca):
1. unit_conversion
2. lca_method
3. lca_flow
4. lca_activity
5. lca_run
(plus products for backward compatibility)

Supports auto-seeding from the senior's background datasets and resilient fallback
to SQLite if PostgreSQL is temporarily unreachable.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from dotenv import load_dotenv
import psycopg
from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    create_engine,
    desc,
    inspect,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.types import JSON

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

# Configurable database URL
DEFAULT_PG_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://postgres:afnandhaar%40786@127.0.0.1:5432/pcf_lca")
SQLITE_FALLBACK_URL = f"sqlite:///{BASE_DIR / 'lca_studio.db'}"


def ensure_postgres_database_exists(db_url: str) -> None:
    """Check if the target PostgreSQL database exists; if not, create it."""
    if not (db_url.startswith("postgresql://") or db_url.startswith("postgresql+psycopg://")):
        return

    try:
        clean_url = db_url.replace("postgresql+psycopg://", "postgresql://")
        parsed = urlparse(clean_url)
        target_db = parsed.path.lstrip("/") or "pcf_lca"
        user = parsed.username or "postgres"
        password = unquote(parsed.password or "")
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 5432

        conn = psycopg.connect(
            dbname="postgres",
            user=user,
            password=password,
            host=host,
            port=port,
        )
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s;", (target_db,))
            if not cur.fetchone():
                cur.execute(f'CREATE DATABASE "{target_db}";')
                print(f"Database '{target_db}' created in PostgreSQL.")
        conn.close()
    except Exception as err:
        print(f"Notice: Could not auto-verify database creation: {err}")


# Ensure pcf_lca database exists before connecting
target_url = DEFAULT_PG_URL if DEFAULT_PG_URL else SQLITE_FALLBACK_URL
if "postgresql" in target_url:
    ensure_postgres_database_exists(target_url)

try:
    if target_url.startswith("postgresql://") or target_url.startswith("postgresql+psycopg://"):
        engine = create_engine(target_url, pool_pre_ping=True)
        with engine.connect() as conn:
            pass
        active_db_type = "postgresql"
    else:
        engine = create_engine(target_url, connect_args={"check_same_thread": False})
        active_db_type = "sqlite"
except Exception as e:
    print(f"Warning: Could not connect to primary database ({e}). Falling back to SQLite.")
    engine = create_engine(SQLITE_FALLBACK_URL, connect_args={"check_same_thread": False})
    active_db_type = "sqlite"

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

JsonType = JSON().with_variant(JSONB, "postgresql")


# ---------------------------------------------------------------------------
# 5 Core Tables (Matching Senior's Schema)
# ---------------------------------------------------------------------------


class UnitConversionRecord(Base):
    __tablename__ = "unit_conversion"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    code = Column(String(50), unique=True, index=True, nullable=False)
    from_unit = Column(String(50), nullable=False)
    to_unit = Column(String(50), nullable=False)
    factor = Column(Float, nullable=False)
    dimension = Column(String(50), nullable=False)


class LcaMethodRecord(Base):
    __tablename__ = "lca_method"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    key = Column(String(100), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    method_tuple = Column(JsonType, nullable=False)
    unit = Column(String(50), nullable=False)
    cfs = Column(JsonType, nullable=False)  # {flow_code: factor}


class LcaFlowRecord(Base):
    __tablename__ = "lca_flow"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    code = Column(String(100), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    unit = Column(String(50), nullable=False, default="kilogram")
    categories = Column(String(100), default="air")
    flow_type = Column(String(50), default="emission")


class LcaActivityRecord(Base):
    __tablename__ = "lca_activity"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    code = Column(String(100), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    unit = Column(String(50), nullable=False)
    location = Column(String(50), default="GLO")
    emissions = Column(JsonType, default=dict)       # {flow_code: amount}
    technosphere = Column(JsonType, default=dict)    # {activity_code: amount}


class LcaRunRecord(Base):
    __tablename__ = "lca_run"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    run_id = Column(String(100), unique=True, index=True, nullable=False)
    product_name = Column(String(255), nullable=True)
    summary = Column(JsonType, nullable=False)       # {"gwp100": ..., "acidification": ...}
    metadata_info = Column("metadata", JsonType, default=dict) # {"plant": ..., "period": ...}
    request = Column(JsonType, nullable=False)       # Full request payload
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)


class ProductRecord(Base):
    __tablename__ = "products"

    product_id = Column(String(100), primary_key=True, index=True)
    product_name = Column(String(255), nullable=False)
    functional_unit_amount = Column(Float, nullable=False, default=1.0)
    functional_unit = Column(String(50), nullable=False, default="unit")
    payload = Column(JsonType, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Default Seed Data from Senior's Pre-file
# ---------------------------------------------------------------------------

INITIAL_FLOWS = {
    "co2": {"name": "Carbon dioxide, fossil", "unit": "kilogram", "categories": "air"},
    "ch4": {"name": "Methane, fossil", "unit": "kilogram", "categories": "air"},
    "n2o": {"name": "Dinitrogen monoxide", "unit": "kilogram", "categories": "air"},
    "so2": {"name": "Sulfur dioxide", "unit": "kilogram", "categories": "air"},
    "nox": {"name": "Nitrogen oxides", "unit": "kilogram", "categories": "air"},
    "nh3": {"name": "Ammonia", "unit": "kilogram", "categories": "air"},
}

INITIAL_METHODS = {
    "gwp100": {
        "name": "IPCC AR6 GWP100",
        "method_tuple": ["IPCC AR6", "GWP100"],
        "unit": "kg CO2-Eq",
        "cfs": {"co2": 1.0, "ch4": 29.8, "n2o": 273.0},
    },
    "acidification": {
        "name": "CML-style Acidification",
        "method_tuple": ["DEMO", "CML-style", "Acidification"],
        "unit": "kg SO2-Eq",
        "cfs": {"so2": 1.0, "nox": 0.5, "nh3": 1.88},
    },
}

INITIAL_SPECS = {
    "electricity_grid_sa": {
        "name": "Electricity, grid mix (SA)", "unit": "kilowatt hour", "location": "SA",
        "emissions": {"co2": 0.57, "ch4": 0.0008, "so2": 0.0011, "nox": 0.0009}, "technosphere": {},
    },
    "natural_gas_heat": {
        "name": "Heat, natural gas", "unit": "kilowatt hour", "location": "SA",
        "emissions": {"co2": 0.20, "ch4": 0.0005, "nox": 0.0002}, "technosphere": {},
    },
    "crude_oil": {
        "name": "Crude oil, at refinery gate", "unit": "kilogram", "location": "GLO",
        "emissions": {"co2": 0.45, "ch4": 0.004, "so2": 0.0006, "nox": 0.0005}, "technosphere": {},
    },
    "hydrogen_smr": {
        "name": "Hydrogen, steam reforming", "unit": "kilogram", "location": "GLO",
        "emissions": {"co2": 9.0, "ch4": 0.02}, "technosphere": {"electricity_grid_sa": 0.5},
    },
    "steel_low_alloy": {
        "name": "Steel, low-alloyed", "unit": "kilogram", "location": "GLO",
        "emissions": {"co2": 1.9, "ch4": 0.004}, "technosphere": {"electricity_grid_sa": 0.4},
    },
    "aluminium_primary": {
        "name": "Aluminium, primary", "unit": "kilogram", "location": "GLO",
        "emissions": {"co2": 6.5, "n2o": 0.0002}, "technosphere": {"electricity_grid_sa": 14.0},
    },
    "polypropylene": {
        "name": "Polypropylene granulate", "unit": "kilogram", "location": "GLO",
        "emissions": {"co2": 1.6, "ch4": 0.01}, "technosphere": {},
    },
    "truck_16t": {
        "name": "Transport, truck 16t", "unit": "ton kilometer", "location": "RoW",
        "emissions": {"co2": 0.11, "n2o": 0.000003, "nox": 0.0004}, "technosphere": {},
    },
    "rail_freight": {
        "name": "Transport, freight train", "unit": "ton kilometer", "location": "RoW",
        "emissions": {"co2": 0.03, "nox": 0.0001}, "technosphere": {},
    },
    "ship_freight": {
        "name": "Transport, sea freight", "unit": "ton kilometer", "location": "GLO",
        "emissions": {"co2": 0.012, "so2": 0.0001, "nox": 0.0002}, "technosphere": {},
    },
    "water_supply": {
        "name": "Water supply, desalinated", "unit": "cubic meter", "location": "SA",
        "emissions": {"co2": 0.05}, "technosphere": {"electricity_grid_sa": 3.5},
    },
    "wastewater_treatment": {
        "name": "Wastewater treatment", "unit": "cubic meter", "location": "SA",
        "emissions": {"co2": 0.35, "ch4": 0.02, "nh3": 0.001}, "technosphere": {"electricity_grid_sa": 0.4},
    },
    "hazardous_waste_incineration": {
        "name": "Hazardous waste incineration", "unit": "kilogram", "location": "SA",
        "emissions": {"co2": 1.1, "nox": 0.001, "so2": 0.0004}, "technosphere": {},
    },
}

INITIAL_UNITS = [
    {"code": "kg_to_kg", "from_unit": "kg", "to_unit": "kilogram", "factor": 1.0, "dimension": "mass"},
    {"code": "tonne_to_kg", "from_unit": "tonne", "to_unit": "kilogram", "factor": 1000.0, "dimension": "mass"},
    {"code": "t_to_kg", "from_unit": "t", "to_unit": "kilogram", "factor": 1000.0, "dimension": "mass"},
    {"code": "g_to_kg", "from_unit": "g", "to_unit": "kilogram", "factor": 0.001, "dimension": "mass"},
    {"code": "kwh_to_kwh", "from_unit": "kWh", "to_unit": "kilowatt hour", "factor": 1.0, "dimension": "energy"},
    {"code": "mj_to_kwh", "from_unit": "MJ", "to_unit": "kilowatt hour", "factor": 0.277778, "dimension": "energy"},
    {"code": "m3_to_m3", "from_unit": "m3", "to_unit": "cubic meter", "factor": 1.0, "dimension": "volume"},
    {"code": "liter_to_m3", "from_unit": "L", "to_unit": "cubic meter", "factor": 0.001, "dimension": "volume"},
    {"code": "km_to_km", "from_unit": "km", "to_unit": "kilometer", "factor": 1.0, "dimension": "distance"},
    {"code": "tkm_to_tkm", "from_unit": "tkm", "to_unit": "ton kilometer", "factor": 1.0, "dimension": "transport"},
]


# ---------------------------------------------------------------------------
# Initialization & Data Migration
# ---------------------------------------------------------------------------


def init_db(database_url: str | None = None) -> str:
    """Initialize all 5 tables and seed with initial data if empty."""
    global engine, SessionLocal, active_db_type

    if database_url:
        try:
            if database_url.startswith("postgresql://") and "psycopg" not in database_url:
                database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
            ensure_postgres_database_exists(database_url)
            new_engine = create_engine(database_url, pool_pre_ping=True)
            with new_engine.connect() as conn:
                pass
            engine = new_engine
            SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
            active_db_type = "postgresql" if "postgresql" in database_url else "sqlite"
        except Exception as e:
            print(f"Failed to bind to provided database URL: {e}")

    Base.metadata.create_all(bind=engine)

    # Seed default data if empty
    db = SessionLocal()
    try:
        # 1. Flows
        if db.query(LcaFlowRecord).count() == 0:
            for code, info in INITIAL_FLOWS.items():
                db.add(LcaFlowRecord(
                    code=code,
                    name=info["name"],
                    unit=info["unit"],
                    categories=info["categories"],
                    flow_type="emission",
                ))
            db.commit()

        # 2. Methods
        if db.query(LcaMethodRecord).count() == 0:
            for key, info in INITIAL_METHODS.items():
                db.add(LcaMethodRecord(
                    key=key,
                    name=info["name"],
                    method_tuple=info["method_tuple"],
                    unit=info["unit"],
                    cfs=info["cfs"],
                ))
            db.commit()

        # 3. Activities
        if db.query(LcaActivityRecord).count() == 0:
            for code, info in INITIAL_SPECS.items():
                db.add(LcaActivityRecord(
                    code=code,
                    name=info["name"],
                    unit=info["unit"],
                    location=info["location"],
                    emissions=info["emissions"],
                    technosphere=info["technosphere"],
                ))
            db.commit()

        # 4. Units
        if db.query(UnitConversionRecord).count() == 0:
            for u in INITIAL_UNITS:
                db.add(UnitConversionRecord(
                    code=u["code"],
                    from_unit=u["from_unit"],
                    to_unit=u["to_unit"],
                    factor=u["factor"],
                    dimension=u["dimension"],
                ))
            db.commit()

    except Exception as err:
        db.rollback()
        print(f"Seeding error in init_db: {err}")
    finally:
        db.close()

    return active_db_type


# ---------------------------------------------------------------------------
# Flow CRUD Operations
# ---------------------------------------------------------------------------


def get_all_flows_db() -> list[dict[str, Any]]:
    db = SessionLocal()
    try:
        rows = db.query(LcaFlowRecord).order_by(LcaFlowRecord.code).all()
        return [
            {
                "id": r.id,
                "code": r.code,
                "name": r.name,
                "unit": r.unit,
                "categories": r.categories,
                "flow_type": r.flow_type,
            }
            for r in rows
        ]
    finally:
        db.close()


def upsert_flow_db(data: dict[str, Any]) -> dict[str, Any]:
    db = SessionLocal()
    try:
        code = str(data.get("code", "")).strip().lower()
        rec = db.query(LcaFlowRecord).filter(LcaFlowRecord.code == code).first()
        if rec:
            rec.name = data.get("name", rec.name)
            rec.unit = data.get("unit", rec.unit)
            rec.categories = data.get("categories", rec.categories)
            rec.flow_type = data.get("flow_type", rec.flow_type)
        else:
            rec = LcaFlowRecord(
                code=code,
                name=data.get("name", code),
                unit=data.get("unit", "kilogram"),
                categories=data.get("categories", "air"),
                flow_type=data.get("flow_type", "emission"),
            )
            db.add(rec)
        db.commit()
        db.refresh(rec)
        return {"status": "success", "id": rec.id, "code": rec.code, "name": rec.name}
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Method CRUD Operations
# ---------------------------------------------------------------------------


def get_all_methods_db() -> list[dict[str, Any]]:
    db = SessionLocal()
    try:
        rows = db.query(LcaMethodRecord).order_by(LcaMethodRecord.key).all()
        return [
            {
                "id": r.id,
                "key": r.key,
                "name": r.name,
                "method_tuple": r.method_tuple,
                "unit": r.unit,
                "cfs": r.cfs,
            }
            for r in rows
        ]
    finally:
        db.close()


def upsert_method_db(data: dict[str, Any]) -> dict[str, Any]:
    db = SessionLocal()
    try:
        key = str(data.get("key", "")).strip().lower()
        rec = db.query(LcaMethodRecord).filter(LcaMethodRecord.key == key).first()
        if rec:
            rec.name = data.get("name", rec.name)
            rec.method_tuple = data.get("method_tuple", rec.method_tuple)
            rec.unit = data.get("unit", rec.unit)
            rec.cfs = data.get("cfs", rec.cfs)
        else:
            rec = LcaMethodRecord(
                key=key,
                name=data.get("name", key),
                method_tuple=data.get("method_tuple", [key]),
                unit=data.get("unit", "kg CO2-Eq"),
                cfs=data.get("cfs", {}),
            )
            db.add(rec)
        db.commit()
        db.refresh(rec)
        return {"status": "success", "id": rec.id, "key": rec.key, "name": rec.name}
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Activity CRUD Operations
# ---------------------------------------------------------------------------


def get_all_activities_db() -> list[dict[str, Any]]:
    db = SessionLocal()
    try:
        rows = db.query(LcaActivityRecord).order_by(LcaActivityRecord.code).all()
        return [
            {
                "id": r.id,
                "code": r.code,
                "name": r.name,
                "unit": r.unit,
                "location": r.location,
                "emissions": r.emissions or {},
                "technosphere": r.technosphere or {},
            }
            for r in rows
        ]
    finally:
        db.close()


def upsert_activity_db(data: dict[str, Any]) -> dict[str, Any]:
    db = SessionLocal()
    try:
        code = str(data.get("code", "")).strip().lower()
        rec = db.query(LcaActivityRecord).filter(LcaActivityRecord.code == code).first()
        if rec:
            rec.name = data.get("name", rec.name)
            rec.unit = data.get("unit", rec.unit)
            rec.location = data.get("location", rec.location)
            rec.emissions = data.get("emissions", rec.emissions)
            rec.technosphere = data.get("technosphere", rec.technosphere)
        else:
            rec = LcaActivityRecord(
                code=code,
                name=data.get("name", code),
                unit=data.get("unit", "kilogram"),
                location=data.get("location", "GLO"),
                emissions=data.get("emissions", {}),
                technosphere=data.get("technosphere", {}),
            )
            db.add(rec)
        db.commit()
        db.refresh(rec)
        return {"status": "success", "id": rec.id, "code": rec.code, "name": rec.name}
    finally:
        db.close()


def delete_activity_db(code: str) -> bool:
    db = SessionLocal()
    try:
        rec = db.query(LcaActivityRecord).filter(LcaActivityRecord.code == code).first()
        if not rec:
            return False
        db.delete(rec)
        db.commit()
        return True
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Unit Conversion CRUD Operations
# ---------------------------------------------------------------------------


def get_all_units_db() -> list[dict[str, Any]]:
    db = SessionLocal()
    try:
        rows = db.query(UnitConversionRecord).order_by(UnitConversionRecord.id).all()
        return [
            {
                "id": r.id,
                "code": r.code,
                "from_unit": r.from_unit,
                "to_unit": r.to_unit,
                "factor": r.factor,
                "dimension": r.dimension,
            }
            for r in rows
        ]
    finally:
        db.close()


def upsert_unit_db(data: dict[str, Any]) -> dict[str, Any]:
    db = SessionLocal()
    try:
        code = str(data.get("code", "")).strip().lower()
        rec = db.query(UnitConversionRecord).filter(UnitConversionRecord.code == code).first()
        if rec:
            rec.from_unit = data.get("from_unit", rec.from_unit)
            rec.to_unit = data.get("to_unit", rec.to_unit)
            rec.factor = float(data.get("factor", rec.factor))
            rec.dimension = data.get("dimension", rec.dimension)
        else:
            rec = UnitConversionRecord(
                code=code,
                from_unit=data.get("from_unit", code),
                to_unit=data.get("to_unit", code),
                factor=float(data.get("factor", 1.0)),
                dimension=data.get("dimension", "general"),
            )
            db.add(rec)
        db.commit()
        db.refresh(rec)
        return {"status": "success", "id": rec.id, "code": rec.code}
    finally:
        db.close()


def delete_unit_db(code: str) -> bool:
    db = SessionLocal()
    try:
        rec = db.query(UnitConversionRecord).filter(UnitConversionRecord.code == code).first()
        if not rec:
            return False
        db.delete(rec)
        db.commit()
        return True
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Run Audit Trail Operations (Matching lca_run in pgAdmin)
# ---------------------------------------------------------------------------


def record_run_db(
    summary: dict[str, Any],
    metadata_info: dict[str, Any],
    request_data: dict[str, Any],
    product_name: str | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Insert a calculation run into lca_run table matching pgAdmin columns."""
    db = SessionLocal()
    try:
        if not run_id:
            run_id = f"run_{uuid.uuid4().hex[:12]}"
        if not product_name:
            product_name = metadata_info.get("product_name") or request_data.get("product", {}).get("name") or "Product"

        rec = LcaRunRecord(
            run_id=run_id,
            product_name=product_name,
            summary=summary,
            metadata_info=metadata_info,
            request=request_data,
        )
        db.add(rec)
        db.commit()
        db.refresh(rec)
        return {
            "id": rec.id,
            "run_id": rec.run_id,
            "product_name": rec.product_name,
            "summary": rec.summary,
            "metadata": rec.metadata_info,
            "created_at": rec.created_at.isoformat(),
        }
    finally:
        db.close()


def get_runs_db(limit: int = 50) -> list[dict[str, Any]]:
    """Retrieve runs from lca_run table."""
    db = SessionLocal()
    try:
        recs = db.query(LcaRunRecord).order_by(desc(LcaRunRecord.id)).limit(limit).all()
        return [
            {
                "id": r.id,
                "run_id": r.run_id,
                "product_name": r.product_name,
                "summary": r.summary,
                "metadata": r.metadata_info,
                "request": r.request,
                "created_at": r.created_at.isoformat(),
            }
            for r in recs
        ]
    finally:
        db.close()


def get_run_by_id_db(run_id: str) -> dict[str, Any] | None:
    """Retrieve a specific run by run_id or integer id."""
    db = SessionLocal()
    try:
        if run_id.isdigit():
            rec = db.query(LcaRunRecord).filter(LcaRunRecord.id == int(run_id)).first()
        else:
            rec = db.query(LcaRunRecord).filter(LcaRunRecord.run_id == run_id).first()
        if not rec:
            return None
        return {
            "id": rec.id,
            "run_id": rec.run_id,
            "product_name": rec.product_name,
            "summary": rec.summary,
            "metadata": rec.metadata_info,
            "request": rec.request,
            "created_at": rec.created_at.isoformat(),
        }
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Compatibility Helpers
# ---------------------------------------------------------------------------


def get_db_status() -> dict[str, Any]:
    """Diagnostics on current database connection and tables."""
    db = SessionLocal()
    try:
        return {
            "active_database": active_db_type,
            "is_postgresql": active_db_type == "postgresql",
            "total_activities": db.query(LcaActivityRecord).count(),
            "total_flows": db.query(LcaFlowRecord).count(),
            "total_methods": db.query(LcaMethodRecord).count(),
            "total_units": db.query(UnitConversionRecord).count(),
            "total_runs": db.query(LcaRunRecord).count(),
        }
    except Exception as e:
        return {"error": str(e), "active_database": active_db_type}
    finally:
        db.close()


def list_lca_runs_db(product_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    """Backward-compatible run list retrieval for frontend."""
    db = SessionLocal()
    try:
        query = db.query(LcaRunRecord)
        if product_id:
            query = query.filter(LcaRunRecord.product_name == product_id)
        recs = query.order_by(desc(LcaRunRecord.id)).limit(limit).all()
        return [
            {
                "id": r.id,
                "run_id": r.run_id,
                "product_id": r.run_id,
                "product_name": r.product_name or "Product",
                "method_name": "IPCC AR6 GWP100",
                "method_unit": "kg CO2-Eq",
                "total_score": r.summary.get("gwp100", 0.0) if isinstance(r.summary, dict) else 0.0,
                "summary": r.summary,
                "metadata": r.metadata_info,
                "calculated_at": r.created_at.isoformat(),
            }
            for r in recs
        ]
    finally:
        db.close()


def record_lca_run_db(product: Any, result: Any) -> None:
    """Backward-compatible run recording from legacy product calculation."""
    db = SessionLocal()
    try:
        summary = {"gwp100": getattr(result, "total_score", 0.0)}
        meta = {
            "product_id": getattr(product, "product_id", "prod"),
            "product_name": getattr(product, "product_name", "Product"),
        }
        rec = LcaRunRecord(
            run_id=f"run_{uuid.uuid4().hex[:12]}",
            product_name=getattr(product, "product_name", "Product"),
            summary=summary,
            metadata_info=meta,
            request={"product_id": getattr(product, "product_id", "")},
        )
        db.add(rec)
        db.commit()
    finally:
        db.close()


def list_products_db() -> list[dict[str, Any]]:
    db = SessionLocal()
    try:
        recs = db.query(ProductRecord).order_by(ProductRecord.product_name).all()
        return [r.payload for r in recs]
    finally:
        db.close()


def save_product_db(product: Any) -> Any:
    from product_model import product_to_dict
    db = SessionLocal()
    try:
        pid = product.product_id
        rec = db.query(ProductRecord).filter(ProductRecord.product_id == pid).first()
        payload = product_to_dict(product)
        if rec:
            rec.product_name = product.product_name
            rec.functional_unit_amount = product.functional_unit_amount
            rec.functional_unit = product.functional_unit
            rec.payload = payload
            rec.updated_at = datetime.now(timezone.utc)
        else:
            rec = ProductRecord(
                product_id=pid,
                product_name=product.product_name,
                functional_unit_amount=product.functional_unit_amount,
                functional_unit=product.functional_unit,
                payload=payload,
            )
            db.add(rec)
        db.commit()
        db.refresh(rec)
        return rec
    finally:
        db.close()


def get_product_db(product_id: str) -> Any:
    from product_model import dict_to_product
    db = SessionLocal()
    try:
        rec = db.query(ProductRecord).filter(ProductRecord.product_id == product_id).first()
        if not rec:
            return None
        return dict_to_product(rec.payload)
    finally:
        db.close()


def delete_product_db(product_id: str) -> bool:
    db = SessionLocal()
    try:
        rec = db.query(ProductRecord).filter(ProductRecord.product_id == product_id).first()
        if not rec:
            return False
        db.delete(rec)
        db.commit()
        return True
    finally:
        db.close()

