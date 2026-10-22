import bw2data as bd

from broom_data import broom_data

# Select the Brightway project.
bd.projects.set_current("brightway_learning_project")

# Get the broom activity and material activities.
db = bd.Database("broom_lca_db")
broom = db.get("plastic_broom")

# Connect each material input to the broom.
for material in broom_data["materials"]:
    material_code = material["name"].lower().replace(" ", "_")

    material_activity = db.get(material_code)

    # Avoid creating duplicate exchanges if this script is run again.
    existing = [
        exc for exc in broom.technosphere() if exc.input.key == material_activity.key
    ]

    if not existing:
        broom.new_exchange(
            input=material_activity.key,
            amount=material["amount"],
            type="technosphere",
        ).save()

    print(
        "Connected:",
        material_activity["name"],
        "| Amount:",
        material["amount"],
        material["unit"],
        "per broom",
    )

print("\nBroom material inputs connected successfully.")
