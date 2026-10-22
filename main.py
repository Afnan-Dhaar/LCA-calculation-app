import bw2data as bd

from inventory_data import (
    BOTTLES_PER_FUNCTIONAL_UNIT,
    ELECTRICITY_PER_BOTTLE,
)


def main():
    # Select our existing Brightway project
    bd.projects.set_current("brightway_learning_project")

    # Open our existing database
    db = bd.Database("learning_db")

    # Inspect emissions from electricity production
    electricity = db.get("electricity_production")

    print("\nElectricity production emissions:")
    for exchange in electricity.exchanges():
        if exchange["type"] == "biosphere":
            print(
                f"{exchange['amount']} "
                f"{exchange.input['unit']} of "
                f"{exchange.input['name']}"
            )

    bottle = db.get("bottle_manufacturing")

    electricity_exchange = next(
        exchange
        for exchange in bottle.exchanges()
        if exchange.input["code"] == "electricity_production"
    )

    print("Inventory validation:")
    print(
        "Expected electricity:",
        ELECTRICITY_PER_BOTTLE,
        "kWh per bottle",
    )
    print(
        "Database electricity:",
        electricity_exchange["amount"],
        "kWh per bottle",
    )
    print(
        "Values match:",
        electricity_exchange["amount"] == ELECTRICITY_PER_BOTTLE,
    )
    print()

    print("Brightway LCA Learning Project")
    print("-" * 35)

    # Display the inventory assumptions
    print("Practice inventory assumptions:")
    print(f"Bottles per functional unit: {BOTTLES_PER_FUNCTIONAL_UNIT}")
    print(f"Electricity per bottle: {ELECTRICITY_PER_BOTTLE} kWh")
    print()

    # Display all activities and their exchanges
    for activity in db:
        print(f"Activity: {activity['name']}")
        print(f"Code: {activity['code']}")
        print(f"Unit: {activity['unit']}")

        for exchange in activity.exchanges():
            print(
                f"  {exchange['type']}: "
                f"{exchange['amount']} "
                f"-> {exchange.input['name']}"
            )

        print()


if __name__ == "__main__":
    main()
