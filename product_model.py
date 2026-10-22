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
    return {
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


def dict_to_product(data: dict) -> Product:
    """Deserialize a dictionary payload into a Product dataclass instance."""
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
