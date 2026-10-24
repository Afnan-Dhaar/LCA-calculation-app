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
import os
import threading
import time
from pathlib import Path
from typing import Any, Literal

import bw2data as bd
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, Security, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

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
# Production Security & Throttling Configuration
# --------------------------------------------------

API_SECURITY_ENABLED = os.getenv("API_SECURITY_ENABLED", "false").lower() in ("true", "1")
API_KEY = os.getenv("API_KEY", "lca-studio-secret-2026")
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "120"))
MAX_PAYLOAD_BYTES = int(os.getenv("MAX_PAYLOAD_BYTES", str(10 * 1024 * 1024)))  # 10 MB limit

api_key_header_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)


def verify_api_key(
    key_header: str | None = Security(api_key_header_scheme),
    bearer_token: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
) -> str:
    """Validate API key via 'X-API-Key' or 'Authorization: Bearer <key>'.
    Bypassed when API_SECURITY_ENABLED is false (e.g. development/testing mode).
    """
    if not API_SECURITY_ENABLED:
        return "development_bypass"

    token = key_header or (bearer_token.credentials if bearer_token else None)
    if not token or token != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key. Provide valid key via 'X-API-Key' header or 'Authorization: Bearer <key>'.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token


class SlidingWindowRateLimiter:
    """Thread-safe in-memory sliding window rate limiter."""

    def __init__(self, limit_per_minute: int = 120):
        self.limit = limit_per_minute
        self.records: dict[str, list[float]] = {}
        self.lock = threading.Lock()
        self.enabled = os.getenv("RATE_LIMIT_ENABLED", "true").lower() in ("true", "1")

    def check(self, client_ip: str) -> tuple[bool, int]:
        if not self.enabled:
            return True, 0
        now = time.time()
        window_start = now - 60.0
        with self.lock:
            timestamps = self.records.get(client_ip, [])
            timestamps = [t for t in timestamps if t > window_start]
            if len(timestamps) >= self.limit:
                retry_after = max(1, int(60.0 - (now - timestamps[0])))
                self.records[client_ip] = timestamps
                return False, retry_after
            timestamps.append(now)
            self.records[client_ip] = timestamps
            return True, 0


rate_limiter = SlidingWindowRateLimiter(limit_per_minute=RATE_LIMIT_PER_MINUTE)


class ProductionGuardsMiddleware(BaseHTTPMiddleware):
    """Enforces maximum payload size and rate limits calculation endpoints."""

    async def dispatch(self, request: Request, call_next):
        # 1. Payload size guard
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > MAX_PAYLOAD_BYTES:
                    return JSONResponse(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        content={"detail": f"Payload exceeds maximum allowed size of {MAX_PAYLOAD_BYTES} bytes."},
                    )
            except ValueError:
                pass

        # 2. Rate limiting guard on calculating endpoints
        if request.url.path.startswith("/v1/lca/calculate") or request.url.path.startswith("/api/lca/calculate"):
            client_ip = request.client.host if request.client else "unknown"
            allowed, retry_after = rate_limiter.check(client_ip)
            if not allowed:
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={"detail": "Too many LCA calculation requests. Please slow down."},
                    headers={"Retry-After": str(retry_after)},
                )

        response = await call_next(request)
        return response


# --------------------------------------------------
# FastAPI App Initialization
# --------------------------------------------------

app = FastAPI(
    title="PCF LCA API (Brightway)",
    description=(
        "Enterprise Life Cycle Assessment & Product Carbon Footprint microservice powered by Brightway 2.5 and PostgreSQL. "
        "Dynamic background database management for flows, activities, methods, and calculation runs."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


@app.on_event("startup")
def startup_event():
    """Ensure database tables and Brightway project are synchronized on boot."""
    try:
        database.init_db()
        import brightway_engine
        brightway_engine.sync_pcf_lca_project(force=False)
    except Exception as err:
        print(f"Startup synchronization notice: {err}")


# Production guards and CORS middlewares
app.add_middleware(ProductionGuardsMiddleware)
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


# --------------------------------------------------
# /v1 Dynamic Pydantic Schemas (Matching Senior's API)
# --------------------------------------------------


class UnitSchema(BaseModel):
    code: str = Field(..., description="Unique unit conversion key, e.g. 'tonne_to_kg'")
    from_unit: str = Field(..., description="Source unit, e.g. 'tonne'")
    to_unit: str = Field(..., description="Target unit, e.g. 'kilogram'")
    factor: float = Field(..., description="Multiplication factor to convert from_unit to to_unit")
    dimension: str = Field(default="mass", description="Physical dimension (mass, energy, volume, distance)")


class FlowSchema(BaseModel):
    code: str = Field(..., description="Elementary emission code, e.g. 'co2', 'ch4', 'so2'")
    name: str = Field(..., description="Descriptive flow name, e.g. 'Carbon dioxide, fossil'")
    unit: str = Field(default="kilogram", description="Unit of elementary flow")
    categories: str = Field(default="air", description="Environmental compartment: air, water, or soil")
    flow_type: str = Field(default="emission", description="Flow classification")


class MethodSchema(BaseModel):
    key: str = Field(..., description="Method identifier, e.g. 'gwp100' or 'acidification'")
    name: str = Field(..., description="Human-readable method title")
    method_tuple: list[str] = Field(..., description="Brightway hierarchy tuple, e.g. ['IPCC AR6', 'GWP100']")
    unit: str = Field(default="kg CO2-Eq", description="Characterization impact unit")
    cfs: dict[str, float] = Field(default_factory=dict, description="Mapping of elementary flow code to characterization factor")


class ActivitySchema(BaseModel):
    code: str = Field(..., description="Activity code, e.g. 'crude_oil', 'electricity_grid_sa'")
    name: str = Field(..., description="Descriptive activity title")
    unit: str = Field(..., description="Reference unit, e.g. 'kilogram', 'kilowatt hour', 'ton kilometer'")
    location: str = Field(default="GLO", description="Geographic coverage: SA, GLO, RoW")
    emissions: dict[str, float] = Field(default_factory=dict, description="Direct elementary emissions {flow_code: amount}")
    technosphere: dict[str, float] = Field(default_factory=dict, description="Background upstream inputs {activity_code: amount}")


class CalculateLCARequest(BaseModel):
    product: ProductSchema | dict[str, Any]
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
    allocation_summary: dict[str, Any] | None = None


# --------------------------------------------------
# Helper Functions
# --------------------------------------------------


def pydantic_to_dataclass(schema: ProductSchema | dict[str, Any]) -> Product:
    """Convert Pydantic ProductSchema or raw payload dict to domain Product dataclass."""
    if isinstance(schema, dict):
        return dict_to_product(schema)
    return dict_to_product(schema.model_dump())


def lca_result_to_response(res: LCAResult, allocation_summary: dict[str, Any] | None = None) -> LCAResultResponse:
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
        allocation_summary=allocation_summary,
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
def save_or_update_product(product_in: ProductSchema | dict[str, Any]) -> dict[str, Any]:
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

        return lca_result_to_response(result, domain_product.allocation_summary)
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

        return lca_result_to_response(result, matched.allocation_summary)
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
    return database.get_db_status()


# ===========================================================================
# /v1 API Endpoints (Matching Senior's OpenAPI Tags & Routes)
# ===========================================================================

# --------------------------------------------------
# Auth & Security Status Endpoints
# --------------------------------------------------


@app.get("/v1/auth/status", tags=["security"], summary="Auth & Security Status")
def v1_auth_status() -> dict[str, Any]:
    """Retrieve current security and throttling configuration."""
    return {
        "security_enabled": API_SECURITY_ENABLED,
        "rate_limit_per_minute": RATE_LIMIT_PER_MINUTE,
        "max_payload_bytes": MAX_PAYLOAD_BYTES,
    }


@app.get("/v1/auth/verify", tags=["security"], summary="Verify API Key")
def v1_auth_verify(token: str = Depends(verify_api_key)) -> dict[str, Any]:
    """Verify validity of provided API key or Bearer token."""
    return {"status": "authenticated", "client": token}


# --------------------------------------------------
# 1. LCA Calculation
# --------------------------------------------------


@app.post("/v1/lca/calculate", tags=["lca"], summary="Calculate")
def v1_calculate_lca(
    payload: dict[str, Any],
    _auth: str = Depends(verify_api_key),
) -> dict[str, Any]:
    """Calculate cradle-to-gate environmental impacts (GWP100, Acidification)
    with ISO 14044 co-product mass/economic allocation and PostgreSQL audit logging.
    """
    try:
        import brightway_engine
        raw = payload.get("product") if (isinstance(payload.get("product"), dict) and "inputs" in payload.get("product")) else payload
        return brightway_engine.calculate_pcf_lca(raw)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"PCF LCA calculation failed: {str(e)}",
        )



# --------------------------------------------------
# 2. History & Audit Trail
# --------------------------------------------------


@app.get("/v1/runs", tags=["history"], summary="List Runs")
def v1_list_runs(limit: int = Query(default=50, ge=1, le=200)) -> list[dict[str, Any]]:
    """List historical calculation runs stored in PostgreSQL lca_run table."""
    return database.get_runs_db(limit=limit)


@app.get("/v1/runs/{run_id}", tags=["history"], summary="Get Run")
def v1_get_run(run_id: str) -> dict[str, Any]:
    """Retrieve full details of a specific calculation run."""
    run = database.get_run_by_id_db(run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Run '{run_id}' not found.")
    return run


# --------------------------------------------------
# 3. Units Management
# --------------------------------------------------


@app.get("/v1/units", tags=["units"], summary="List Units")
def v1_list_units() -> list[dict[str, Any]]:
    """List all unit conversion factors stored in PostgreSQL."""
    return database.get_all_units_db()


@app.post("/v1/units", tags=["units"], summary="Upsert Unit")
def v1_upsert_unit(unit_in: UnitSchema) -> dict[str, Any]:
    """Create or update a unit conversion factor."""
    return database.upsert_unit_db(unit_in.model_dump())


@app.delete("/v1/units/{code}", tags=["units"], summary="Delete Unit")
def v1_delete_unit(code: str) -> dict[str, Any]:
    """Remove a unit conversion factor from database."""
    ok = database.delete_unit_db(code)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unit '{code}' not found.")
    return {"status": "success", "deleted_code": code}


# --------------------------------------------------
# 4. Activities Management
# --------------------------------------------------


@app.get("/v1/activities", tags=["activities"], summary="List Activities")
def v1_list_activities() -> list[dict[str, Any]]:
    """List all background activities and emission factors stored in PostgreSQL."""
    return database.get_all_activities_db()


@app.post("/v1/activities", tags=["activities"], summary="Upsert Activity")
def v1_upsert_activity(act_in: ActivitySchema) -> dict[str, Any]:
    """Create or update a background activity and incrementally sync Brightway database."""
    try:
        res = database.upsert_activity_db(act_in.model_dump())
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(err))

    import brightway_engine
    brightway_engine.sync_single_activity(act_in.code)
    return res


@app.delete("/v1/activities/{code}", tags=["activities"], summary="Delete Activity")
def v1_delete_activity(
    code: str,
    cascade: bool = Query(default=False, description="Cascade delete downstream dependencies"),
) -> dict[str, Any]:
    """Remove a background activity from database with downstream dependency check."""
    try:
        ok = database.delete_activity_db(code, cascade=cascade)
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(err))

    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Activity '{code}' not found.")
    import brightway_engine
    brightway_engine.delete_single_activity(code)
    return {"status": "success", "deleted_code": code}


# --------------------------------------------------
# 5. Flows Management
# --------------------------------------------------


@app.get("/v1/flows", tags=["flows"], summary="List Flows")
def v1_list_flows() -> list[dict[str, Any]]:
    """List all elementary emissions and biosphere flows in PostgreSQL."""
    return database.get_all_flows_db()


@app.post("/v1/flows", tags=["flows"], summary="Upsert Flow")
def v1_upsert_flow(flow_in: FlowSchema) -> dict[str, Any]:
    """Create or update an elementary flow and incrementally sync Brightway biosphere."""
    try:
        res = database.upsert_flow_db(flow_in.model_dump())
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(err))

    import brightway_engine
    brightway_engine.sync_single_flow(flow_in.code)
    return res


@app.delete("/v1/flows/{code}", tags=["flows"], summary="Delete Flow")
def v1_delete_flow(
    code: str,
    cascade: bool = Query(default=False, description="Cascade delete dependencies in activities and methods"),
) -> dict[str, Any]:
    """Remove an elementary flow from database with dependency checking."""
    try:
        ok = database.delete_flow_db(code, cascade=cascade)
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(err))

    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Flow '{code}' not found.")
    import brightway_engine
    brightway_engine.delete_single_flow(code)
    return {"status": "success", "deleted_code": code}


# --------------------------------------------------
# 6. Methods Management
# --------------------------------------------------


@app.get("/v1/methods", tags=["methods"], summary="List Methods")
def v1_list_methods() -> list[dict[str, Any]]:
    """List all configured LCIA methods and characterization factors."""
    return database.get_all_methods_db()


@app.post("/v1/methods", tags=["methods"], summary="Upsert Method")
def v1_upsert_method(method_in: MethodSchema) -> dict[str, Any]:
    """Create or update an LCIA method and incrementally sync Brightway."""
    try:
        res = database.upsert_method_db(method_in.model_dump())
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(err))

    import brightway_engine
    brightway_engine.sync_single_method(method_in.key)
    return res


@app.delete("/v1/methods/{key}", tags=["methods"], summary="Delete Method")
def v1_delete_method(key: str) -> dict[str, Any]:
    """Remove an LCIA method from database and deregister from Brightway."""
    try:
        ok = database.delete_method_db(key)
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(err))

    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Method '{key}' not found.")
    import brightway_engine
    brightway_engine.delete_single_method(key)
    return {"status": "success", "deleted_key": key}


# --------------------------------------------------
# 7. Database Version & Audit Fingerprint
# --------------------------------------------------


@app.get("/v1/database/version", tags=["database", "health"], summary="Database Version & Matrix Fingerprint")
def v1_database_version() -> dict[str, Any]:
    """Retrieve database status, active database engine, record counts, and deterministic SHA-256 matrix hash."""
    return database.get_db_status()



# --------------------------------------------------
# Entrypoint for running with 'python api.py'
# --------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    print("Starting Brightway Product LCA API server on http://localhost:8000...")
    print("Interactive Swagger documentation available at: http://localhost:8000/docs")
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
