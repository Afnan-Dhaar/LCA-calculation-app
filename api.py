"""
FastAPI REST API Service for Brightway Product Life Cycle Assessment (LCA).

Provides endpoints for:
- Full cradle-to-grave LCA matrix calculation on dynamic product payloads
- Product model persistence and retrieval (CRUD)
- Querying installed LCIA methods (e.g. CML GWP100, EF, ReCiPe)
- Background flows and health check
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

import bw2data as bd
from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import db as database
from brightway_engine import (
    DEFAULT_LCIA_METHOD,
    DEFAULT_PROJECT,
    LCAResult,
    calculate_product_lca,
    get_available_methods,
)
from product_model import (
    Exchange,
    Process,
    Product,
    Transportation,
    dict_to_product,
    load_products_from_json,
    product_to_dict,
    save_products_to_json,
    validate_product,
)

# --------------------------------------------------
# FastAPI App Initialization
# --------------------------------------------------

app = FastAPI(
    title="Brightway Product LCA API",
    description=(
        "REST API service for dynamic, multi-process Life Cycle Assessment (LCA) powered by Brightway. "
        "Allows external applications, dashboards, and enterprise tools to model product supply chains, "
        "manage life-cycle stages, and compute characterized environmental impacts and hotspots in real-time."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Enable CORS for external frontend or microservice integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STORAGE_FILE = Path("saved_products.json")

# --------------------------------------------------
# Pydantic Request & Response Schemas
# --------------------------------------------------


class ExchangeSchema(BaseModel):
    flow_name: str = Field(..., description="Flow, material, or energy name (e.g. 'Plastic granules', 'Electricity, grid average', 'Carbon dioxide, fossil')")
    exchange_type: Literal["input", "output"] = Field(..., description="Direction: 'input' for resources/materials/energy, 'output' for products/emissions")
    amount: float = Field(..., ge=0.0, description="Amount consumed or emitted")
    unit: str = Field(default="kg", description="Measurement unit (e.g. kg, kWh, m3, unit)")


class TransportationSchema(BaseModel):
    transport_mode: str = Field(default="truck", description="Mode of transport: 'truck', 'train', 'ship', or 'air'")
    distance: float = Field(..., ge=0.0, description="Distance traveled in kilometers")
    distance_unit: str = Field(default="km", description="Distance unit")
    transported_mass: float | None = Field(default=1.0, ge=0.0, description="Weight of the transported cargo in mass_unit")
    mass_unit: str | None = Field(default="kg", description="Mass unit (e.g. kg or t)")


class ProcessSchema(BaseModel):
    process_id: str = Field(..., description="Unique process identifier string (e.g. 'raw_materials_prep')")
    process_name: str = Field(..., description="Human-readable process title")
    stage: str = Field(default="Manufacturing", description="Life cycle stage (e.g. Raw Materials, Manufacturing, Packaging, Distribution & Transport, Use Phase, End of Life)")
    exchanges: list[ExchangeSchema] = Field(default_factory=list, description="List of material/energy inputs or emissions")
    transportation: list[TransportationSchema] = Field(default_factory=list, description="List of freight transportation legs")


class ProductSchema(BaseModel):
    product_id: str = Field(..., description="Unique product code (e.g. 'pet_bottle_500ml')")
    product_name: str = Field(..., description="Product name (e.g. '500ml PET Beverage Bottle')")
    functional_unit_amount: float = Field(default=1.0, gt=0.0, description="Reference amount for LCA functional unit")
    functional_unit: str = Field(default="unit", description="Reference unit of analysis (e.g. unit, kg, piece)")
    processes: list[ProcessSchema] = Field(default_factory=list, description="Multi-stage supply chain processes")


class CalculateLCARequest(BaseModel):
    product: ProductSchema
    method: list[str] | tuple[str, ...] | None = Field(
        default=None,
        description="Optional LCIA method tuple. Defaults to CML v4.8 GWP100 climate change.",
        example=["CML v4.8 2016 no LT", "climate change no LT", "global warming potential (GWP100) no LT"],
    )


class CalculateSavedRequest(BaseModel):
    method: list[str] | tuple[str, ...] | None = Field(
        default=None,
        description="Optional LCIA method tuple. Defaults to CML v4.8 GWP100 climate change.",
        example=["CML v4.8 2016 no LT", "climate change no LT", "global warming potential (GWP100) no LT"],
    )


class ProcessContributionResponse(BaseModel):
    process_id: str
    process_name: str
    stage: str
    score: float
    percentage: float
    unit: str


class StageContributionResponse(BaseModel):
    stage: str
    score: float
    percentage: float
    unit: str


class FlowContributionResponse(BaseModel):
    flow_name: str
    category: str
    amount: float
    unit: str
    score: float
    percentage: float


class TransportContributionResponse(BaseModel):
    process_id: str
    process_name: str
    mode: str
    distance_km: float
    mass_kg: float
    tkm: float
    score: float
    percentage: float


class LCAResultResponse(BaseModel):
    product_id: str
    product_name: str
    functional_unit_amount: float
    functional_unit: str
    method_name: str
    method_unit: str
    total_score: float
    process_contributions: list[ProcessContributionResponse]
    stage_contributions: list[StageContributionResponse]
    flow_contributions: list[FlowContributionResponse]
    transport_contributions: list[TransportContributionResponse]
    transport_score: float
    transport_percentage: float
    inventory_summary: dict[str, float]
    warnings: list[str]


# --------------------------------------------------
# Helper Functions
# --------------------------------------------------


def pydantic_to_dataclass(schema: ProductSchema) -> Product:
    """Convert Pydantic ProductSchema to domain Product dataclass."""
    return dict_to_product(schema.model_dump())


def lca_result_to_response(res: LCAResult) -> LCAResultResponse:
    """Convert domain LCAResult dataclass to Pydantic response."""
    return LCAResultResponse(
        product_id=res.product_id,
        product_name=res.product_name,
        functional_unit_amount=res.functional_unit_amount,
        functional_unit=res.functional_unit,
        method_name=res.method_name,
        method_unit=res.method_unit,
        total_score=res.total_score,
        process_contributions=[
            ProcessContributionResponse(
                process_id=p.process_id,
                process_name=p.process_name,
                stage=p.stage,
                score=p.score,
                percentage=p.percentage,
                unit=p.unit,
            )
            for p in res.process_contributions
        ],
        stage_contributions=[
            StageContributionResponse(
                stage=s.stage,
                score=s.score,
                percentage=s.percentage,
                unit=s.unit,
            )
            for s in res.stage_contributions
        ],
        flow_contributions=[
            FlowContributionResponse(
                flow_name=f.flow_name,
                category=f.category,
                amount=f.amount,
                unit=f.unit,
                score=f.score,
                percentage=f.percentage,
            )
            for f in res.flow_contributions
        ],
        transport_contributions=[
            TransportContributionResponse(
                process_id=t.process_id,
                process_name=t.process_name,
                mode=t.mode,
                distance_km=t.distance_km,
                mass_kg=t.mass_kg,
                tkm=t.tkm,
                score=t.score,
                percentage=t.percentage,
            )
            for t in res.transport_contributions
        ],
        transport_score=res.transport_score,
        transport_percentage=res.transport_percentage,
        inventory_summary=res.inventory_summary,
        warnings=res.warnings,
    )


# --------------------------------------------------
# API Endpoints
# --------------------------------------------------


@app.get("/", tags=["Info"])
def root_info() -> dict[str, Any]:
    """Root endpoint providing service status and documentation link."""
    return {
        "service": "Brightway Product LCA API",
        "status": "online",
        "version": "1.0.0",
        "docs_url": "/docs",
        "redoc_url": "/redoc",
    }


@app.get("/health", tags=["Health"])
def health_check() -> dict[str, Any]:
    """System health check and Brightway environment diagnostics."""
    bd.projects.set_current(DEFAULT_PROJECT)
    return {
        "status": "healthy",
        "brightway_project": bd.projects.current,
        "installed_databases": list(bd.databases),
        "installed_methods_count": len(bd.methods),
        "persisted_products_file": str(STORAGE_FILE.resolve()),
        "persisted_products_exist": STORAGE_FILE.exists(),
    }


@app.get("/api/methods", tags=["LCIA Methods"])
def list_methods(
    search: str | None = Query(default=None, description="Search term to filter methods (e.g. 'climate', 'water', 'cml')"),
    limit: int = Query(default=50, ge=1, le=200, description="Maximum number of methods to return"),
) -> list[dict[str, Any]]:
    """List available Brightway Life Cycle Impact Assessment (LCIA) methods."""
    results = get_available_methods(search=search, limit=limit)
    return [
        {
            "method_tuple": list(m[0]),
            "display_name": m[1],
        }
        for m in results
    ]


@app.get("/api/products", response_model=list[ProductSchema], tags=["Product Storage"])
def get_all_products() -> list[dict[str, Any]]:
    """Retrieve all products stored in the workspace."""
    products = load_products_from_json(STORAGE_FILE)
    return [product_to_dict(p) for p in products]


@app.get("/api/products/{product_id}", response_model=ProductSchema, tags=["Product Storage"])
def get_product_by_id(product_id: str) -> dict[str, Any]:
    """Retrieve a specific product payload by its product_id."""
    products = load_products_from_json(STORAGE_FILE)
    matched = next((p for p in products if p.product_id == product_id), None)
    if not matched:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID '{product_id}' was not found in storage.",
        )
    return product_to_dict(matched)


@app.post("/api/products", status_code=status.HTTP_201_CREATED, tags=["Product Storage"])
def save_or_update_product(product_in: ProductSchema) -> dict[str, Any]:
    """Create or update a product life cycle model in storage."""
    product = pydantic_to_dataclass(product_in)
    errors = validate_product(product)
    if errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"validation_errors": errors},
        )

    products = load_products_from_json(STORAGE_FILE)
    existing_idx = next((i for i, p in enumerate(products) if p.product_id == product.product_id), None)

    if existing_idx is not None:
        products[existing_idx] = product
        action = "updated"
    else:
        products.append(product)
        action = "created"

    save_products_to_json(products, STORAGE_FILE)

    return {
        "status": "success",
        "action": action,
        "product_id": product.product_id,
        "product_name": product.product_name,
        "stages_count": len(product.processes),
    }


@app.delete("/api/products/{product_id}", tags=["Product Storage"])
def delete_product(product_id: str) -> dict[str, Any]:
    """Delete a product model from storage."""
    products = load_products_from_json(STORAGE_FILE)
    existing = [p for p in products if p.product_id == product_id]
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID '{product_id}' does not exist.",
        )

    remaining = [p for p in products if p.product_id != product_id]
    save_products_to_json(remaining, STORAGE_FILE)

    return {
        "status": "success",
        "deleted_product_id": product_id,
        "remaining_count": len(remaining),
    }


@app.post("/api/lca/calculate", response_model=LCAResultResponse, tags=["LCA Calculations"])
def calculate_lca(request: CalculateLCARequest) -> LCAResultResponse:
    """Calculate cradle-to-grave Life Cycle Assessment on any product payload in real time.

    Executes Brightway supply chain compilation, inventory generation (LCI),
    and characterized impact assessment (LCIA) with process and stage contribution breakdowns.
    """
    domain_product = pydantic_to_dataclass(request.product)
    errors = validate_product(domain_product)
    if errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"validation_errors": errors},
        )

    method_tuple = tuple(request.method) if request.method else DEFAULT_LCIA_METHOD

    try:
        result = calculate_product_lca(
            product=domain_product,
            method=method_tuple,
            project_name=DEFAULT_PROJECT,
        )
        try:
            database.record_lca_run_db(domain_product, result)
        except Exception as db_err:
            print(f"Warning: could not save run to database: {db_err}")

        return lca_result_to_response(result)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Brightway LCA calculation failed: {str(e)}",
        )


@app.post("/api/lca/calculate-saved/{product_id}", response_model=LCAResultResponse, tags=["LCA Calculations"])
def calculate_lca_on_saved_product(
    product_id: str,
    request: CalculateSavedRequest | None = None,
) -> LCAResultResponse:
    """Run LCA calculation on a product that has already been saved to the workspace."""
    products = load_products_from_json(STORAGE_FILE)
    matched = next((p for p in products if p.product_id == product_id), None)
    if not matched:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product '{product_id}' was not found in storage.",
        )

    method_tuple = tuple(request.method) if (request and request.method) else DEFAULT_LCIA_METHOD

    try:
        result = calculate_product_lca(
            product=matched,
            method=method_tuple,
            project_name=DEFAULT_PROJECT,
        )
        try:
            database.record_lca_run_db(matched, result)
        except Exception as db_err:
            print(f"Warning: could not save run to database: {db_err}")

        return lca_result_to_response(result)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Brightway LCA calculation failed: {str(e)}",
        )


# --------------------------------------------------
# LCA Audit & History Endpoints
# --------------------------------------------------


@app.get("/api/history", tags=["LCA Audit & History"])
def get_lca_history(
    product_id: str | None = Query(default=None, description="Optional product ID filter"),
    limit: int = Query(default=50, ge=1, le=200, description="Max history records to return"),
) -> list[dict[str, Any]]:
    """Retrieve historical LCA assessment runs stored in the relational database."""
    return database.list_lca_runs_db(product_id=product_id, limit=limit)


@app.get("/api/database/status", tags=["Health"])
def get_database_status() -> dict[str, Any]:
    """Check database status, connection type (PostgreSQL vs SQLite), and record counts."""
    return {
        "active_database": database.active_db_type,
        "is_postgresql": database.active_db_type == "postgresql",
        "total_products_stored": len(database.list_products_db()),
        "total_historical_runs": len(database.list_lca_runs_db(limit=1000)),
    }


# --------------------------------------------------
# Entrypoint for running with 'python api.py'
# --------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    print("Starting Brightway Product LCA API server on http://localhost:8000...")
    print("Interactive Swagger documentation available at: http://localhost:8000/docs")
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
