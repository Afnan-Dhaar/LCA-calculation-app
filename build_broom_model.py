import bw2data as bd

from broom_data import broom_data

# Select our Brightway project.
bd.projects.set_current("brightway_learning_project")

# Open the broom database.
db = bd.Database("broom_lca_db")

# Create the main product activity from structured input data.
broom = db.new_activity(
    code="plastic_broom",
    name=broom_data["product"]["name"],
    unit=broom_data["product"]["unit"],
    type="process",
)

# Define the activity's reference product output.
broom.new_exchange(
    input=broom.key,
    amount=broom_data["product"]["functional_unit"],
    type="production",
).save()

# Save the activity to the Brightway database.
broom.save()

print("Created Brightway activity:")
print("Name:", broom["name"])
print("Database:", broom.key[0])
print("Unit:", broom["unit"])
print("Activity key:", broom.key)
