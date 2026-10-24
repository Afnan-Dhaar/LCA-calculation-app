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
    "po4": {"name": "Phosphate", "unit": "kilogram", "categories": "water"},
    "p": {"name": "Phosphorus", "unit": "kilogram", "categories": "water"},
    "nmvoc": {"name": "Non-methane volatile organic compounds", "unit": "kilogram", "categories": "air"},
    "cfc11": {"name": "CFC-11 (Trichlorofluoromethane)", "unit": "kilogram", "categories": "air"},
    "co": {"name": "Carbon monoxide", "unit": "kilogram", "categories": "air"},
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
    "eutrophication": {
        "name": "CML-style Eutrophication",
        "method_tuple": ["DEMO", "CML-style", "Eutrophication"],
        "unit": "kg PO4-Eq",
        "cfs": {"nox": 0.13, "nh3": 0.35, "po4": 1.0, "p": 3.06},
    },
    "photochemical_ozone": {
        "name": "CML-style Photochemical Ozone Creation",
        "method_tuple": ["DEMO", "CML-style", "Photochemical Ozone Creation"],
        "unit": "kg NMVOC-Eq",
        "cfs": {"nmvoc": 1.0, "ch4": 0.007, "so2": 0.05, "co": 0.04},
    },
    "ozone_depletion": {
        "name": "CML-style Ozone Depletion",
        "method_tuple": ["DEMO", "CML-style", "Ozone Depletion"],
        "unit": "kg CFC-11-Eq",
        "cfs": {"cfc11": 1.0, "n2o": 0.017},
    },
    "abiotic_depletion_fossil": {
        "name": "CML-style Abiotic Depletion (Fossil)",
        "method_tuple": ["DEMO", "CML-style", "Abiotic Depletion Fossil"],
        "unit": "MJ",
        "cfs": {"crude_oil": 42.5, "ch4": 50.0},
    },
}

INITIAL_SPECS = {
    "electricity_grid_sa": {
        "name": "Electricity, grid mix (SA)", "unit": "kilowatt hour", "location": "SA",
        "emissions": {"co2": 0.57, "ch4": 0.0008, "so2": 0.0011, "nox": 0.0009, "co": 0.0001}, "technosphere": {},
    },
    "natural_gas_heat": {
        "name": "Heat, natural gas", "unit": "kilowatt hour", "location": "SA",
        "emissions": {"co2": 0.20, "ch4": 0.0005, "nox": 0.0002, "co": 0.00005}, "technosphere": {},
    },
    "crude_oil": {
        "name": "Crude oil, at refinery gate", "unit": "kilogram", "location": "GLO",
        "emissions": {"co2": 0.45, "ch4": 0.004, "so2": 0.0006, "nox": 0.0005, "nmvoc": 0.0008, "co": 0.0002}, "technosphere": {},
    },
    "hydrogen_smr": {
        "name": "Hydrogen, steam reforming", "unit": "kilogram", "location": "GLO",
        "emissions": {"co2": 9.0, "ch4": 0.02, "co": 0.001}, "technosphere": {"electricity_grid_sa": 0.5},
    },
    "steel_low_alloy": {
        "name": "Steel, low-alloyed", "unit": "kilogram", "location": "GLO",
        "emissions": {"co2": 1.9, "ch4": 0.004, "so2": 0.001}, "technosphere": {"electricity_grid_sa": 0.4},
    },
    "aluminium_primary": {
        "name": "Aluminium, primary", "unit": "kilogram", "location": "GLO",
        "emissions": {"co2": 6.5, "n2o": 0.0002, "so2": 0.003}, "technosphere": {"electricity_grid_sa": 14.0},
    },
    "polypropylene": {
        "name": "Polypropylene granulate", "unit": "kilogram", "location": "GLO",
        "emissions": {"co2": 1.6, "ch4": 0.01, "nmvoc": 0.002}, "technosphere": {},
    },
    "truck_16t": {
        "name": "Transport, truck 16t", "unit": "ton kilometer", "location": "RoW",
        "emissions": {"co2": 0.11, "n2o": 0.000003, "nox": 0.0004, "nmvoc": 0.00005, "co": 0.0001}, "technosphere": {},
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
        "emissions": {"co2": 0.35, "ch4": 0.02, "nh3": 0.001, "po4": 0.0004, "p": 0.0001}, "technosphere": {"electricity_grid_sa": 0.4},
    },
    "hazardous_waste_incineration": {
        "name": "Hazardous waste incineration", "unit": "kilogram", "location": "SA",
        "emissions": {"co2": 1.1, "nox": 0.001, "so2": 0.0004}, "technosphere": {},
    },
}

INITIAL_UNITS = [
    # Mass
    {"code": "kg_to_kg", "from_unit": "kg", "to_unit": "kilogram", "factor": 1.0, "dimension": "mass"},
    {"code": "tonne_to_kg", "from_unit": "tonne", "to_unit": "kilogram", "factor": 1000.0, "dimension": "mass"},
    {"code": "t_to_kg", "from_unit": "t", "to_unit": "kilogram", "factor": 1000.0, "dimension": "mass"},
    {"code": "g_to_kg", "from_unit": "g", "to_unit": "kilogram", "factor": 0.001, "dimension": "mass"},
    {"code": "mg_to_kg", "from_unit": "mg", "to_unit": "kilogram", "factor": 0.000001, "dimension": "mass"},
    {"code": "lb_to_kg", "from_unit": "lb", "to_unit": "kilogram", "factor": 0.45359237, "dimension": "mass"},
    {"code": "oz_to_kg", "from_unit": "oz", "to_unit": "kilogram", "factor": 0.0283495, "dimension": "mass"},
    # Energy
    {"code": "kwh_to_kwh", "from_unit": "kWh", "to_unit": "kilowatt hour", "factor": 1.0, "dimension": "energy"},
    {"code": "wh_to_kwh", "from_unit": "Wh", "to_unit": "kilowatt hour", "factor": 0.001, "dimension": "energy"},
    {"code": "mwh_to_kwh", "from_unit": "MWh", "to_unit": "kilowatt hour", "factor": 1000.0, "dimension": "energy"},
    {"code": "mj_to_kwh", "from_unit": "MJ", "to_unit": "kilowatt hour", "factor": 0.277778, "dimension": "energy"},
    {"code": "gj_to_kwh", "from_unit": "GJ", "to_unit": "kilowatt hour", "factor": 277.778, "dimension": "energy"},
    {"code": "btu_to_kwh", "from_unit": "BTU", "to_unit": "kilowatt hour", "factor": 0.000293071, "dimension": "energy"},
    {"code": "kcal_to_kwh", "from_unit": "kcal", "to_unit": "kilowatt hour", "factor": 0.00116222, "dimension": "energy"},
    # Volume
    {"code": "m3_to_m3", "from_unit": "m3", "to_unit": "cubic meter", "factor": 1.0, "dimension": "volume"},
    {"code": "liter_to_m3", "from_unit": "L", "to_unit": "cubic meter", "factor": 0.001, "dimension": "volume"},
    {"code": "ml_to_m3", "from_unit": "ml", "to_unit": "cubic meter", "factor": 0.000001, "dimension": "volume"},
    {"code": "gal_to_m3", "from_unit": "gal", "to_unit": "cubic meter", "factor": 0.00378541, "dimension": "volume"},
    {"code": "bbl_to_m3", "from_unit": "bbl", "to_unit": "cubic meter", "factor": 0.1589873, "dimension": "volume"},
    # Distance
    {"code": "km_to_km", "from_unit": "km", "to_unit": "kilometer", "factor": 1.0, "dimension": "distance"},
    {"code": "m_to_km", "from_unit": "m", "to_unit": "kilometer", "factor": 0.001, "dimension": "distance"},
    {"code": "mile_to_km", "from_unit": "mile", "to_unit": "kilometer", "factor": 1.60934, "dimension": "distance"},
    {"code": "mi_to_km", "from_unit": "mi", "to_unit": "kilometer", "factor": 1.60934, "dimension": "distance"},
    # Transport
    {"code": "tkm_to_tkm", "from_unit": "tkm", "to_unit": "ton kilometer", "factor": 1.0, "dimension": "transport"},
    {"code": "kgkm_to_tkm", "from_unit": "kgkm", "to_unit": "ton kilometer", "factor": 0.001, "dimension": "transport"},
]


# ---------------------------------------------------------------------------
# Initialization & Data Migration
# ---------------------------------------------------------------------------


def init_db(database_url: str | None = None) -> str:
    """Initialize all 5 tables and seed with initial data idempotently."""
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

    # Seed default data (insert missing items idempotently)
    db = SessionLocal()
    try:
        # 1. Flows (insert any missing)
        existing_flow_codes = {r.code for r in db.query(LcaFlowRecord.code).all()}
        for code, info in INITIAL_FLOWS.items():
            if code not in existing_flow_codes:
                db.add(LcaFlowRecord(
                    code=code,
                    name=info["name"],
                    unit=info["unit"],
                    categories=info["categories"],
                    flow_type="emission",
                ))

        # 2. Methods (insert any missing)
        existing_method_keys = {r.key for r in db.query(LcaMethodRecord.key).all()}
        for key, info in INITIAL_METHODS.items():
            if key not in existing_method_keys:
                db.add(LcaMethodRecord(
                    key=key,
                    name=info["name"],
                    method_tuple=info["method_tuple"],
                    unit=info["unit"],
                    cfs=info["cfs"],
                ))

        # 3. Activities (insert any missing)
        existing_activity_codes = {r.code for r in db.query(LcaActivityRecord.code).all()}
        for code, info in INITIAL_SPECS.items():
            if code not in existing_activity_codes:
                db.add(LcaActivityRecord(
                    code=code,
                    name=info["name"],
                    unit=info["unit"],
                    location=info["location"],
                    emissions=info["emissions"],
                    technosphere=info["technosphere"],
                ))

        # 4. Units (insert any missing)
        existing_unit_codes = {r.code for r in db.query(UnitConversionRecord.code).all()}
        for u in INITIAL_UNITS:
            if u["code"] not in existing_unit_codes:
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


def delete_flow_db(code: str, cascade: bool = False) -> bool:
    """Delete an elementary flow from lca_flow table with referential integrity check."""
    db = SessionLocal()
    try:
        code = str(code).strip().lower()
        rec = db.query(LcaFlowRecord).filter(LcaFlowRecord.code == code).first()
        if not rec:
            return False

        if not cascade:
            all_acts = db.query(LcaActivityRecord).all()
            referencing_acts = [a.code for a in all_acts if code in (a.emissions or {})]

            all_methods = db.query(LcaMethodRecord).all()
            referencing_methods = [m.key for m in all_methods if code in (m.cfs or {})]

            if referencing_acts or referencing_methods:
                err_parts = []
                if referencing_acts:
                    err_parts.append(f"activities: {', '.join(referencing_acts)}")
                if referencing_methods:
                    err_parts.append(f"methods: {', '.join(referencing_methods)}")
                raise ValueError(
                    f"Cannot delete flow '{code}': referenced by {'; '.join(err_parts)}. "
                    "Remove dependencies first or specify cascade=True."
                )

        db.delete(rec)
        db.commit()
        return True
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


def delete_method_db(key: str) -> bool:
    """Delete an LCIA method from lca_method table."""
    db = SessionLocal()
    try:
        key = str(key).strip().lower()
        rec = db.query(LcaMethodRecord).filter(LcaMethodRecord.key == key).first()
        if not rec:
            return False
        db.delete(rec)
        db.commit()
        return True
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
    """Create or update background activity with relational integrity checks."""
    db = SessionLocal()
    try:
        code = str(data.get("code", "")).strip().lower()
        if not code:
            raise ValueError("Activity code cannot be empty.")

        technosphere = data.get("technosphere") or {}
        emissions = data.get("emissions") or {}

        # 1. Self-reference check
        if code in technosphere:
            raise ValueError(f"Activity '{code}' cannot reference itself as an upstream input.")

        # 2. Referential integrity: Check that upstream technosphere activities exist
        existing_acts = {r.code for r in db.query(LcaActivityRecord.code).all()}
        missing_acts = [dep for dep in technosphere.keys() if dep != code and dep not in existing_acts]
        if missing_acts:
            raise ValueError(f"Technosphere inputs reference non-existent background activities: {', '.join(missing_acts)}")

        # 3. Referential integrity: Check that emission flows exist in lca_flow
        existing_flows = {r.code for r in db.query(LcaFlowRecord.code).all()}
        missing_flows = [fl for fl in emissions.keys() if fl not in existing_flows]
        if missing_flows:
            raise ValueError(f"Direct emissions reference non-existent elementary flows in lca_flow: {', '.join(missing_flows)}")

        rec = db.query(LcaActivityRecord).filter(LcaActivityRecord.code == code).first()
        if rec:
            rec.name = data.get("name", rec.name)
            rec.unit = data.get("unit", rec.unit)
            rec.location = data.get("location", rec.location)
            rec.emissions = emissions
            rec.technosphere = technosphere
        else:
            rec = LcaActivityRecord(
                code=code,
                name=data.get("name", code),
                unit=data.get("unit", "kilogram"),
                location=data.get("location", "GLO"),
                emissions=emissions,
                technosphere=technosphere,
            )
            db.add(rec)
        db.commit()
        db.refresh(rec)
        return {"status": "success", "id": rec.id, "code": rec.code, "name": rec.name}
    finally:
        db.close()


def delete_activity_db(code: str, cascade: bool = False) -> bool:
    """Delete a background activity with downstream dependency check."""
    db = SessionLocal()
    try:
        code = str(code).strip().lower()
        rec = db.query(LcaActivityRecord).filter(LcaActivityRecord.code == code).first()
        if not rec:
            return False

        if not cascade:
            all_acts = db.query(LcaActivityRecord).all()
            dependent_acts = [a.code for a in all_acts if a.code != code and code in (a.technosphere or {})]
            if dependent_acts:
                raise ValueError(
                    f"Cannot delete activity '{code}': required by downstream activities ({', '.join(dependent_acts)}). "
                    "Remove dependency references or specify cascade=True."
                )

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


def normalize_unit_str(u: str) -> str:
    """Normalize unit string to canonical short code."""
    if not u:
        return ""
    clean = str(u).strip().lower().replace("_", " ").replace("-", " ")
    clean = " ".join(clean.split())
    ALIASES = {
        "kilogram": "kg", "kilograms": "kg", "kgs": "kg",
        "gram": "g", "grams": "g",
        "milligram": "mg", "milligrams": "mg",
        "metric ton": "t", "metric tonne": "t", "ton": "t", "tonne": "t", "tonnes": "t", "tons": "t",
        "pound": "lb", "pounds": "lb", "lbs": "lb",
        "ounce": "oz", "ounces": "oz",
        "kilowatt hour": "kwh", "kilowatt-hour": "kwh", "kilowatthour": "kwh",
        "watt hour": "wh", "watthour": "wh",
        "megawatt hour": "mwh", "megawatthour": "mwh",
        "megajoule": "mj", "megajoules": "mj",
        "gigajoule": "gj", "gigajoules": "gj",
        "joule": "j", "joules": "j",
        "cubic meter": "m3", "cubic metre": "m3", "m^3": "m3",
        "liter": "l", "liters": "l", "litre": "l", "litres": "l",
        "milliliter": "ml", "milliliters": "ml",
        "gallon": "gal", "gallons": "gal",
        "barrel": "bbl", "barrels": "bbl",
        "kilometer": "km", "kilometers": "km", "kilometre": "km",
        "meter": "m", "meters": "m", "metre": "m",
        "mile": "mi", "miles": "mi",
        "ton kilometer": "tkm", "ton-kilometer": "tkm", "ton-km": "tkm", "tonne-km": "tkm", "tonne kilometer": "tkm",
    }
    return ALIASES.get(clean, clean)


# SI Standard Fallback table (relative to canonical SI base unit per dimension)
SI_BASE_FACTORS: dict[str, tuple[str, float]] = {
    # dimension: mass -> base 'kg'
    "kg": ("mass", 1.0),
    "g": ("mass", 0.001),
    "mg": ("mass", 0.000001),
    "t": ("mass", 1000.0),
    "tonne": ("mass", 1000.0),
    "lb": ("mass", 0.45359237),
    "oz": ("mass", 0.0283495),

    # dimension: energy -> base 'kwh'
    "kwh": ("energy", 1.0),
    "wh": ("energy", 0.001),
    "mwh": ("energy", 1000.0),
    "mj": ("energy", 0.2777777778),
    "gj": ("energy", 277.7777778),
    "j": ("energy", 2.777777778e-7),
    "btu": ("energy", 0.000293071),
    "kcal": ("energy", 0.00116222),

    # dimension: volume -> base 'm3'
    "m3": ("volume", 1.0),
    "l": ("volume", 0.001),
    "ml": ("volume", 0.000001),
    "gal": ("volume", 0.00378541),
    "bbl": ("volume", 0.1589873),

    # dimension: distance -> base 'km'
    "km": ("distance", 1.0),
    "m": ("distance", 0.001),
    "mi": ("distance", 1.60934),

    # dimension: transport -> base 'tkm'
    "tkm": ("transport", 1.0),
    "kgkm": ("transport", 0.001),
}


def resolve_conversion_graph(from_unit: str, to_unit: str) -> float | None:
    """Solve multi-hop unit conversion path across PostgreSQL unit_conversion table
    using Breadth-First Search (BFS) graph traversal.
    """
    from collections import deque
    f_norm = normalize_unit_str(from_unit)
    t_norm = normalize_unit_str(to_unit)
    if not f_norm or not t_norm:
        return None
    if f_norm == t_norm:
        return 1.0

    db = SessionLocal()
    try:
        rows = db.query(UnitConversionRecord).all()
        if not rows:
            return None

        adj: dict[str, list[tuple[str, float]]] = {}
        for r in rows:
            u = normalize_unit_str(r.from_unit)
            v = normalize_unit_str(r.to_unit)
            try:
                f = float(r.factor)
            except (ValueError, TypeError):
                continue
            if f <= 0:
                continue
            adj.setdefault(u, []).append((v, f))
            adj.setdefault(v, []).append((u, 1.0 / f))

        if f_norm not in adj or t_norm not in adj:
            return None

        queue = deque([(f_norm, 1.0)])
        visited = {f_norm}
        while queue:
            curr_unit, curr_factor = queue.popleft()
            if curr_unit == t_norm:
                return curr_factor
            for neighbor, edge_factor in adj.get(curr_unit, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, curr_factor * edge_factor))
        return None
    finally:
        db.close()


def convert_unit_db(amount: float, from_unit: str, to_unit: str) -> float:
    """Convert an amount from from_unit to to_unit using:
    1. Multi-hop graph search across PostgreSQL unit_conversion table
    2. SI physical dimension fallback dictionary
    """
    if amount == 0.0:
        return 0.0

    f_norm = normalize_unit_str(from_unit)
    t_norm = normalize_unit_str(to_unit)

    if not f_norm or not t_norm or f_norm == t_norm:
        return float(amount)

    # 1. Multi-hop graph traversal on PostgreSQL unit_conversion table
    try:
        graph_factor = resolve_conversion_graph(f_norm, t_norm)
        if graph_factor is not None:
            return float(amount) * graph_factor
    except Exception:
        pass

    # 2. SI standard dictionary fallback
    if f_norm in SI_BASE_FACTORS and t_norm in SI_BASE_FACTORS:
        f_dim, f_factor = SI_BASE_FACTORS[f_norm]
        t_dim, t_factor = SI_BASE_FACTORS[t_norm]
        if f_dim != t_dim:
            raise ValueError(f"Unit dimension mismatch: cannot convert '{from_unit}' ({f_dim}) to '{to_unit}' ({t_dim})")
        return float(amount) * (f_factor / t_factor)

    # If completely unknown, return original amount with warning
    print(f"Notice: No unit conversion factor found for '{from_unit}' -> '{to_unit}'. Using 1:1.")
    return float(amount)


def get_background_matrix_hash() -> str:
    """Calculate a deterministic SHA-256 fingerprint representing the background
    technosphere, biosphere, impact methods, and unit conversions.
    """
    import hashlib
    db = SessionLocal()
    try:
        flows = sorted([(r.code, r.unit) for r in db.query(LcaFlowRecord.code, LcaFlowRecord.unit).all()])
        methods = sorted([
            (m.key, m.unit, tuple(sorted((m.cfs or {}).items())))
            for m in db.query(LcaMethodRecord).all()
        ])
        acts = sorted([
            (
                a.code,
                a.unit,
                a.location,
                tuple(sorted((a.technosphere or {}).items())),
                tuple(sorted((a.emissions or {}).items()))
            )
            for a in db.query(LcaActivityRecord).all()
        ])
        units = sorted([(u.code, float(u.factor)) for u in db.query(UnitConversionRecord.code, UnitConversionRecord.factor).all()])

        raw_repr = json.dumps({
            "flows": flows,
            "methods": methods,
            "activities": acts,
            "units": units,
        }, sort_keys=True)
        digest = hashlib.sha256(raw_repr.encode("utf-8")).hexdigest()
        return f"sha256:{digest[:16]}"
    except Exception:
        return "sha256:unknown"
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

        if "matrix_hash" not in metadata_info:
            metadata_info["matrix_hash"] = get_background_matrix_hash()

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
    """Diagnostics on current database connection, background matrix hash, and table counts."""
    db = SessionLocal()
    try:
        matrix_hash = get_background_matrix_hash()
        return {
            "active_database": active_db_type,
            "is_postgresql": active_db_type == "postgresql",
            "matrix_hash": matrix_hash,
            "total_activities": db.query(LcaActivityRecord).count(),
            "total_flows": db.query(LcaFlowRecord).count(),
            "total_methods": db.query(LcaMethodRecord).count(),
            "total_units": db.query(UnitConversionRecord).count(),
            "total_runs": db.query(LcaRunRecord).count(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
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

