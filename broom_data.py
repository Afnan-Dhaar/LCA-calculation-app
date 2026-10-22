# Example input data for one plastic broom.
# These are fictional practice values, not measured data.

broom_data = {
    "product": {
        "name": "Plastic broom",
        "functional_unit": 1,
        "unit": "unit",
    },
    "materials": [
        {
            "name": "Plastic granules",
            "amount": 0.30,
            "unit": "kg",
        },
        {
            "name": "Broom bristles",
            "amount": 0.10,
            "unit": "kg",
        },
    ],
    "manufacturing": {
        "electricity": {
            "amount": 0.20,
            "unit": "kWh",
        },
    },
    "transportation": {
        "distance": 100,
        "unit": "km",
        "transport_mode": "truck",
    },
}
