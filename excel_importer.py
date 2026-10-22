import pandas as pd

from product_model import (
    Exchange,
    Process,
    Product,
    Transportation,
    validate_product,
)


def import_products_from_excel(uploaded_file):
    """Convert a workbook into validated Product objects."""

    workbook = pd.ExcelFile(uploaded_file)

    required_sheets = {
        "Products",
        "Processes",
        "Exchanges",
        "Transportation",
    }

    missing_sheets = required_sheets - set(workbook.sheet_names)

    if missing_sheets:
        raise ValueError(
            "Missing required sheets: " + ", ".join(sorted(missing_sheets))
        )

    tables = {
        name: pd.read_excel(workbook, sheet_name=name) for name in required_sheets
    }

    # Check required columns.
    required_columns = {
        "Products": [
            "product_id",
            "product_name",
            "functional_unit_amount",
            "functional_unit",
        ],
        "Processes": [
            "process_id",
            "product_id",
            "process_name",
            "stage",
        ],
        "Exchanges": [
            "process_id",
            "flow_name",
            "exchange_type",
            "amount",
            "unit",
        ],
        "Transportation": [
            "process_id",
            "transport_mode",
            "distance",
            "distance_unit",
            "transported_mass",
            "mass_unit",
        ],
    }

    for sheet, columns in required_columns.items():
        missing = set(columns) - set(tables[sheet].columns)

        if missing:
            raise ValueError(
                f"{sheet} is missing columns: " + ", ".join(sorted(missing))
            )

    products_table = tables["Products"]
    processes_table = tables["Processes"]
    exchanges_table = tables["Exchanges"]
    transport_table = tables["Transportation"]

    if products_table["product_id"].isna().any():
        raise ValueError("Every product needs a product_id.")

    if products_table["product_id"].duplicated().any():
        raise ValueError("Duplicate product IDs found.")

    products = []

    for _, product_row in products_table.iterrows():
        product_id = str(product_row["product_id"]).strip()

        product_processes = []

        matching_processes = processes_table[
            processes_table["product_id"].astype(str).str.strip() == product_id
        ]

        for _, process_row in matching_processes.iterrows():
            process_id = str(process_row["process_id"]).strip()

            matching_exchanges = exchanges_table[
                exchanges_table["process_id"].astype(str).str.strip() == process_id
            ]

            exchanges = []

            for _, exchange_row in matching_exchanges.iterrows():
                exchange_type = str(exchange_row["exchange_type"]).strip().lower()

                if exchange_type not in {"input", "output"}:
                    raise ValueError(
                        f"Invalid exchange_type {exchange_type!r} "
                        f"for process {process_id!r}. "
                        "Use 'input' or 'output'."
                    )

                exchanges.append(
                    Exchange(
                        flow_name=str(exchange_row["flow_name"]).strip(),
                        exchange_type=exchange_type,
                        amount=float(exchange_row["amount"]),
                        unit=str(exchange_row["unit"]).strip(),
                    )
                )

            matching_transport = transport_table[
                transport_table["process_id"].astype(str).str.strip() == process_id
            ]

            transportation = []

            for _, transport_row in matching_transport.iterrows():
                if pd.isna(transport_row["distance"]):
                    raise ValueError(f"Missing distance for process {process_id!r}.")

                mass = transport_row["transported_mass"]

                transportation.append(
                    Transportation(
                        transport_mode=str(transport_row["transport_mode"]).strip(),
                        distance=float(transport_row["distance"]),
                        distance_unit=str(transport_row["distance_unit"]).strip(),
                        transported_mass=(None if pd.isna(mass) else float(mass)),
                        mass_unit=(
                            None
                            if pd.isna(transport_row["mass_unit"])
                            else str(transport_row["mass_unit"]).strip()
                        ),
                    )
                )

            product_processes.append(
                Process(
                    process_id=process_id,
                    process_name=str(process_row["process_name"]).strip(),
                    stage=str(process_row["stage"]).strip(),
                    exchanges=exchanges,
                    transportation=transportation,
                )
            )

        product = Product(
            product_id=product_id,
            product_name=str(product_row["product_name"]).strip(),
            functional_unit_amount=float(product_row["functional_unit_amount"]),
            functional_unit=str(product_row["functional_unit"]).strip(),
            processes=product_processes,
        )

        errors = validate_product(product)

        if errors:
            raise ValueError(
                f"Product {product_id!r} has validation errors: " + "; ".join(errors)
            )

        products.append(product)

    return products
