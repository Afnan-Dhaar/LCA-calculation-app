import React, { useState, useEffect } from 'react'
import {
  Play,
  TrendingUp,
  AlertTriangle,
  Truck,
  Compass,
  BarChart2,
  Layers,
  Cpu,
  Award,
  RefreshCw,
  Sparkles,
  Box,
  Search,
  Zap,
  Sliders,
  ArrowRight,
  Leaf,
  GitFork,
  CheckCircle2,
} from 'lucide-react'
import { fetchMethods } from '../apiClient'

const STAGE_COLORS = {
  'Raw Materials': '#38BDF8',
  'Materials & Energy (Background)': '#10B981',
  'Manufacturing': '#F59E0B',
  'Packaging': '#A855F7',
  'Distribution & Transport': '#EC4899',
  'Use Phase': '#6366F1',
  'End of Life': '#14B8A6',
}

const PRESET_METHODS = [
  {
    id: 'cml_gwp100_no_lt',
    name: 'CML v4.8 (2016) - Climate Change GWP100',
    tuple: ['CML v4.8 2016 no LT', 'climate change no LT', 'global warming potential (GWP100) no LT'],
    shortName: 'CML v4.8 GWP100',
    sub: 'IPCC Climate Change (100-yr horizon)',
  },
  {
    id: 'ef_v3_climate',
    name: 'EF v3.0 - Climate Change (EU Environmental Footprint)',
    tuple: ['EF v3.0 no LT', 'climate change no LT', 'global warming potential (GWP100) no LT'],
    shortName: 'EF v3.0 Climate',
    sub: 'EU Environmental Footprint Framework',
  },
  {
    id: 'ef_v3_fossil',
    name: 'EF v3.0 - Climate Change (Fossil only)',
    tuple: ['EF v3.0 no LT', 'climate change: fossil no LT', 'global warming potential (GWP100) no LT'],
    shortName: 'EF v3.0 Fossil',
    sub: 'EU Fossil Carbon Emissions',
  },
  {
    id: 'eco_scarcity_climate',
    name: 'Ecological Scarcity 2021 - Climate Change',
    tuple: ['Ecological Scarcity 2021 no LT', 'climate change no LT', 'global warming potential (GWP100) no LT'],
    shortName: 'Ecological Scarcity',
    sub: 'Swiss Federal Office for the Environment (FOEN)',
  },
]

export default function LcaAnalytics({
  result,
  products,
  currentProduct,
  selectedProductId,
  setSelectedProductId,
  onCalculateSaved,
  onCalculateCurrent,
  isCalculating,
}) {
  const [selectedMethodId, setSelectedMethodId] = useState('cml_gwp100_no_lt')
  const [customMethodTuple, setCustomMethodTuple] = useState(null)
  const [isSearchingMethods, setIsSearchingMethods] = useState(false)
  const [methodQuery, setMethodQuery] = useState('')
  const [searchResults, setSearchResults] = useState([])
  const [showSearchModal, setShowSearchModal] = useState(false)

  // Interactive Sensitivity Simulation State
  const [gridRenewablePct, setGridRenewablePct] = useState(0)
  const [logisticsDelta, setLogisticsDelta] = useState(0)
  const [materialEffPct, setMaterialEffPct] = useState(0)
  const [highlightedNode, setHighlightedNode] = useState(null)


  // Current active method tuple
  const getActiveMethodTuple = () => {
    if (selectedMethodId === '__custom__' && customMethodTuple) {
      return customMethodTuple
    }
    const found = PRESET_METHODS.find((m) => m.id === selectedMethodId)
    return found ? found.tuple : PRESET_METHODS[0].tuple
  }

  // Trigger calculation with chosen method
  const handleTriggerCalc = () => {
    const methodTuple = getActiveMethodTuple()
    if (selectedProductId === '__current_builder__') {
      onCalculateCurrent(methodTuple)
    } else if (selectedProductId) {
      onCalculateSaved(selectedProductId, methodTuple)
    } else if (products.length > 0) {
      onCalculateSaved(products[0].product_id, methodTuple)
    } else {
      onCalculateCurrent(methodTuple)
    }
  }

  // Handle Brightway method search
  const handleSearchMethods = async () => {
    if (!methodQuery.trim()) return
    try {
      setIsSearchingMethods(true)
      const res = await fetchMethods(methodQuery.trim(), 20)
      setSearchResults(res)
    } catch (err) {
      console.warn('Could not search methods:', err)
    } finally {
      setIsSearchingMethods(false)
    }
  }

  const handleSelectCustomMethod = (method) => {
    setCustomMethodTuple(method.method_tuple)
    setSelectedMethodId('__custom__')
    setShowSearchModal(false)
  }

  return (
    <div className="lca-analytics-view">
      {/* Top Header & Calculation Controls */}
      <div className="glass-panel" style={{ marginBottom: '1.75rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <h2 style={{ fontSize: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
              <BarChart2 size={24} color="#06B6D4" />
              LCA Calculations & Hotspot Analytics
            </h2>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>
              Multi-method Life Cycle Assessment powered by Brightway 2.5 characterization solver.
            </p>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
            {/* 1. Target Product Selector */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <label className="form-label" style={{ margin: 0 }}>Model:</label>
              <select
                id="select-analytics-product"
                className="form-select"
                value={selectedProductId || '__current_builder__'}
                onChange={(e) => setSelectedProductId(e.target.value)}
                style={{ minWidth: '180px' }}
              >
                <optgroup label="Active in Studio">
                  <option value="__current_builder__">
                    Builder: {currentProduct?.product_name || 'Active Product'}
                  </option>
                </optgroup>
                {products.length > 0 && (
                  <optgroup label="Saved in Storage">
                    {products.map((p) => (
                      <option key={p.product_id} value={p.product_id}>
                        {p.product_name} ({p.product_id})
                      </option>
                    ))}
                  </optgroup>
                )}
              </select>
            </div>

            {/* 2. LCIA Impact Method Selector */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <label className="form-label" style={{ margin: 0 }}>Method:</label>
              <select
                id="select-analytics-method"
                className="form-select"
                value={selectedMethodId}
                onChange={(e) => {
                  if (e.target.value === '__open_search__') {
                    setShowSearchModal(true)
                  } else {
                    setSelectedMethodId(e.target.value)
                  }
                }}
                style={{ minWidth: '220px' }}
              >
                {PRESET_METHODS.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name}
                  </option>
                ))}
                {customMethodTuple && (
                  <option value="__custom__">
                    Custom: {customMethodTuple.slice(-1)[0] || 'Selected Method'}
                  </option>
                )}
                <option value="__open_search__">🔍 Search 760+ Methods...</option>
              </select>
            </div>

            {/* 3. Compute Button */}
            <button
              id="btn-trigger-analytics-calc"
              className="btn btn-primary"
              onClick={handleTriggerCalc}
              disabled={isCalculating}
            >
              {isCalculating ? (
                <>
                  <RefreshCw size={16} className="spin-icon" style={{ animation: 'spin 1s linear infinite' }} />
                  <span>Computing Matrix...</span>
                </>
              ) : (
                <>
                  <Play size={16} fill="currentColor" />
                  <span>Compute Assessment</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Method Search Modal */}
      {showSearchModal && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0,0,0,0.75)', backdropFilter: 'blur(8px)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: '1rem'
        }}>
          <div className="glass-panel" style={{ width: '100%', maxWidth: '650px', background: '#0F172A', border: '1px solid rgba(255,255,255,0.15)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
              <h3 style={{ fontSize: '1.2rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Compass size={20} color="#06B6D4" />
                Select Impact Assessment Method (LCIA)
              </h3>
              <button
                className="btn btn-secondary btn-sm"
                onClick={() => setShowSearchModal(false)}
              >
                ✕ Close
              </button>
            </div>

            <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginBottom: '1rem' }}>
              Search across Brightway's registered 760+ method categories (e.g. <em>climate</em>, <em>water</em>, <em>acidification</em>, <em>ozone</em>, <em>cml</em>, <em>ef</em>):
            </p>

            <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem' }}>
              <input
                type="text"
                className="form-control"
                placeholder="Search methods (e.g. climate, water, toxicity)..."
                value={methodQuery}
                onChange={(e) => setMethodQuery(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSearchMethods()}
              />
              <button
                className="btn btn-primary"
                onClick={handleSearchMethods}
                disabled={isSearchingMethods}
              >
                <Search size={16} />
                <span>Search</span>
              </button>
            </div>

            <div style={{ maxHeight: '300px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {searchResults.length === 0 ? (
                <p style={{ color: 'var(--text-dim)', textAlign: 'center', padding: '1.5rem', fontStyle: 'italic', fontSize: '0.85rem' }}>
                  {isSearchingMethods ? 'Searching Brightway registry...' : 'Type a keyword above and click Search.'}
                </p>
              ) : (
                searchResults.map((m, idx) => (
                  <div
                    key={idx}
                    onClick={() => handleSelectCustomMethod(m)}
                    style={{
                      background: 'rgba(255,255,255,0.03)',
                      border: '1px solid var(--border-subtle)',
                      padding: '0.75rem 1rem',
                      borderRadius: '6px',
                      cursor: 'pointer',
                      fontSize: '0.85rem',
                      transition: 'all 0.2s',
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.borderColor = '#10B981')}
                    onMouseLeave={(e) => (e.currentTarget.style.borderColor = 'var(--border-subtle)')}
                  >
                    <strong>{m.display_name}</strong>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}

      {!result ? (
        <div className="glass-panel" style={{ textAlign: 'center', padding: '4rem 2rem' }}>
          <Compass size={48} color="#06B6D4" style={{ marginBottom: '1rem', opacity: 0.8 }} />
          <h3 style={{ fontSize: '1.35rem', marginBottom: '0.5rem' }}>No Assessment Executed Yet</h3>
          <p style={{ color: 'var(--text-muted)', maxWidth: '520px', margin: '0 auto 1.5rem auto', fontSize: '0.9rem', lineHeight: 1.6 }}>
            Run the Brightway Life Cycle Assessment engine with your chosen impact method on the active model or saved products.
          </p>

          <div style={{ display: 'flex', justifyContent: 'center', gap: '1rem', flexWrap: 'wrap' }}>
            <button
              className="btn btn-primary"
              onClick={() => onCalculateCurrent(getActiveMethodTuple())}
              disabled={isCalculating}
            >
              <Sparkles size={16} />
              <span>Assess Active: {currentProduct?.product_name || 'Current Model'}</span>
            </button>

            {products.length > 0 && (
              <button
                className="btn btn-secondary"
                onClick={() => onCalculateSaved(products[0].product_id, getActiveMethodTuple())}
                disabled={isCalculating}
              >
                <Box size={16} />
                <span>Assess Saved: {products[0].product_name}</span>
              </button>
            )}
          </div>
        </div>
      ) : (
        <div className="analytics-results-container">
          {/* 4 Hero KPI Cards */}
          <div className="kpi-grid">
            <div className="kpi-card" style={{ borderLeft: '4px solid #10B981' }}>
              <div className="kpi-label">
                <span>Total Impact</span>
                <Award size={18} color="#10B981" />
              </div>
              <div className="kpi-value" style={{ color: '#34D399' }}>
                {result.total_score.toFixed(4)}
              </div>
              <div className="kpi-sub">
                {result.method_unit} per {result.functional_unit_amount} {result.functional_unit}
              </div>
            </div>

            <div className="kpi-card" style={{ borderLeft: '4px solid #06B6D4' }}>
              <div className="kpi-label">
                <span>Selected Impact Method</span>
                <Compass size={18} color="#06B6D4" />
              </div>
              <div className="kpi-value" style={{ fontSize: '1.15rem', lineHeight: '1.3' }}>
                {result.method_name.split('/')[0]?.trim() || 'Custom Method'}
              </div>
              <div className="kpi-sub" title={result.method_name} style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {result.method_name}
              </div>
            </div>

            <div className="kpi-card" style={{ borderLeft: '4px solid #F59E0B' }}>
              <div className="kpi-label">
                <span>Freight Logistics</span>
                <Truck size={18} color="#F59E0B" />
              </div>
              <div className="kpi-value" style={{ color: '#FBBF24' }}>
                {result.transport_percentage?.toFixed(1) || 0}%
              </div>
              <div className="kpi-sub">
                {result.transport_score?.toFixed(4) || 0} {result.method_unit} transport footprint
              </div>
            </div>

            <div className="kpi-card" style={{ borderLeft: '4px solid #8B5CF6' }}>
              <div className="kpi-label">
                <span>Life Cycle Stages</span>
                <Layers size={18} color="#8B5CF6" />
              </div>
              <div className="kpi-value" style={{ color: '#C084FC' }}>
                {result.stage_contributions?.length || 0}
              </div>
              <div className="kpi-sub">
                {result.process_contributions?.length || 0} total contributing supply chain nodes
              </div>
            </div>
          </div>

          {/* ISO 14044 Co-Product Allocation Banner (if applicable) */}
          {result.allocation_summary && (
            <div
              className="glass-panel"
              style={{
                marginBottom: '1.75rem',
                borderLeft: '4px solid #F59E0B',
                background: 'rgba(245, 158, 11, 0.05)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.5rem' }}>
                <Sparkles size={18} color="#F59E0B" />
                <h4 style={{ margin: 0, fontSize: '0.95rem', color: '#FCD34D' }}>
                  ISO 14044 Multi-Output Co-Product Allocation ({result.allocation_summary.method?.toUpperCase()} METHOD)
                </h4>
              </div>
              <p style={{ margin: '0 0 0.75rem 0', fontSize: '0.85rem', color: 'var(--text-muted)', lineHeight: 1.5 }}>
                A multi-output system balance was detected. Inputs, emissions, and transport burdens have been allocated using ISO 14044 {result.allocation_summary.method} allocation:
                {' '}
                <strong style={{ color: '#F59E0B' }}>
                  {result.allocation_summary.allocation_percentage}%
                </strong>{' '}
                allocated to target product ({result.product_name}), with the remaining{' '}
                <strong style={{ color: '#93C5FD' }}>
                  {(100 - result.allocation_summary.allocation_percentage).toFixed(2)}%
                </strong>{' '}
                allocated to co-products.
              </p>
              {result.allocation_summary.co_products && result.allocation_summary.co_products.length > 0 && (
                <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                  {result.allocation_summary.co_products.map((cp, idx) => (
                    <span
                      key={idx}
                      className="badge"
                      style={{ background: 'rgba(59, 130, 246, 0.15)', color: '#93C5FD', border: '1px solid rgba(59, 130, 246, 0.3)', padding: '0.25rem 0.6rem' }}
                    >
                      Co-product: {cp.name} ({cp.amount} kg &bull; {cp.share_pct}%)
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Interactive Sensitivity & Scenario Simulation ("What-If" Explorer) */}
          {(() => {
            const baseTotal = result.total_score
            const elecContrib = result.process_contributions?.find((p) =>
              p.process_name?.toLowerCase().includes('electricity')
            )
            const elecScore = elecContrib ? elecContrib.score : baseTotal * 0.12
            const transScore = result.transport_score || 0
            const matContrib = result.stage_contributions?.find((s) =>
              s.stage === 'Raw Materials' || s.stage === 'Materials & Energy (Background)'
            )
            const matScore = matContrib ? Math.max(0, matContrib.score - elecScore) : baseTotal * 0.45

            const elecSavings = elecScore * (gridRenewablePct / 100.0)
            const transDelta = transScore * (logisticsDelta / 100.0)
            const matSavings = matScore * (materialEffPct / 100.0)

            const simulatedTotal = Math.max(0.0001, baseTotal - elecSavings + transDelta - matSavings)
            const delta = simulatedTotal - baseTotal
            const pctDelta = (delta / baseTotal) * 100.0

            return (
              <div className="glass-panel" style={{ marginBottom: '1.75rem', border: '1px solid rgba(16, 185, 129, 0.25)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem', flexWrap: 'wrap', gap: '0.75rem' }}>
                  <div>
                    <h3 style={{ fontSize: '1.15rem', display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#34D399' }}>
                      <Sliders size={20} color="#10B981" />
                      Interactive Sensitivity & Scenario Explorer
                    </h3>
                    <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', margin: '0.2rem 0 0 0' }}>
                      Simulate real-time decarbonization strategies (clean grid, freight reduction, material circularity) without modifying the base model.
                    </p>
                  </div>

                  {(gridRenewablePct > 0 || logisticsDelta !== 0 || materialEffPct > 0) && (
                    <button
                      className="btn btn-secondary btn-sm"
                      onClick={() => {
                        setGridRenewablePct(0)
                        setLogisticsDelta(0)
                        setMaterialEffPct(0)
                      }}
                      style={{ fontSize: '0.8rem' }}
                    >
                      <RefreshCw size={13} />
                      <span>Reset Levers</span>
                    </button>
                  )}
                </div>

                {/* Simulated Impact KPI Bar */}
                <div
                  style={{
                    background: 'rgba(15, 23, 42, 0.7)',
                    borderRadius: 'var(--radius-md)',
                    padding: '1.25rem',
                    border: '1px solid rgba(255, 255, 255, 0.08)',
                    marginBottom: '1.5rem',
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                    gap: '1rem',
                    alignItems: 'center',
                  }}
                >
                  <div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                      Baseline Footprint
                    </div>
                    <div style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--text-main)' }}>
                      {result.total_score.toFixed(4)}{' '}
                      <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{result.method_unit}</span>
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                    <ArrowRight size={22} color="#06B6D4" />
                    <div>
                      <div style={{ fontSize: '0.75rem', color: '#38BDF8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                        Simulated Scenario
                      </div>
                      <div style={{ fontSize: '1.75rem', fontWeight: 900, color: delta < 0 ? '#34D399' : delta > 0 ? '#F43F5E' : '#FFF' }}>
                        {simulatedTotal.toFixed(4)}{' '}
                        <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{result.method_unit}</span>
                      </div>
                    </div>
                  </div>

                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                      Net Decarbonization
                    </div>
                    <div
                      style={{
                        fontSize: '1.4rem',
                        fontWeight: 800,
                        color: delta < 0 ? '#34D399' : delta > 0 ? '#F43F5E' : 'var(--text-dim)',
                      }}
                    >
                      {pctDelta > 0 ? `+${pctDelta.toFixed(1)}%` : `${pctDelta.toFixed(1)}%`}
                    </div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                      {delta < 0 ? `Savings: ${Math.abs(delta).toFixed(4)} ${result.method_unit}` : delta > 0 ? `Increase: +${delta.toFixed(4)} ${result.method_unit}` : 'Neutral baseline'}
                    </div>
                  </div>
                </div>

                {/* 3 Interactive Sliders */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '1.25rem' }}>
                  {/* Slider 1: Clean Energy */}
                  <div style={{ background: 'rgba(255, 255, 255, 0.02)', padding: '1rem', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                      <span style={{ fontSize: '0.85rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                        <Zap size={15} color="#F59E0B" />
                        Renewable Electricity Offset
                      </span>
                      <span style={{ fontWeight: 800, color: '#FCD34D', fontSize: '0.9rem' }}>
                        {gridRenewablePct}%
                      </span>
                    </div>
                    <input
                      type="range"
                      min="0"
                      max="100"
                      step="5"
                      value={gridRenewablePct}
                      onChange={(e) => setGridRenewablePct(Number(e.target.value))}
                      className="slider-control"
                    />
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.72rem', color: 'var(--text-dim)', marginTop: '0.35rem' }}>
                      <span>0% (Grid Default)</span>
                      <span>100% (Solar/Hydro PPA)</span>
                    </div>
                  </div>

                  {/* Slider 2: Logistics Optimization */}
                  <div style={{ background: 'rgba(255, 255, 255, 0.02)', padding: '1rem', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                      <span style={{ fontSize: '0.85rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                        <Truck size={15} color="#06B6D4" />
                        Logistics Distance Delta
                      </span>
                      <span style={{ fontWeight: 800, color: logisticsDelta < 0 ? '#34D399' : logisticsDelta > 0 ? '#F87171' : '#FFF', fontSize: '0.9rem' }}>
                        {logisticsDelta > 0 ? `+${logisticsDelta}%` : `${logisticsDelta}%`}
                      </span>
                    </div>
                    <input
                      type="range"
                      min="-80"
                      max="100"
                      step="10"
                      value={logisticsDelta}
                      onChange={(e) => setLogisticsDelta(Number(e.target.value))}
                      className="slider-control"
                    />
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.72rem', color: 'var(--text-dim)', marginTop: '0.35rem' }}>
                      <span>-80% (Local Sourcing)</span>
                      <span>+100% (Global Reach)</span>
                    </div>
                  </div>

                  {/* Slider 3: Material Circularity */}
                  <div style={{ background: 'rgba(255, 255, 255, 0.02)', padding: '1rem', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                      <span style={{ fontSize: '0.85rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                        <Leaf size={15} color="#10B981" />
                        Material Lightweighting
                      </span>
                      <span style={{ fontWeight: 800, color: '#34D399', fontSize: '0.9rem' }}>
                        {materialEffPct}%
                      </span>
                    </div>
                    <input
                      type="range"
                      min="0"
                      max="50"
                      step="5"
                      value={materialEffPct}
                      onChange={(e) => setMaterialEffPct(Number(e.target.value))}
                      className="slider-control"
                    />
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.72rem', color: 'var(--text-dim)', marginTop: '0.35rem' }}>
                      <span>0% (Virgin Default)</span>
                      <span>50% (Eco-Design / Recycled)</span>
                    </div>
                  </div>
                </div>
              </div>
            )
          })()}

          {/* Interactive Supply Chain Flow Diagram (Sankey-style Pipeline) */}
          <div className="glass-panel" style={{ marginBottom: '1.75rem' }}>
            <h3 style={{ fontSize: '1.1rem', marginBottom: '0.3rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <GitFork size={20} color="#06B6D4" />
              Supply Chain Lifecycle Flow Map
            </h3>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginBottom: '1rem' }}>
              Interactive cradle-to-grave pipeline tracing resources, transformations, and logistics into the functional unit.
            </p>

            <div className="supply-chain-flow">
              <div className="flow-step-box" style={{ borderTop: '3px solid #38BDF8' }}>
                <div style={{ fontSize: '0.75rem', color: '#38BDF8', fontWeight: 700, textTransform: 'uppercase' }}>Stage 1</div>
                <div style={{ fontWeight: 700, fontSize: '0.9rem', marginTop: '0.2rem' }}>Raw Feedstocks</div>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-dim)', marginTop: '0.4rem' }}>Upstream Extraction</div>
                <div style={{ fontWeight: 800, color: '#FFF', fontSize: '0.95rem', marginTop: '0.5rem' }}>
                  {result.stage_contributions?.find(s => s.stage === 'Raw Materials' || s.stage === 'Materials & Energy (Background)')?.percentage.toFixed(1) || '0'}%
                </div>
              </div>

              <div className="flow-arrow"><ArrowRight size={20} /></div>

              <div className="flow-step-box" style={{ borderTop: '3px solid #F59E0B' }}>
                <div style={{ fontSize: '0.75rem', color: '#F59E0B', fontWeight: 700, textTransform: 'uppercase' }}>Stage 2</div>
                <div style={{ fontWeight: 700, fontSize: '0.9rem', marginTop: '0.2rem' }}>Process Energy</div>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-dim)', marginTop: '0.4rem' }}>Power & Grid Heat</div>
                <div style={{ fontWeight: 800, color: '#FFF', fontSize: '0.95rem', marginTop: '0.5rem' }}>
                  {result.process_contributions?.find(p => p.process_name?.toLowerCase().includes('electricity'))?.percentage.toFixed(1) || '9.5'}%
                </div>
              </div>

              <div className="flow-arrow"><ArrowRight size={20} /></div>

              <div className="flow-step-box" style={{ borderTop: '3px solid #FBBF24' }}>
                <div style={{ fontSize: '0.75rem', color: '#FBBF24', fontWeight: 700, textTransform: 'uppercase' }}>Stage 3</div>
                <div style={{ fontWeight: 700, fontSize: '0.9rem', marginTop: '0.2rem' }}>Freight Logistics</div>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-dim)', marginTop: '0.4rem' }}>Road & Rail Network</div>
                <div style={{ fontWeight: 800, color: '#FFF', fontSize: '0.95rem', marginTop: '0.5rem' }}>
                  {result.transport_percentage?.toFixed(1) || 0}%
                </div>
              </div>

              <div className="flow-arrow"><ArrowRight size={20} /></div>

              <div className="flow-step-box" style={{ borderTop: '3px solid #10B981', background: 'rgba(16, 185, 129, 0.08)' }}>
                <div style={{ fontSize: '0.75rem', color: '#10B981', fontWeight: 700, textTransform: 'uppercase' }}>Final Product</div>
                <div style={{ fontWeight: 700, fontSize: '0.9rem', marginTop: '0.2rem' }}>{result.product_name}</div>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-dim)', marginTop: '0.4rem' }}>1.0 {result.functional_unit}</div>
                <div style={{ fontWeight: 800, color: '#34D399', fontSize: '0.95rem', marginTop: '0.5rem' }}>
                  {result.total_score.toFixed(4)} {result.method_unit}
                </div>
              </div>
            </div>
          </div>


          {/* 1. Stage Contribution Visual Breakdown */}
          <div className="glass-panel" style={{ marginBottom: '1.75rem' }}>
            <h3 style={{ fontSize: '1.1rem', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Layers size={20} color="#10B981" />
              Cradle-to-Grave Stage Breakdown ({result.product_name})
            </h3>

            {/* Stacked bar visualization */}
            <div style={{ height: '24px', display: 'flex', borderRadius: '8px', overflow: 'hidden', marginBottom: '1.25rem', border: '1px solid var(--border-subtle)' }}>
              {result.stage_contributions.map((s, idx) => {
                const color = STAGE_COLORS[s.stage] || '#8B5CF6'
                const pct = Math.max(s.percentage, 1.5) // minimum width for visibility
                return (
                  <div
                    key={idx}
                    title={`${s.stage}: ${s.score.toFixed(4)} ${s.unit} (${s.percentage.toFixed(1)}%)`}
                    style={{
                      width: `${pct}%`,
                      backgroundColor: color,
                      transition: 'width 0.5s ease',
                    }}
                  />
                )
              })}
            </div>

            {/* Stage Cards Grid */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem' }}>
              {result.stage_contributions.map((s, idx) => {
                const color = STAGE_COLORS[s.stage] || '#8B5CF6'
                return (
                  <div
                    key={idx}
                    style={{
                      background: 'rgba(15, 23, 42, 0.5)',
                      padding: '1rem',
                      borderRadius: '8px',
                      border: '1px solid var(--border-subtle)',
                      borderTop: `3px solid ${color}`,
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.4rem' }}>
                      <span style={{ fontWeight: 600, fontSize: '0.85rem' }}>{s.stage}</span>
                      <span className="badge" style={{ backgroundColor: `${color}25`, color: color }}>
                        {s.percentage.toFixed(1)}%
                      </span>
                    </div>
                    <div style={{ fontSize: '1.25rem', fontWeight: 800 }}>
                      {s.score.toFixed(4)} <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{s.unit}</span>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>

          {/* 2. Process Hotspot Rankings */}
          <div className="glass-panel" style={{ marginBottom: '1.75rem' }}>
            <h3 style={{ fontSize: '1.1rem', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <TrendingUp size={20} color="#F59E0B" />
              Supply Chain Hotspot Rankings (Top Contributors)
            </h3>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {result.process_contributions.map((p, idx) => (
                <div
                  key={idx}
                  style={{
                    background: 'rgba(15, 23, 42, 0.4)',
                    padding: '1rem',
                    borderRadius: '8px',
                    border: '1px solid var(--border-subtle)',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.4rem' }}>
                    <div>
                      <span style={{ fontWeight: 700, fontSize: '0.925rem' }}>#{idx + 1} {p.process_name}</span>
                      <span style={{ color: 'var(--text-dim)', fontSize: '0.775rem', marginLeft: '0.6rem' }}>
                        [{p.stage}]
                      </span>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <span style={{ fontWeight: 800, fontSize: '1rem', color: '#FFF' }}>
                        {p.score.toFixed(4)} {p.unit}
                      </span>
                      <span style={{ fontWeight: 700, color: '#38BDF8', marginLeft: '0.5rem', fontSize: '0.875rem' }}>
                        ({p.percentage.toFixed(1)}%)
                      </span>
                    </div>
                  </div>

                  <div className="progress-track">
                    <div
                      className="progress-fill"
                      style={{
                        width: `${Math.min(p.percentage, 100)}%`,
                        background: idx === 0 ? 'linear-gradient(90deg, #F59E0B, #EF4444)' : 'linear-gradient(90deg, #10B981, #06B6D4)',
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* 3. Elementary Biosphere Emissions Table */}
          {result.flow_contributions?.length > 0 && (
            <div className="glass-panel" style={{ marginBottom: '1.75rem' }}>
              <h3 style={{ fontSize: '1.1rem', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Cpu size={20} color="#38BDF8" />
                Elementary Biosphere Flows & Emissions
              </h3>

              <div className="data-table-container">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Biosphere Flow</th>
                      <th>Compartment</th>
                      <th>Inventory Mass</th>
                      <th>Characterized Impact</th>
                      <th>Share (%)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.flow_contributions.map((f, idx) => (
                      <tr key={idx}>
                        <td style={{ fontWeight: 600 }}>{f.flow_name}</td>
                        <td><span className="badge badge-cyan">{f.category}</span></td>
                        <td>{f.amount.toFixed(5)} {f.unit}</td>
                        <td style={{ fontWeight: 700, color: '#34D399' }}>{f.score.toFixed(5)} {result.method_unit}</td>
                        <td style={{ fontWeight: 600 }}>{f.percentage.toFixed(1)}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* 4. Transportation Logistics Table */}
          {result.transport_contributions?.length > 0 && (
            <div className="glass-panel">
              <h3 style={{ fontSize: '1.1rem', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Truck size={20} color="#FBBF24" />
                Freight Transportation Logistics Breakdown
              </h3>

              <div className="data-table-container">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Life Cycle Stage</th>
                      <th>Mode</th>
                      <th>Distance</th>
                      <th>Payload Weight</th>
                      <th>Work (t·km)</th>
                      <th>Emissions Score</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.transport_contributions.map((t, idx) => (
                      <tr key={idx}>
                        <td style={{ fontWeight: 600 }}>{t.process_name}</td>
                        <td><span className="badge badge-amber">{t.mode.toUpperCase()}</span></td>
                        <td>{t.distance_km} km</td>
                        <td>{t.mass_kg} kg</td>
                        <td>{t.tkm.toFixed(4)} t·km</td>
                        <td style={{ fontWeight: 700, color: '#FBBF24' }}>{t.score.toFixed(5)} {result.method_unit}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Warnings */}
          {result.warnings?.length > 0 && (
            <div className="glass-panel" style={{ marginTop: '1.75rem', borderColor: 'rgba(245, 158, 11, 0.4)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#FBBF24', marginBottom: '0.5rem' }}>
                <AlertTriangle size={18} />
                <h4 style={{ fontSize: '0.9rem' }}>Calculation Warnings & Fallbacks</h4>
              </div>
              <ul style={{ paddingLeft: '1.25rem', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                {result.warnings.map((w, idx) => (
                  <li key={idx}>{w}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
