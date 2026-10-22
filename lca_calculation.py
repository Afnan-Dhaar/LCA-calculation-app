import bw2calc as bc
import bw2data as bd

# The LCIA method we will use for climate-change assessment.
CLIMATE_CHANGE_METHOD = (
    "CML v4.8 2016 no LT",
    "climate change no LT",
    "global warming potential (GWP100) no LT",
)


def get_bottle_activity():
    """Retrieve the bottle manufacturing activity."""

    bd.projects.set_current("brightway_learning_project")
    db = bd.Database("learning_db")

    return db.get("bottle_manufacturing")


def calculate_inventory():
    """Calculate the life cycle inventory for one bottle."""

    bottle = get_bottle_activity()

    lca = bc.LCA({bottle: 1})
    lca.lci()

    total_co2 = float(lca.inventory.sum())

    print("Life Cycle Inventory (LCI)")
    print("-" * 35)
    print("Functional unit: 1 bottle")
    print(f"Total inventory amount: {total_co2:.4f} kg CO2")
    print(f"Total inventory amount: {total_co2 * 1000:.2f} g CO2")


def calculate_impact():
    """Calculate the climate-change impact for one bottle."""

    bottle = get_bottle_activity()

    # Create an LCA calculation using the selected impact method.
    lca = bc.LCA(
        {bottle: 1},
        method=CLIMATE_CHANGE_METHOD,
    )

    # First calculate the life cycle inventory.
    lca.lci()

    # Then calculate the environmental impact.
    lca.lcia()

    impact_score = float(lca.score)

    print("\nClimate Change Impact Assessment (LCIA)")
    print("-" * 42)
    print("Functional unit: 1 bottle")
    print("Method: CML GWP100")
    print(f"Impact: {impact_score:.6f} kg CO2-eq")
    print(f"Impact: {impact_score * 1000:.2f} g CO2-eq")


def list_lcia_methods():
    """List available life cycle impact assessment methods."""

    bd.projects.set_current("brightway_learning_project")
    methods = list(bd.methods)

    print("\nAvailable LCIA methods")
    print("-" * 35)

    if not methods:
        print("No LCIA methods are installed yet.")
        return

    for method in methods[:20]:
        print(method)

    print(f"\nTotal methods available: {len(methods)}")


if __name__ == "__main__":
    calculate_inventory()
    calculate_impact()
    list_lcia_methods()
