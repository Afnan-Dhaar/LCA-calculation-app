import bw2data as bd

# Select the Brightway project.
bd.projects.set_current("brightway_learning_project")

# Open the broom database.
db = bd.Database("broom_lca_db")

# Define the two material production activities.
materials = [
    {
        "code": "plastic_granules",
        "name": "Plastic granules production",
        "unit": "kilogram",
    },
    {
        "code": "broom_bristles",
        "name": "Broom bristles production",
        "unit": "kilogram",
    },
]

for material in materials:
    activity = db.new_activity(
        code=material["code"],
        name=material["name"],
        unit=material["unit"],
        type="process",
    )

    # Each process produces 1 kg of its material.
    activity.new_exchange(
        input=activity.key,
        amount=1,
        type="production",
    ).save()

    activity.save()

    print("Created:", activity["name"], "| Unit:", activity["unit"])

print("\nMaterial activities created successfully.")
