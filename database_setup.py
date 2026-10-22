import bw2data as bd

from inventory_data import CO2_PER_KWH


def setup_emission_flow():
    # Select the existing project
    bd.projects.set_current("brightway_learning_project")

    # Open the existing process database
    process_db = bd.Database("learning_db")

    # Create a separate database for our practice emission flow
    biosphere_name = "learning_biosphere"
    biosphere_db = bd.Database(biosphere_name)

    if biosphere_name not in bd.databases:
        biosphere_db.register()

    # Create the CO2 flow if it doesn't already exist
    flow_code = "co2_emission_to_air"

    if flow_code not in biosphere_db:
        biosphere_db.write(
            {
                (biosphere_name, flow_code): {
                    "name": "Carbon dioxide, emitted to air",
                    "code": flow_code,
                    "unit": "kilogram",
                    "categories": ("air",),
                    "type": "emission",
                    "exchanges": [],
                }
            }
        )

    # Retrieve the flow and electricity-producing activity
    co2_flow = biosphere_db.get(flow_code)
    electricity = process_db.get("electricity_production")

    # Add the emission exchange only if it doesn't exist
    existing = [
        exchange
        for exchange in electricity.exchanges()
        if exchange["type"] == "biosphere" and exchange.input.key == co2_flow.key
    ]

    if not existing:
        electricity.new_exchange(
            input=co2_flow.key,
            amount=CO2_PER_KWH,
            type="biosphere",
        ).save()

    print("Emission flow:", co2_flow["name"])
    print("Unit:", co2_flow["unit"])
    print("Emission factor:", CO2_PER_KWH, "kg CO2 per kWh")
    print("Electricity activity updated successfully.")


if __name__ == "__main__":
    setup_emission_flow()
