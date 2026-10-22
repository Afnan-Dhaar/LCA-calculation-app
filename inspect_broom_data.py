from broom_data import broom_data

# Read the product information.
product = broom_data["product"]

print("PRODUCT")
print("-" * 30)
print("Name:", product["name"])
print("Functional unit:", product["functional_unit"], product["unit"])

# Read the materials.
print("\nMATERIALS")
print("-" * 30)

for material in broom_data["materials"]:
    print(
        material["name"],
        "-",
        material["amount"],
        material["unit"],
    )

# Read manufacturing data.
manufacturing = broom_data["manufacturing"]

print("\nMANUFACTURING")
print("-" * 30)
print(
    "Electricity:",
    manufacturing["electricity"]["amount"],
    manufacturing["electricity"]["unit"],
)

# Read transportation data.
transport = broom_data["transportation"]

print("\nTRANSPORTATION")
print("-" * 30)
print("Distance:", transport["distance"], transport["unit"])
print("Mode:", transport["transport_mode"])
