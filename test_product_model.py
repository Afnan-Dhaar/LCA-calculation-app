from product_model import (
    Exchange,
    Process,
    Product,
    Transportation,
    validate_product,
)

# Define a product with two life-cycle processes.
broom = Product(
    product_id="broom_001",
    product_name="Plastic broom",
    functional_unit_amount=1,
    functional_unit="unit",
    processes=[
        Process(
            process_id="material_production",
            process_name="Material production",
            stage="Raw materials",
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
            process_id="broom_manufacturing",
            process_name="Broom manufacturing",
            stage="Manufacturing",
            exchanges=[
                Exchange(
                    flow_name="Electricity",
                    exchange_type="input",
                    amount=0.20,
                    unit="kWh",
                ),
                Exchange(
                    flow_name="Plastic broom",
                    exchange_type="output",
                    amount=1,
                    unit="unit",
                ),
            ],
            transportation=[
                Transportation(
                    transport_mode="truck",
                    distance=100,
                    distance_unit="km",
                    transported_mass=0.40,
                    mass_unit="kg",
                )
            ],
        ),
    ],
)


# Validate the model.
errors = validate_product(broom)

if errors:
    print("Validation failed:")
    for error in errors:
        print("-", error)
else:
    print("Product model is valid!")

print("\nProduct:", broom.product_name)
print("Functional unit:", broom.functional_unit_amount, broom.functional_unit)
print("Number of processes:", len(broom.processes))

for process in broom.processes:
    print(f"\nProcess: {process.process_name}")
    print("Stage:", process.stage)

    for exchange in process.exchanges:
        print(
            f"  {exchange.exchange_type.title()}: "
            f"{exchange.flow_name} — {exchange.amount} {exchange.unit}"
        )

    for transport in process.transportation:
        print(
            f"  Transport: {transport.transport_mode}, "
            f"{transport.distance} {transport.distance_unit}"
        )

# Test Serialization & Payload Generation
print("\n" + "=" * 50)
print("TESTING JSON SERIALIZATION & PERSISTENCE")
print("=" * 50)
from product_model import dict_to_product, load_products_from_json, product_to_dict, save_products_to_json
import json
from pathlib import Path

payload = product_to_dict(broom)
print("Serialized Product Payload (preview):")
print(json.dumps(payload, indent=2)[:350] + "\n...")

# Test Deserialization
reconstructed = dict_to_product(payload)
assert reconstructed.product_id == broom.product_id
assert len(reconstructed.processes) == len(broom.processes)
assert reconstructed.processes[0].exchanges[0].flow_name == broom.processes[0].exchanges[0].flow_name
print("Deserialization verification: SUCCESS!")

# Test File Persistence
test_file = Path("test_saved_products.json")
save_products_to_json([broom], test_file)
assert test_file.exists(), "File should be created on disk"
loaded_from_disk = load_products_from_json(test_file)
assert len(loaded_from_disk) == 1
assert loaded_from_disk[0].product_name == broom.product_name
test_file.unlink()  # cleanup
print("Disk persistence verification: SUCCESS!")
