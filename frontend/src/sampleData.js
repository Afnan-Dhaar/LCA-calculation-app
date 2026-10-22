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
