from pathlib import Path

from excel_importer import import_products_from_excel

# Find the Excel template in the project folder.
excel_file = Path("product_lca_template.xlsx")

if not excel_file.exists():
    raise FileNotFoundError(
        "product_lca_template.xlsx was not found in this folder. "
        "Download the Excel template from the Excel Import tab "
        "in Product LCA Studio and save it in this project folder."
    )


# Convert the workbook into reusable product objects.
with excel_file.open("rb") as file:
    products = import_products_from_excel(file)


# Display the imported product models.
print(f"Successfully imported {len(products)} product(s).")

for product in products:
    print("\nProduct:", product.product_name)
    print(
        "Functional unit:",
        product.functional_unit_amount,
        product.functional_unit,
    )
    print("Processes:", len(product.processes))

    for process in product.processes:
        print(f"\n  Process: {process.process_name}")
        print("  Stage:", process.stage)

        for exchange in process.exchanges:
            print(
                f"    {exchange.exchange_type.title()}: "
                f"{exchange.flow_name} — "
                f"{exchange.amount} {exchange.unit}"
            )

        for transport in process.transportation:
            print(
                f"    Transport: {transport.transport_mode}, "
                f"{transport.distance} {transport.distance_unit}"
            )
