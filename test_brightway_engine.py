import sys

# Ensure UTF-8 output on Windows consoles
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from pathlib import Path
from brightway_engine import calculate_product_lca, get_available_methods
from excel_importer import import_products_from_excel
from product_model import Exchange, Process, Product, Transportation


def test_programmatic_product():
    """Test LCA calculation on a programmatically built multi-process product."""
    print("=" * 60)
    print("TEST 1: Programmatically defined Multi-Process Product")
    print("=" * 60)

    # Define a 2-stage product: Plastic Broom
    broom = Product(
        product_id="broom_test_001",
        product_name="Eco Plastic Broom",
        functional_unit_amount=1.0,
        functional_unit="unit",
        processes=[
            Process(
                process_id="mat_prod",
                process_name="Raw Material Compounding",
                stage="Raw Materials",
                exchanges=[
                    Exchange(
                        flow_name="Plastic granules",
                        exchange_type="input",
                        amount=0.30,
                        unit="kg",
                    ),
                    Exchange(
                        flow_name="Broom bristles",
                        exchange_type="input",
                        amount=0.10,
                        unit="kg",
                    ),
                ],
            ),
            Process(
                process_id="broom_mfg",
                process_name="Broom Assembly & Molding",
                stage="Manufacturing",
                exchanges=[
                    # Connect to upstream raw material process
                    Exchange(
                        flow_name="Raw Material Compounding",
                        exchange_type="input",
                        amount=1.0,
                        unit="unit",
                    ),
                    # Background electricity
                    Exchange(
                        flow_name="Electricity",
                        exchange_type="input",
                        amount=0.20,
                        unit="kWh",
                    ),
                    # Direct fossil CO2 emission
                    Exchange(
                        flow_name="Carbon dioxide, fossil",
                        exchange_type="output",
                        amount=0.05,
                        unit="kg",
                    ),
                ],
                transportation=[
                    Transportation(
                        transport_mode="truck",
                        distance=150,
                        distance_unit="km",
                        transported_mass=0.40,
                        mass_unit="kg",
                    )
                ],
            ),
        ],
    )

    result = calculate_product_lca(broom)

    print(f"Product: {result.product_name} ({result.product_id})")
    print(f"Functional Unit: {result.functional_unit_amount} {result.functional_unit}")
    print(f"Total Environmental Impact: {result.total_score:.4f} {result.method_unit}")
    print(f"Method: {result.method_name}")

    print("\n--- STAGE BREAKDOWN ---")
    for s in result.stage_contributions:
        print(f"  {s.stage:30} : {s.score:.4f} {s.unit} ({s.percentage:.1f}%)")

    print("\n--- PROCESS HOTSPOTS ---")
    for p in result.process_contributions:
        print(f"  {p.process_name:30} [{p.stage:20}] : {p.score:.4f} {p.unit} ({p.percentage:.1f}%)")

    print("\n--- ELEMENTARY EMISSIONS ---")
    for f in result.flow_contributions:
        print(f"  {f.flow_name:30} [{f.category:10}] : {f.amount:.4f} {f.unit} -> {f.score:.4f} kg CO2-eq ({f.percentage:.1f}%)")

    print("\n--- TRANSPORTATION LEGS ---")
    for t in result.transport_contributions:
        print(f"  {t.process_name} | {t.mode} | {t.distance_km} km | {t.mass_kg} kg ({t.tkm:.4f} tkm) -> {t.score:.4f} kg CO2-eq ({t.percentage:.1f}%)")

    assert result.total_score > 0, "LCA score should be strictly positive!"
    assert len(result.stage_contributions) >= 2, "Should have multiple stages!"
    print("\n>>> Programmatic Product LCA Test PASSED! <<<\n")


def test_excel_imported_product():
    """Test LCA calculation on products imported from the Excel template."""
    print("=" * 60)
    print("TEST 2: Excel Imported Multi-Process Product")
    print("=" * 60)

    excel_path = Path("product_lca_template.xlsx")
    if not excel_path.exists():
        print(f"File {excel_path} not found, skipping Excel test.")
        return

    with excel_path.open("rb") as f:
        products = import_products_from_excel(f)

    print(f"Imported {len(products)} product(s) from Excel.")
    for prod in products:
        result = calculate_product_lca(prod)
        print(f"\nProduct: {result.product_name}")
        print(f"Total LCA Impact: {result.total_score:.4f} {result.method_unit}")
        print("Stages:")
        for s in result.stage_contributions:
            print(f"  - {s.stage}: {s.score:.4f} {s.unit} ({s.percentage:.1f}%)")
        assert result.total_score > 0, "Imported Excel product LCA score should be positive!"

    print("\n>>> Excel Imported Product LCA Test PASSED! <<<\n")


def test_method_listing():
    """Test listing of available LCIA methods."""
    print("=" * 60)
    print("TEST 3: Available LCIA Methods")
    print("=" * 60)
    methods = get_available_methods("climate", limit=5)
    print(f"Found {len(methods)} climate methods:")
    for m_tuple, display in methods:
        print(f"  - {display}")
    assert len(methods) > 0, "Should find climate methods in Brightway!"
    print("\n>>> Method Listing Test PASSED! <<<\n")


if __name__ == "__main__":
    test_programmatic_product()
    test_excel_imported_product()
    test_method_listing()
    print("ALL BRIGHTWAY ENGINE TESTS PASSED!")
