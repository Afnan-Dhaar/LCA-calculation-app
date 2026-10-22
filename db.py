"""
Database Layer for Brightway LCA Studio.

Supports PostgreSQL with automatic schema migration, and fallback to SQLite
if PostgreSQL is temporarily unreachable. Stores both product life-cycle models
and historical LCA assessment runs for auditing and analytics.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    desc,
    inspect,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from sqlalchemy.types import JSON

from brightway_engine import LCAResult
from product_model import Product, dict_to_product, load_products_from_json, product_to_dict

load_dotenv()

# Base directory
BASE_DIR = Path(__file__).resolve().parent

# Configurable database URL
DEFAULT_PG_URL = os.getenv("DATABASE_URL")
SQLITE_FALLBACK_URL = f"sqlite:///{BASE_DIR / 'lca_studio.db'}"

# Choose engine
target_url = DEFAULT_PG_URL if DEFAULT_PG_URL else SQLITE_FALLBACK_URL

try:
    if target_url.startswith("postgresql://") or target_url.startswith("postgresql+psycopg://"):
        engine = create_engine(target_url, pool_pre_ping=True)
        # Test connection
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

# Use JSON type compatible with both SQLite and Postgres
JsonType = JSON().with_variant(JSONB, "postgresql")


# ---------------------------------------------------------------------------
# Database Tables
# ---------------------------------------------------------------------------

class ProductRecord(Base):
    __tablename__ = "products"

    product_id = Column(String(100), primary_key=True, index=True)
    product_name = Column(String(255), nullable=False)
    functional_unit_amount = Column(Float, nullable=False, default=1.0)
    functional_unit = Column(String(50), nullable=False, default="unit")
    payload = Column(JsonType, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    runs = relationship("LcaRunRecord", back_populates="product", cascade="all, delete-orphan")


class LcaRunRecord(Base):
    __tablename__ = "lca_runs"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    product_id = Column(String(100), ForeignKey("products.product_id", ondelete="CASCADE"), index=True)
    product_name = Column(String(255), nullable=False)
    method_name = Column(String(255), nullable=False)
    method_unit = Column(String(50), nullable=False, default="kg CO2-eq")
    total_score = Column(Float, nullable=False)
    transport_score = Column(Float, default=0.0)
    transport_percentage = Column(Float, default=0.0)
    stage_breakdown = Column(JsonType, nullable=False)
    hotspots = Column(JsonType, nullable=False)
    flow_emissions = Column(JsonType, nullable=False)
    transport_breakdown = Column(JsonType, nullable=False)
    warnings = Column(JsonType, default=list)
    calculated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    product = relationship("ProductRecord", back_populates="runs")


# ---------------------------------------------------------------------------
# Initialization & Data Migration
# ---------------------------------------------------------------------------

def init_db(database_url: str | None = None) -> str:
    """Initialize tables and migrate saved_products.json into database if empty."""
    global engine, SessionLocal, active_db_type

    if database_url:
        try:
            if database_url.startswith("postgresql://") and "psycopg" not in database_url:
                database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)

            new_engine = create_engine(database_url, pool_pre_ping=True)
            with new_engine.connect() as conn:
                pass
            engine = new_engine
            SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
            active_db_type = "postgresql" if "postgresql" in database_url else "sqlite"
        except Exception as e:
            print(f"Failed to bind to provided database URL: {e}")

    Base.metadata.create_all(bind=engine)

    # Initial migration from saved_products.json if products table is empty
    db = SessionLocal()
    try:
        count = db.query(ProductRecord).count()
        json_path = BASE_DIR / "saved_products.json"
        if count == 0 and json_path.exists():
            saved_products = load_products_from_json(json_path)
            for p in saved_products:
                record = ProductRecord(
                    product_id=p.product_id,
                    product_name=p.product_name,
                    functional_unit_amount=p.functional_unit_amount,
                    functional_unit=p.functional_unit,
                    payload=product_to_dict(p),
                )
                db.add(record)
            db.commit()
            print(f"Migrated {len(saved_products)} product(s) from JSON into database ({active_db_type}).")
    except Exception as err:
        db.rollback()
        print(f"Migration error: {err}")
    finally:
        db.close()

    return active_db_type


# ---------------------------------------------------------------------------
# CRUD Operations
# ---------------------------------------------------------------------------

def save_product_db(product: Product) -> ProductRecord:
    db = SessionLocal()
    try:
        existing = db.query(ProductRecord).filter(ProductRecord.product_id == product.product_id).first()
        payload = product_to_dict(product)
        if existing:
            existing.product_name = product.product_name
            existing.functional_unit_amount = product.functional_unit_amount
            existing.functional_unit = product.functional_unit
            existing.payload = payload
            existing.updated_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(existing)
            return existing
        else:
            new_rec = ProductRecord(
                product_id=product.product_id,
                product_name=product.product_name,
                functional_unit_amount=product.functional_unit_amount,
                functional_unit=product.functional_unit,
                payload=payload,
            )
            db.add(new_rec)
            db.commit()
            db.refresh(new_rec)
            return new_rec
    finally:
        db.close()


def get_product_db(product_id: str) -> Product | None:
    db = SessionLocal()
    try:
        rec = db.query(ProductRecord).filter(ProductRecord.product_id == product_id).first()
        if not rec:
            return None
        return dict_to_product(rec.payload)
    finally:
        db.close()


def list_products_db() -> list[dict[str, Any]]:
    db = SessionLocal()
    try:
        recs = db.query(ProductRecord).order_by(ProductRecord.product_name).all()
        return [r.payload for r in recs]
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


def record_lca_run_db(product: Product, result: LCAResult) -> LcaRunRecord:
    """Save an LCA calculation run into the database for auditing & historical tracking."""
    db = SessionLocal()
    try:
        # Ensure parent product exists in DB
        save_product_db(product)

        run = LcaRunRecord(
            product_id=product.product_id,
            product_name=product.product_name,
            method_name=result.method_name,
            method_unit=result.method_unit,
            total_score=result.total_score,
            transport_score=result.transport_score,
            transport_percentage=result.transport_percentage,
            stage_breakdown=[
                {"stage": s.stage, "score": s.score, "percentage": s.percentage, "unit": s.unit}
                for s in result.stage_contributions
            ],
            hotspots=[
                {
                    "process_id": p.process_id,
                    "process_name": p.process_name,
                    "stage": p.stage,
                    "score": p.score,
                    "percentage": p.percentage,
                    "unit": p.unit,
                }
                for p in result.process_contributions
            ],
            flow_emissions=[
                {
                    "flow_name": f.flow_name,
                    "category": f.category,
                    "amount": f.amount,
                    "unit": f.unit,
                    "score": f.score,
                    "percentage": f.percentage,
                }
                for f in result.flow_contributions
            ],
            transport_breakdown=[
                {
                    "process_name": t.process_name,
                    "mode": t.mode,
                    "distance_km": t.distance_km,
                    "mass_kg": t.mass_kg,
                    "tkm": t.tkm,
                    "score": t.score,
                    "percentage": t.percentage,
                }
                for t in result.transport_contributions
            ],
            warnings=result.warnings,
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        return run
    finally:
        db.close()


def list_lca_runs_db(product_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    db = SessionLocal()
    try:
        query = db.query(LcaRunRecord)
        if product_id:
            query = query.filter(LcaRunRecord.product_id == product_id)
        runs = query.order_by(desc(LcaRunRecord.calculated_at)).limit(limit).all()

        return [
            {
                "run_id": r.id,
                "product_id": r.product_id,
                "product_name": r.product_name,
                "method_name": r.method_name,
                "method_unit": r.method_unit,
                "total_score": r.total_score,
                "transport_score": r.transport_score,
                "transport_percentage": r.transport_percentage,
                "stage_breakdown": r.stage_breakdown,
                "hotspots": r.hotspots,
                "calculated_at": r.calculated_at.isoformat() if r.calculated_at else None,
            }
            for r in runs
        ]
    finally:
        db.close()


# Run initialization on import
init_db()
