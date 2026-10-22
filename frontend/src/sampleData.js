/**
 * Realistic Pre-configured LCA Product Life Cycle Models
 */

export const SAMPLE_PRODUCTS = [
  {
    product_id: 'plastic_broom_eco',
    product_name: 'Eco Plastic Broom',
    functional_unit_amount: 1.0,
    functional_unit: 'unit',
    processes: [
      {
        process_id: 'broom_materials',
        process_name: 'Raw Material Compounding',
        stage: 'Raw Materials',
        exchanges: [
          { flow_name: 'Plastic granules', exchange_type: 'input', amount: 0.30, unit: 'kg' },
          { flow_name: 'Broom bristles', exchange_type: 'input', amount: 0.10, unit: 'kg' },
        ],
        transportation: [
          { transport_mode: 'truck', distance: 100.0, distance_unit: 'km', transported_mass: 0.40, mass_unit: 'kg' }
        ]
      },
      {
        process_id: 'broom_assembly',
        process_name: 'Broom Molding & Assembly',
        stage: 'Manufacturing',
        exchanges: [
          { flow_name: 'Electricity, grid average', exchange_type: 'input', amount: 0.20, unit: 'kWh' },
          { flow_name: 'Carbon dioxide, fossil', exchange_type: 'output', amount: 0.05, unit: 'kg' },
        ],
        transportation: [
          { transport_mode: 'truck', distance: 50.0, distance_unit: 'km', transported_mass: 0.40, mass_unit: 'kg' }
        ]
      }
    ]
  },
  {
    product_id: 'pet_bottle_500ml',
    product_name: '500ml PET Beverage Bottle',
    functional_unit_amount: 1.0,
    functional_unit: 'bottle',
    processes: [
      {
        process_id: 'preform_injection',
        process_name: 'PET Preform Injection Molding',
        stage: 'Raw Materials & Preform',
        exchanges: [
          { flow_name: 'Plastic granules', exchange_type: 'input', amount: 0.022, unit: 'kg' },
          { flow_name: 'Electricity, grid average', exchange_type: 'input', amount: 0.045, unit: 'kWh' },
          { flow_name: 'Carbon dioxide, fossil', exchange_type: 'output', amount: 0.004, unit: 'kg' }
        ],
        transportation: [
          { transport_mode: 'truck', distance: 200.0, distance_unit: 'km', transported_mass: 0.022, mass_unit: 'kg' }
        ]
      },
      {
        process_id: 'bottle_blow_molding',
        process_name: 'Stretch Blow Molding & Labeling',
        stage: 'Manufacturing',
        exchanges: [
          { flow_name: 'Electricity, grid average', exchange_type: 'input', amount: 0.035, unit: 'kWh' },
          { flow_name: 'Carbon dioxide, fossil', exchange_type: 'output', amount: 0.002, unit: 'kg' }
        ],
        transportation: [
          { transport_mode: 'truck', distance: 80.0, distance_unit: 'km', transported_mass: 0.025, mass_unit: 'kg' }
        ]
      },
      {
        process_id: 'retail_distribution',
        process_name: 'Regional Retail Logistics',
        stage: 'Distribution & Transport',
        exchanges: [],
        transportation: [
          { transport_mode: 'truck', distance: 350.0, distance_unit: 'km', transported_mass: 0.025, mass_unit: 'kg' }
        ]
      }
    ]
  },
  {
    product_id: 'aluminum_can_330ml',
    product_name: '330ml Aluminium Beverage Can',
    functional_unit_amount: 1.0,
    functional_unit: 'can',
    processes: [
      {
        process_id: 'sheet_stamping',
        process_name: 'Aluminium Sheet Cupping & Body Maker',
        stage: 'Manufacturing',
        exchanges: [
          { flow_name: 'Electricity, grid average', exchange_type: 'input', amount: 0.12, unit: 'kWh' },
          { flow_name: 'Carbon dioxide, fossil', exchange_type: 'output', amount: 0.015, unit: 'kg' }
        ],
        transportation: [
          { transport_mode: 'truck', distance: 120.0, distance_unit: 'km', transported_mass: 0.015, mass_unit: 'kg' }
        ]
      },
      {
        process_id: 'distribution',
        process_name: 'Supermarket Transport',
        stage: 'Distribution & Transport',
        exchanges: [],
        transportation: [
          { transport_mode: 'truck', distance: 180.0, distance_unit: 'km', transported_mass: 0.015, mass_unit: 'kg' }
        ]
      }
    ]
  }
]

export const SENIOR_REFINERY_PAYLOAD = {
  product: {
    name: "Diesel, refinery gate",
    functional_unit: "1 kg of diesel"
  },
  allocation: {
    method: "mass"
  },
  inputs: [
    {
      name: "Crude oil",
      key: "crude_oil",
      stage: "raw_material",
      amount: 1.15,
      unit: "kg"
    },
    {
      name: "Process electricity",
      key: "electricity_grid_sa",
      stage: "manufacturing",
      amount: 0.12,
      unit: "kWh"
    },
    {
      name: "Process heat",
      key: "natural_gas_heat",
      stage: "manufacturing",
      amount: 0.8,
      unit: "kWh"
    },
    {
      name: "Hydrogen (hydrotreating)",
      key: "hydrogen_smr",
      stage: "manufacturing",
      amount: 0.02,
      unit: "kg"
    },
    {
      name: "Crude oil transport",
      key: "truck_16t",
      stage: "transport",
      mass: 1.15,
      mass_unit: "kg",
      distance_km: 300
    }
  ],
  outputs: [
    {
      type: "product",
      name: "Diesel",
      amount: 1.0,
      unit: "kg",
      price: 1.0
    },
    {
      type: "co_product",
      name: "Gasoline",
      amount: 0.35,
      unit: "kg",
      price: 1.1
    },
    {
      type: "co_product",
      name: "LPG",
      amount: 0.12,
      unit: "kg",
      price: 0.9
    },
    {
      type: "emission",
      name: "Flue gas CO2",
      flow: "co2",
      amount: 0.22,
      unit: "kg"
    },
    {
      type: "emission",
      name: "Flue gas SO2",
      flow: "so2",
      amount: 0.0004,
      unit: "kg"
    },
    {
      type: "emission",
      name: "Flue gas NOx",
      flow: "nox",
      amount: 0.0007,
      unit: "kg"
    },
    {
      type: "emission",
      name: "Fugitive methane",
      flow: "ch4",
      amount: 0.0009,
      unit: "kg"
    },
    {
      type: "waste",
      name: "Process wastewater",
      key: "wastewater_treatment",
      amount: 0.003,
      unit: "m3"
    },
    {
      type: "waste",
      name: "Spent catalyst",
      key: "hazardous_waste_incineration",
      amount: 0.0008,
      unit: "kg"
    }
  ],
  metadata: {
    product_code: "DSL-001",
    plant: "Refinery A",
    period: "2026-Q3",
    request_ref: "REQ-12345"
  }
}

