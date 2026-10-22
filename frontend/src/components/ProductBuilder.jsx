import React from 'react'
import { Plus, Trash2, Save, Play, RefreshCw, Sparkles, Truck, Flame, Box, ShieldCheck } from 'lucide-react'
import { SAMPLE_PRODUCTS } from '../sampleData'

const STAGE_OPTIONS = [
  'Raw Materials',
  'Manufacturing',
  'Packaging',
  'Distribution & Transport',
  'Use Phase',
  'End of Life',
]

const INPUT_FLOW_PRESETS = [
  { name: 'Plastic granules', unit: 'kg' },
  { name: 'Electricity, grid average', unit: 'kWh' },
  { name: 'Solar electricity', unit: 'kWh' },
  { name: 'Steel, unalloyed', unit: 'kg' },
  { name: 'Aluminium, primary', unit: 'kg' },
  { name: 'Natural gas, burned in furnace', unit: 'MJ' },
  { name: 'Water, decarbonised', unit: 'm3' },
  { name: 'Cardboard packaging', unit: 'kg' },
]

const EMISSION_FLOW_PRESETS = [
  { name: 'Carbon dioxide, fossil', unit: 'kg' },
  { name: 'Methane, fossil', unit: 'kg' },
  { name: 'Nitrous oxide', unit: 'kg' },
  { name: 'Nitrogen oxides', unit: 'kg' },
  { name: 'Sulfur dioxide', unit: 'kg' },
]

export default function ProductBuilder({ product, setProduct, onSave, onCalculate, isSaving, isCalculating }) {
  // Update top-level product property
  const handleProductChange = (field, value) => {
    setProduct((prev) => ({ ...prev, [field]: value }))
  }

  // Load a preset example
  const handleLoadPreset = (e) => {
    const selectedId = e.target.value
    if (!selectedId) return
    const found = SAMPLE_PRODUCTS.find((p) => p.product_id === selectedId)
    if (found) {
      setProduct(JSON.parse(JSON.stringify(found)))
    }
  }

  // Add process stage
  const handleAddProcess = () => {
    const nextIdx = product.processes.length + 1
    const newProc = {
      process_id: `process_${nextIdx}`,
      process_name: `Stage ${nextIdx} Process`,
      stage: 'Manufacturing',
      exchanges: [
        { flow_name: 'Electricity, grid average', exchange_type: 'input', amount: 0.1, unit: 'kWh' }
      ],
      transportation: [
        { transport_mode: 'truck', distance: 50.0, distance_unit: 'km', transported_mass: 0.1, mass_unit: 'kg' }
      ]
    }
    setProduct((prev) => ({
      ...prev,
      processes: [...prev.processes, newProc]
    }))
  }

  // Remove process stage
  const handleRemoveProcess = (procIndex) => {
    if (product.processes.length <= 1) {
      alert('A product must contain at least 1 process stage.')
      return
    }
    setProduct((prev) => ({
      ...prev,
      processes: prev.processes.filter((_, i) => i !== procIndex)
    }))
  }

  // Update process fields
  const handleProcessChange = (procIndex, field, value) => {
    setProduct((prev) => {
      const nextProcesses = [...prev.processes]
      nextProcesses[procIndex] = { ...nextProcesses[procIndex], [field]: value }
      return { ...prev, processes: nextProcesses }
    })
  }

  // Add Exchange
  const handleAddExchange = (procIndex, type) => {
    const defaultFlow = type === 'input' ? INPUT_FLOW_PRESETS[0] : EMISSION_FLOW_PRESETS[0]
    setProduct((prev) => {
      const nextProcesses = [...prev.processes]
      const proc = { ...nextProcesses[procIndex] }
      proc.exchanges = [
        ...proc.exchanges,
        {
          flow_name: defaultFlow.name,
          exchange_type: type,
          amount: 1.0,
          unit: defaultFlow.unit
        }
      ]
      nextProcesses[procIndex] = proc
      return { ...prev, processes: nextProcesses }
    })
  }

  // Update Exchange
  const handleExchangeChange = (procIndex, exIndex, field, value) => {
    setProduct((prev) => {
      const nextProcesses = [...prev.processes]
      const proc = { ...nextProcesses[procIndex] }
      const nextExchanges = [...proc.exchanges]
      nextExchanges[exIndex] = { ...nextExchanges[exIndex], [field]: value }
      proc.exchanges = nextExchanges
      nextProcesses[procIndex] = proc
      return { ...prev, processes: nextProcesses }
    })
  }

  // Delete Exchange
  const handleDeleteExchange = (procIndex, exIndex) => {
    setProduct((prev) => {
      const nextProcesses = [...prev.processes]
      const proc = { ...nextProcesses[procIndex] }
      proc.exchanges = proc.exchanges.filter((_, i) => i !== exIndex)
      nextProcesses[procIndex] = proc
      return { ...prev, processes: nextProcesses }
    })
  }

  // Add Transportation
  const handleAddTransport = (procIndex) => {
    setProduct((prev) => {
      const nextProcesses = [...prev.processes]
      const proc = { ...nextProcesses[procIndex] }
      proc.transportation = [
        ...(proc.transportation || []),
        {
          transport_mode: 'truck',
          distance: 100.0,
          distance_unit: 'km',
          transported_mass: 1.0,
          mass_unit: 'kg'
        }
      ]
      nextProcesses[procIndex] = proc
      return { ...prev, processes: nextProcesses }
    })
  }

  // Update Transportation
  const handleTransportChange = (procIndex, trIndex, field, value) => {
    setProduct((prev) => {
      const nextProcesses = [...prev.processes]
      const proc = { ...nextProcesses[procIndex] }
      const nextTransport = [...(proc.transportation || [])]
      nextTransport[trIndex] = { ...nextTransport[trIndex], [field]: value }
      proc.transportation = nextTransport
      nextProcesses[procIndex] = proc
      return { ...prev, processes: nextProcesses }
    })
  }

  // Delete Transportation
  const handleDeleteTransport = (procIndex, trIndex) => {
    setProduct((prev) => {
      const nextProcesses = [...prev.processes]
      const proc = { ...nextProcesses[procIndex] }
      proc.transportation = proc.transportation.filter((_, i) => i !== trIndex)
      nextProcesses[procIndex] = proc
      return { ...prev, processes: nextProcesses }
    })
  }

  return (
    <div className="product-builder-view">
      {/* Top Action Bar */}
      <div className="glass-panel" style={{ marginBottom: '1.75rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem', marginBottom: '1.25rem' }}>
          <div>
            <h2 style={{ fontSize: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
              <Box size={24} color="#10B981" />
              Life Cycle Product Studio
            </h2>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>
              Define cradle-to-grave stages, input materials, energy, direct emissions, and transportation.
            </p>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
            <select
              className="form-select"
              id="select-sample-preset"
              onChange={handleLoadPreset}
              defaultValue=""
              style={{ minWidth: '190px' }}
            >
              <option value="" disabled>Load Example Model...</option>
              {SAMPLE_PRODUCTS.map((sp) => (
                <option key={sp.product_id} value={sp.product_id}>
                  {sp.product_name}
                </option>
              ))}
            </select>

            <button
              id="btn-save-product"
              className="btn btn-secondary"
              onClick={onSave}
              disabled={isSaving}
            >
              <Save size={16} />
              <span>{isSaving ? 'Saving...' : 'Save to Disk'}</span>
            </button>

            <button
              id="btn-run-lca-direct"
              className="btn btn-primary"
              onClick={onCalculate}
              disabled={isCalculating}
            >
              <Play size={16} fill="currentColor" />
              <span>{isCalculating ? 'Computing Matrix...' : 'Run LCA Calculation'}</span>
            </button>
          </div>
        </div>

        {/* Product Basic Fields */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem' }}>
          <div className="form-group">
            <label className="form-label">Product ID / Code</label>
            <input
              type="text"
              id="input-product-id"
              className="form-control"
              value={product.product_id}
              onChange={(e) => handleProductChange('product_id', e.target.value)}
              placeholder="e.g. pet_bottle_500ml"
            />
          </div>

          <div className="form-group">
            <label className="form-label">Product Display Name</label>
            <input
              type="text"
              id="input-product-name"
              className="form-control"
              value={product.product_name}
              onChange={(e) => handleProductChange('product_name', e.target.value)}
              placeholder="e.g. 500ml PET Beverage Bottle"
            />
          </div>

          <div className="form-group">
            <label className="form-label">Functional Unit Amount</label>
            <input
              type="number"
              step="any"
              id="input-functional-unit-amount"
              className="form-control"
              value={product.functional_unit_amount}
              onChange={(e) => handleProductChange('functional_unit_amount', parseFloat(e.target.value) || 1.0)}
            />
          </div>

          <div className="form-group">
            <label className="form-label">Reference Unit</label>
            <input
              type="text"
              id="input-functional-unit"
              className="form-control"
              value={product.functional_unit}
              onChange={(e) => handleProductChange('functional_unit', e.target.value)}
              placeholder="e.g. unit, bottle, kg"
            />
          </div>
        </div>
      </div>

      {/* Processes & Life Cycle Stages */}
      <div className="processes-list" style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
        {product.processes.map((proc, pIdx) => {
          const inputs = proc.exchanges.filter((ex) => ex.exchange_type === 'input')
          const emissions = proc.exchanges.filter((ex) => ex.exchange_type === 'output')
          const transport = proc.transportation || []

          return (
            <div key={proc.process_id || pIdx} className="glass-panel" style={{ borderLeft: '4px solid #10B981' }}>
              {/* Process Card Header */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem', flexWrap: 'wrap', gap: '0.75rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                  <span className="badge badge-emerald">Stage {pIdx + 1}</span>
                  <input
                    type="text"
                    className="form-control"
                    style={{ fontWeight: 700, fontSize: '1.1rem', width: '280px', background: 'rgba(0,0,0,0.3)' }}
                    value={proc.process_name}
                    onChange={(e) => handleProcessChange(pIdx, 'process_name', e.target.value)}
                  />
                  <input
                    type="text"
                    className="form-control"
                    style={{ fontSize: '0.85rem', width: '180px', color: 'var(--text-muted)' }}
                    value={proc.process_id}
                    onChange={(e) => handleProcessChange(pIdx, 'process_id', e.target.value)}
                    placeholder="process_id"
                  />
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                  <select
                    className="form-select"
                    value={proc.stage}
                    onChange={(e) => handleProcessChange(pIdx, 'stage', e.target.value)}
                  >
                    {STAGE_OPTIONS.map((stg) => (
                      <option key={stg} value={stg}>{stg}</option>
                    ))}
                  </select>

                  <button
                    className="btn btn-danger btn-sm"
                    onClick={() => handleRemoveProcess(pIdx)}
                    title="Delete Process Stage"
                  >
                    <Trash2 size={15} />
                  </button>
                </div>
              </div>

              {/* 1. Material & Energy Inputs */}
              <div style={{ marginBottom: '1.25rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                  <h4 style={{ fontSize: '0.9rem', color: '#38BDF8', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                    <Box size={16} />
                    Material & Energy Inputs ({inputs.length})
                  </h4>
                  <button
                    className="btn btn-secondary btn-sm"
                    onClick={() => handleAddExchange(pIdx, 'input')}
                  >
                    <Plus size={14} /> Add Input
                  </button>
                </div>

                {inputs.length === 0 ? (
                  <p style={{ color: 'var(--text-dim)', fontSize: '0.8rem', fontStyle: 'italic' }}>
                    No material or energy inputs added to this stage.
                  </p>
                ) : (
                  <div className="data-table-container">
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Flow / Material Name</th>
                          <th style={{ width: '130px' }}>Amount</th>
                          <th style={{ width: '100px' }}>Unit</th>
                          <th style={{ width: '60px' }}></th>
                        </tr>
                      </thead>
                      <tbody>
                        {proc.exchanges.map((ex, exIdx) => {
                          if (ex.exchange_type !== 'input') return null
                          return (
                            <tr key={exIdx}>
                              <td>
                                <input
                                  type="text"
                                  list={`presets-inputs-${pIdx}`}
                                  className="form-control"
                                  value={ex.flow_name}
                                  onChange={(e) => handleExchangeChange(pIdx, exIdx, 'flow_name', e.target.value)}
                                  placeholder="e.g. Plastic granules, Electricity, grid average"
                                />
                                <datalist id={`presets-inputs-${pIdx}`}>
                                  {INPUT_FLOW_PRESETS.map((p) => (
                                    <option key={p.name} value={p.name} />
                                  ))}
                                </datalist>
                              </td>
                              <td>
                                <input
                                  type="number"
                                  step="any"
                                  className="form-control"
                                  value={ex.amount}
                                  onChange={(e) => handleExchangeChange(pIdx, exIdx, 'amount', parseFloat(e.target.value) || 0)}
                                />
                              </td>
                              <td>
                                <input
                                  type="text"
                                  className="form-control"
                                  value={ex.unit}
                                  onChange={(e) => handleExchangeChange(pIdx, exIdx, 'unit', e.target.value)}
                                />
                              </td>
                              <td>
                                <button
                                  className="btn btn-danger btn-sm"
                                  onClick={() => handleDeleteExchange(pIdx, exIdx)}
                                >
                                  <Trash2 size={13} />
                                </button>
                              </td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>

              {/* 2. Direct Process Emissions */}
              <div style={{ marginBottom: '1.25rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                  <h4 style={{ fontSize: '0.9rem', color: '#FB7185', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                    <Flame size={16} />
                    Direct Process Emissions ({emissions.length})
                  </h4>
                  <button
                    className="btn btn-secondary btn-sm"
                    onClick={() => handleAddExchange(pIdx, 'output')}
                  >
                    <Plus size={14} /> Add Direct Emission
                  </button>
                </div>

                {emissions.length === 0 ? (
                  <p style={{ color: 'var(--text-dim)', fontSize: '0.8rem', fontStyle: 'italic' }}>
                    No direct elementary emissions recorded (e.g. direct chimney stack emissions).
                  </p>
                ) : (
                  <div className="data-table-container">
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Elementary Emission Flow</th>
                          <th style={{ width: '130px' }}>Amount</th>
                          <th style={{ width: '100px' }}>Unit</th>
                          <th style={{ width: '60px' }}></th>
                        </tr>
                      </thead>
                      <tbody>
                        {proc.exchanges.map((ex, exIdx) => {
                          if (ex.exchange_type !== 'output') return null
                          return (
                            <tr key={exIdx}>
                              <td>
                                <input
                                  type="text"
                                  list={`presets-emissions-${pIdx}`}
                                  className="form-control"
                                  value={ex.flow_name}
                                  onChange={(e) => handleExchangeChange(pIdx, exIdx, 'flow_name', e.target.value)}
                                  placeholder="e.g. Carbon dioxide, fossil"
                                />
                                <datalist id={`presets-emissions-${pIdx}`}>
                                  {EMISSION_FLOW_PRESETS.map((p) => (
                                    <option key={p.name} value={p.name} />
                                  ))}
                                </datalist>
                              </td>
                              <td>
                                <input
                                  type="number"
                                  step="any"
                                  className="form-control"
                                  value={ex.amount}
                                  onChange={(e) => handleExchangeChange(pIdx, exIdx, 'amount', parseFloat(e.target.value) || 0)}
                                />
                              </td>
                              <td>
                                <input
                                  type="text"
                                  className="form-control"
                                  value={ex.unit}
                                  onChange={(e) => handleExchangeChange(pIdx, exIdx, 'unit', e.target.value)}
                                />
                              </td>
                              <td>
                                <button
                                  className="btn btn-danger btn-sm"
                                  onClick={() => handleDeleteExchange(pIdx, exIdx)}
                                >
                                  <Trash2 size={13} />
                                </button>
                              </td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>

              {/* 3. Freight Transportation */}
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                  <h4 style={{ fontSize: '0.9rem', color: '#FBBF24', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                    <Truck size={16} />
                    Freight Transportation Legs ({transport.length})
                  </h4>
                  <button
                    className="btn btn-secondary btn-sm"
                    onClick={() => handleAddTransport(pIdx)}
                  >
                    <Plus size={14} /> Add Transport Leg
                  </button>
                </div>

                {transport.length === 0 ? (
                  <p style={{ color: 'var(--text-dim)', fontSize: '0.8rem', fontStyle: 'italic' }}>
                    No transportation associated with this process stage.
                  </p>
                ) : (
                  <div className="data-table-container">
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Transport Mode</th>
                          <th style={{ width: '130px' }}>Distance (km)</th>
                          <th style={{ width: '130px' }}>Cargo Mass (kg)</th>
                          <th style={{ width: '60px' }}></th>
                        </tr>
                      </thead>
                      <tbody>
                        {transport.map((tr, trIdx) => (
                          <tr key={trIdx}>
                            <td>
                              <select
                                className="form-select"
                                value={tr.transport_mode}
                                onChange={(e) => handleTransportChange(pIdx, trIdx, 'transport_mode', e.target.value)}
                              >
                                <option value="truck">Truck / Lorry (Road)</option>
                                <option value="train">Freight Train (Rail)</option>
                                <option value="ship">Cargo Container Ship (Sea)</option>
                                <option value="air">Air Freight (Airplane)</option>
                              </select>
                            </td>
                            <td>
                              <input
                                type="number"
                                step="any"
                                className="form-control"
                                value={tr.distance}
                                onChange={(e) => handleTransportChange(pIdx, trIdx, 'distance', parseFloat(e.target.value) || 0)}
                              />
                            </td>
                            <td>
                              <input
                                type="number"
                                step="any"
                                className="form-control"
                                value={tr.transported_mass || 1.0}
                                onChange={(e) => handleTransportChange(pIdx, trIdx, 'transported_mass', parseFloat(e.target.value) || 0)}
                              />
                            </td>
                            <td>
                              <button
                                className="btn btn-danger btn-sm"
                                onClick={() => handleDeleteTransport(pIdx, trIdx)}
                              >
                                <Trash2 size={13} />
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </div>
          )
        })}

        {/* Add Stage CTA */}
        <div style={{ textAlign: 'center', padding: '1rem' }}>
          <button
            id="btn-add-process-stage"
            className="btn btn-outline-emerald"
            onClick={handleAddProcess}
            style={{ padding: '0.85rem 2rem' }}
          >
            <Plus size={18} />
            <span>Add Life Cycle Stage</span>
          </button>
        </div>
      </div>
    </div>
  )
}
