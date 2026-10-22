from dataclasses import dataclass, field
from typing import Literal

ExchangeType = Literal["input", "output"]


@dataclass
class Exchange:
    flow_name: str
    exchange_type: ExchangeType
    amount: float
    unit: str


@dataclass
class Transportation:
    transport_mode: str
    distance: float
    distance_unit: str
    transported_mass: float | None = None
    mass_unit: str | None = None


@dataclass
class Process:
    process_id: str
    process_name: str
    stage: str
    exchanges: list[Exchange] = field(default_factory=list)
    transportation: list[Transportation] = field(default_factory=list)


@dataclass
class Product:
    product_id: str
    product_name: str
    functional_unit_amount: float
    functional_unit: str
    processes: list[Process] = field(default_factory=list)
    allocation_summary: dict | None = None


def validate_product(product: Product) -> list[str]:
    """Return validation errors; an empty list means the model passed."""
    errors = []

    if not product.product_id.strip():
        errors.append("Product ID is required.")

    if not product.product_name.strip():
        errors.append("Product name is required.")

    if product.functional_unit_amount <= 0:
        errors.append("Functional unit amount must be greater than zero.")

    if not product.functional_unit.strip():
        errors.append("Functional unit is required.")

    process_ids = [process.process_id for process in product.processes]

    if len(process_ids) != len(set(process_ids)):
        errors.append("Process IDs must be unique within a product.")

    for process in product.processes:
        if not process.process_id.strip():
            errors.append("Every process needs a process ID.")

        if not process.process_name.strip():
            errors.append(f"Process {process.process_id!r} needs a name.")

        for exchange in process.exchanges:
            if not exchange.flow_name.strip():
                errors.append(
                    f"Process {process.process_id!r} has an exchange "
                    "without a flow name."
                )

            if exchange.amount < 0:
                errors.append(f"Exchange {exchange.flow_name!r} has a negative amount.")

            if not exchange.unit.strip():
                errors.append(f"Exchange {exchange.flow_name!r} needs a unit.")

        for transport in process.transportation:
            if transport.distance < 0:
                errors.append(
                    f"Process {process.process_id!r} has a negative transport distance."
                )

            if transport.transported_mass is not None:
                if transport.transported_mass < 0:
                    errors.append(
                        f"Process {process.process_id!r} has a negative "
                        "transported mass."
                    )

    return errors


def product_to_dict(product: Product) -> dict:
    """Serialize a Product dataclass instance into a clean JSON-serializable dictionary (payload)."""
    result = {
        "product_id": product.product_id,
        "product_name": product.product_name,
        "functional_unit_amount": float(product.functional_unit_amount),
        "functional_unit": product.functional_unit,
        "processes": [
            {
                "process_id": proc.process_id,
                "process_name": proc.process_name,
                "stage": proc.stage,
                "exchanges": [
                    {
                        "flow_name": exc.flow_name,
                        "exchange_type": exc.exchange_type,
                        "amount": float(exc.amount),
                        "unit": exc.unit,
                    }
                    for exc in proc.exchanges
                ],
                "transportation": [
                    {
                        "transport_mode": tr.transport_mode,
                        "distance": float(tr.distance),
                        "distance_unit": tr.distance_unit,
                        "transported_mass": (
                            float(tr.transported_mass) if tr.transported_mass is not None else None
                        ),
                        "mass_unit": tr.mass_unit,
                    }
                    for tr in proc.transportation
                ],
            }
            for proc in product.processes
        ],
    }
    if product.allocation_summary:
        result["allocation_summary"] = product.allocation_summary
    return result


def is_flat_lca_payload(data: dict) -> bool:
    """Detect if a payload uses the flat refinery/process schema (with inputs/outputs/allocation)
    rather than the nested processes schema.
    """
    if not isinstance(data, dict):
        return False
    # If it already has processes array with process_id, it is our canonical schema
    if "processes" in data and isinstance(data["processes"], list) and len(data["processes"]) > 0:
        first_proc = data["processes"][0]
        if isinstance(first_proc, dict) and "process_id" in first_proc:
            return False
    return "inputs" in data or "outputs" in data or ("product" in data and isinstance(data["product"], dict))


def convert_flat_payload_to_product(data: dict) -> Product:
    """Transform a flat refinery/LCA payload (with inputs, outputs, allocation) into
    a fully structured Product instance with ISO 14044 co-product allocation applied.
    """
    import re

    # 1. Product Name, ID & Functional Unit
    if "product" in data and isinstance(data["product"], dict):
        prod_meta = data["product"]
        raw_name = prod_meta.get("name", "Product")
        raw_fu = str(prod_meta.get("functional_unit", "1 kg")).strip()
    else:
        raw_name = data.get("name", data.get("product_name", "Product"))
        raw_fu = str(data.get("functional_unit", "1 kg")).strip()

    # Extract amount and unit from string like "1 kg of diesel" or "1 kg"
    fu_amount = 1.0
    fu_unit = "kg"
    match = re.match(r"^([0-9.]+)\s*([a-zA-Z0-9]+)", raw_fu)
    if match:
        try:
            fu_amount = float(match.group(1))
            fu_unit = match.group(2)
        except ValueError:
            pass
    elif raw_fu:
        fu_unit = raw_fu

    metadata = data.get("metadata", {})
    prod_id = str(metadata.get("product_code") or data.get("product_id") or "").strip()
    if not prod_id:
        prod_id = re.sub(r"[^a-zA-Z0-9_-]", "_", raw_name).strip("_").lower()
        if not prod_id:
            prod_id = "prod_refinery_001"

    # 2. Allocation Calculation (ISO 14044)
    alloc_config = data.get("allocation", {})
    alloc_method = str(alloc_config.get("method", "mass")).strip().lower()

    outputs = data.get("outputs", [])
    main_product_amount = fu_amount
    main_product_price = 1.0
    co_products = []
    emissions = []
    wastes = []

    for out in outputs:
        out_type = str(out.get("type", "product")).strip().lower()
        if out_type == "product":
            main_product_amount = float(out.get("amount", fu_amount))
            main_product_price = float(out.get("price", 1.0))
        elif out_type in ["co_product", "coproduct"]:
            co_products.append(out)
        elif out_type == "emission":
            emissions.append(out)
        elif out_type in ["waste", "byproduct_waste"]:
            wastes.append(out)

    alloc_factor = 1.0
    allocation_summary = None

    if co_products:
        if alloc_method == "mass":
            total_mass = main_product_amount + sum(float(cp.get("amount", 0.0)) for cp in co_products)
            alloc_factor = (main_product_amount / total_mass) if total_mass > 0 else 1.0
            allocation_summary = {
                "method": "mass",
                "allocation_factor": round(alloc_factor, 6),
                "allocation_percentage": round(alloc_factor * 100, 2),
                "target_product_amount": main_product_amount,
                "total_co_product_amount": total_mass - main_product_amount,
                "total_system_mass": total_mass,
                "co_products": [
                    {
                        "name": cp.get("name", "Co-product"),
                        "amount": float(cp.get("amount", 0.0)),
                        "share_pct": round((float(cp.get("amount", 0.0)) / total_mass) * 100, 2),
                    }
                    for cp in co_products
                ],
            }
        elif alloc_method == "economic":
            total_val = (main_product_amount * main_product_price) + sum(
                float(cp.get("amount", 0.0)) * float(cp.get("price", 1.0)) for cp in co_products
            )
            target_val = main_product_amount * main_product_price
            alloc_factor = (target_val / total_val) if total_val > 0 else 1.0
            allocation_summary = {
                "method": "economic",
                "allocation_factor": round(alloc_factor, 6),
                "allocation_percentage": round(alloc_factor * 100, 2),
                "target_product_revenue": target_val,
                "total_system_revenue": total_val,
                "co_products": [
                    {
                        "name": cp.get("name", "Co-product"),
                        "amount": float(cp.get("amount", 0.0)),
                        "price": float(cp.get("price", 1.0)),
                        "revenue": float(cp.get("amount", 0.0)) * float(cp.get("price", 1.0)),
                    }
                    for cp in co_products
                ],
            }

    # 3. Process Stages Grouping
    STAGE_MAP = {
        "raw_material": ("Raw Material Acquisition", "Feedstock & Extraction"),
        "raw_materials": ("Raw Material Acquisition", "Feedstock & Extraction"),
        "manufacturing": ("Manufacturing", "Refining & Processing Operations"),
        "refining": ("Manufacturing", "Refining Operations"),
        "production": ("Manufacturing", "Production Operations"),
        "transport": ("Distribution & Transport", "Feedstock Logistics"),
        "transportation": ("Distribution & Transport", "Feedstock Logistics"),
        "logistics": ("Distribution & Transport", "Logistics"),
        "distribution": ("Distribution & Transport", "Distribution"),
        "use": ("Use Phase", "Product Use"),
        "end_of_life": ("End of Life", "End of Life"),
        "waste": ("End of Life", "Waste Management"),
    }

    processes_map: dict[str, dict] = {}

    def get_or_create_process(stage_key: str) -> dict:
        norm_key = stage_key.lower().strip()
        canonical_stage, default_proc_name = STAGE_MAP.get(
            norm_key, (norm_key.title(), norm_key.title())
        )
        proc_id = f"proc_{norm_key}"
        if proc_id not in processes_map:
            processes_map[proc_id] = {
                "process_id": proc_id,
                "process_name": default_proc_name,
                "stage": canonical_stage,
                "exchanges": [],
                "transportation": [],
            }
        return processes_map[proc_id]

    # Process Inputs
    for inp in data.get("inputs", []):
        raw_stage = str(inp.get("stage", "manufacturing")).strip().lower()

        # Check if this input represents transportation (has distance_km or transport key)
        if "distance_km" in inp or "distance" in inp:
            dist = float(inp.get("distance_km", inp.get("distance", 0.0)))
            mass = inp.get("mass", inp.get("amount"))
            mass_val = (float(mass) * alloc_factor) if mass is not None else None
            mass_unit = str(inp.get("mass_unit", inp.get("unit", "kg"))).strip()
            mode = str(inp.get("key", inp.get("name", "truck"))).strip()

            proc = get_or_create_process(raw_stage if raw_stage in ["transport", "transportation", "distribution"] else "transport")
            proc["transportation"].append(
                Transportation(
                    transport_mode=mode,
                    distance=dist,
                    distance_unit=str(inp.get("distance_unit", "km")).strip(),
                    transported_mass=mass_val,
                    mass_unit=mass_unit,
                )
            )
        else:
            flow_name = str(inp.get("name", inp.get("key", ""))).strip()
            raw_amt = float(inp.get("amount", 0.0))
            allocated_amt = raw_amt * alloc_factor
            unit = str(inp.get("unit", "kg")).strip()

            proc = get_or_create_process(raw_stage)
            proc["exchanges"].append(
                Exchange(
                    flow_name=flow_name,
                    exchange_type="input",
                    amount=allocated_amt,
                    unit=unit,
                )
            )

    # Process Emissions (outputs) -> direct biosphere emissions
    for em in emissions:
        flow_name = str(em.get("name", em.get("flow", ""))).strip()
        raw_amt = float(em.get("amount", 0.0))
        allocated_amt = raw_amt * alloc_factor
        unit = str(em.get("unit", "kg")).strip()

        proc = get_or_create_process("manufacturing")
        proc["exchanges"].append(
            Exchange(
                flow_name=flow_name,
                exchange_type="output",
                amount=allocated_amt,
                unit=unit,
            )
        )

    # Process Waste (outputs) -> technosphere waste treatment services
    for w in wastes:
        flow_name = str(w.get("name", w.get("key", ""))).strip()
        raw_amt = float(w.get("amount", 0.0))
        allocated_amt = raw_amt * alloc_factor
        unit = str(w.get("unit", "kg")).strip()

        proc = get_or_create_process("manufacturing")
        proc["exchanges"].append(
            Exchange(
                flow_name=flow_name,
                exchange_type="input",
                amount=allocated_amt,
                unit=unit,
            )
        )

    processes = [
        Process(
            process_id=p["process_id"],
            process_name=p["process_name"],
            stage=p["stage"],
            exchanges=p["exchanges"],
            transportation=p["transportation"],
        )
        for p in processes_map.values()
    ]

    return Product(
        product_id=prod_id,
        product_name=raw_name,
        functional_unit_amount=fu_amount,
        functional_unit=fu_unit,
        processes=processes,
        allocation_summary=allocation_summary,
    )


def dict_to_product(data: dict) -> Product:
    """Deserialize a dictionary payload into a Product dataclass instance.
    Automatically detects and adapts flat refinery payloads (inputs/outputs/allocation)
    into standard Product objects with ISO 14044 allocation.
    """
    if is_flat_lca_payload(data):
        return convert_flat_payload_to_product(data)

    processes = []
    for proc_data in data.get("processes", []):
        exchanges = [
            Exchange(
                flow_name=str(e.get("flow_name", "")).strip(),
                exchange_type=str(e.get("exchange_type", "input")).strip().lower(),  # type: ignore
                amount=float(e.get("amount", 0.0)),
                unit=str(e.get("unit", "")).strip(),
            )
            for e in proc_data.get("exchanges", [])
        ]

        transportation = [
            Transportation(
                transport_mode=str(t.get("transport_mode", "truck")).strip().lower(),
                distance=float(t.get("distance", 0.0)),
                distance_unit=str(t.get("distance_unit", "km")).strip(),
                transported_mass=(
                    float(t["transported_mass"]) if t.get("transported_mass") is not None else None
                ),
                mass_unit=str(t.get("mass_unit", "kg")).strip() if t.get("mass_unit") else None,
            )
            for t in proc_data.get("transportation", [])
        ]

        processes.append(
            Process(
                process_id=str(proc_data.get("process_id", "")).strip(),
                process_name=str(proc_data.get("process_name", "")).strip(),
                stage=str(proc_data.get("stage", "Manufacturing")).strip(),
                exchanges=exchanges,
                transportation=transportation,
            )
        )

    return Product(
        product_id=str(data.get("product_id", "")).strip(),
        product_name=str(data.get("product_name", "")).strip(),
        functional_unit_amount=float(data.get("functional_unit_amount", 1.0)),
        functional_unit=str(data.get("functional_unit", "unit")).strip(),
        processes=processes,
        allocation_summary=data.get("allocation_summary"),
    )


def save_products_to_json(products: list[Product], file_path: str = "saved_products.json") -> None:
    """Persist a list of Product objects to disk as JSON."""
    import json
    from pathlib import Path

    payload = [product_to_dict(p) for p in products]
    Path(file_path).write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_products_from_json(file_path: str = "saved_products.json") -> list[Product]:
    """Load a list of Product objects from a JSON file on disk."""
    import json
    from pathlib import Path

    path = Path(file_path)
    if not path.exists():
        return []

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [dict_to_product(item) for item in data if isinstance(item, dict)]
        elif isinstance(data, dict):
            return [dict_to_product(data)]
        return []
    except Exception:
        return []
