import React, { useState, useEffect } from 'react'
import {
  History,
  Database,
  BarChart3,
  Clock,
  RefreshCw,
  Award,
  Truck,
  Layers,
  Filter,
  Eye,
  Copy,
  CheckCircle2,
  Fingerprint,
  Search,
} from 'lucide-react'
import { fetchHistory, fetchDatabaseStatus, fetchRuns, fetchDatabaseVersion } from '../apiClient'

export default function LcaHistory({ onSelectRun }) {
  const [activeSource, setActiveSource] = useState('v1_runs') // 'v1_runs' | 'product_runs'
  const [v1Runs, setV1Runs] = useState([])
  const [productRuns, setProductRuns] = useState([])
  const [dbStatus, setDbStatus] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [searchFilter, setSearchFilter] = useState('')
  const [selectedRunModal, setSelectedRunModal] = useState(null)
  const [copied, setCopied] = useState(false)

  const loadHistoryData = async () => {
    try {
      setIsLoading(true)
      const [v1, p, s] = await Promise.all([
        fetchRuns(100).catch(() => []),
        fetchHistory(null, 100).catch(() => []),
        fetchDatabaseVersion().catch(() => ({})),
      ])
      setV1Runs(v1)
      setProductRuns(p)
      setDbStatus(s)
    } catch (err) {
      console.warn('Could not load history:', err)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    loadHistoryData()
  }, [])

  // Filter runs based on search keyword
  const filteredV1Runs = v1Runs.filter((r) => {
    if (!searchFilter) return true
    const q = searchFilter.toLowerCase()
    return (
      r.product_name?.toLowerCase().includes(q) ||
      r.run_id?.toLowerCase().includes(q) ||
      r.metadata_info?.matrix_hash?.toLowerCase().includes(q)
    )
  })

  const filteredProductRuns = productRuns.filter((r) => {
    if (!searchFilter) return true
    const q = searchFilter.toLowerCase()
    return (
      r.product_name?.toLowerCase().includes(q) ||
      r.method_name?.toLowerCase().includes(q)
    )
  })

  // Copy JSON payload
  const handleCopyJson = (data) => {
    navigator.clipboard.writeText(JSON.stringify(data, null, 2))
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="lca-history-view">
      {/* Top Header */}
      <div className="glass-panel" style={{ marginBottom: '1.75rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <h2 style={{ fontSize: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
              <History size={24} color="#8B5CF6" />
              LCA Audit Trail & Historical Database
            </h2>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>
              Permanent record of Brightway calculation runs stored in PostgreSQL <code style={{ color: '#38BDF8' }}>lca_run</code> with deterministic SHA-256 matrix fingerprints.
            </p>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
            {/* Matrix Fingerprint Pill */}
            {dbStatus?.matrix_hash && (
              <div
                className="badge"
                style={{
                  padding: '0.5rem 0.85rem',
                  fontSize: '0.8rem',
                  background: 'rgba(6, 182, 212, 0.15)',
                  color: '#38BDF8',
                  border: '1px solid rgba(6, 182, 212, 0.3)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.4rem',
                }}
                title="Deterministic SHA-256 fingerprint representing active background database"
              >
                <Fingerprint size={15} />
                <span>Matrix: {dbStatus.matrix_hash}</span>
              </div>
            )}

            {/* Database Engine Badge */}
            <div
              className="badge"
              style={{
                padding: '0.5rem 0.85rem',
                fontSize: '0.8rem',
                background: dbStatus?.is_postgresql ? 'rgba(16, 185, 129, 0.15)' : 'rgba(139, 92, 246, 0.15)',
                color: dbStatus?.is_postgresql ? '#34D399' : '#C084FC',
                border: `1px solid ${dbStatus?.is_postgresql ? 'rgba(16, 185, 129, 0.3)' : 'rgba(139, 92, 246, 0.3)'}`,
              }}
            >
              <Database size={15} />
              <span>Engine: {dbStatus?.active_database?.toUpperCase() || 'POSTGRESQL'} ({v1Runs.length} Runs)</span>
            </div>

            <button
              id="btn-refresh-history"
              className="btn btn-secondary btn-sm"
              onClick={loadHistoryData}
              disabled={isLoading}
            >
              <RefreshCw size={14} className={isLoading ? 'spin-icon' : ''} style={isLoading ? { animation: 'spin 1s linear infinite' } : {}} />
              <span>Refresh</span>
            </button>
          </div>
        </div>
      </div>

      {/* View Source Selector & Search Filter */}
      <div className="glass-panel" style={{ marginBottom: '1.5rem', padding: '1rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button
              className={`btn btn-sm ${activeSource === 'v1_runs' ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => setActiveSource('v1_runs')}
            >
              <Database size={14} />
              <span>PostgreSQL Runs ({v1Runs.length})</span>
            </button>
            <button
              className={`btn btn-sm ${activeSource === 'product_runs' ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => setActiveSource('product_runs')}
            >
              <Layers size={14} />
              <span>Product Model Runs ({productRuns.length})</span>
            </button>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', minWidth: '260px' }}>
            <Search size={16} color="var(--text-dim)" />
            <input
              type="text"
              className="form-control"
              placeholder="Filter by product name, run ID, or hash..."
              value={searchFilter}
              onChange={(e) => setSearchFilter(e.target.value)}
              style={{ fontSize: '0.85rem' }}
            />
          </div>
        </div>
      </div>

      {/* Audit Log Table */}
      <div className="glass-panel">
        {activeSource === 'v1_runs' && (
          filteredV1Runs.length === 0 ? (
            <p style={{ color: 'var(--text-dim)', textAlign: 'center', padding: '3rem 1rem', fontStyle: 'italic' }}>
              No PostgreSQL calculation runs matching filter. Execute an assessment in LCA Analytics to record your first run.
            </p>
          ) : (
            <div className="data-table-container">
              <table className="data-table">
                <thead>
                  <tr>
                    <th style={{ width: '110px' }}>Run ID</th>
                    <th>Product Name</th>
                    <th>GWP100 Footprint</th>
                    <th>Acidification</th>
                    <th>Matrix Hash</th>
                    <th>Logged At</th>
                    <th style={{ textAlign: 'center' }}>Inspect</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredV1Runs.map((run) => (
                    <tr key={run.run_id}>
                      <td>
                        <span className="badge badge-purple" title={run.run_id}>
                          {run.run_id.slice(0, 8)}...
                        </span>
                      </td>
                      <td style={{ fontWeight: 700 }}>{run.product_name}</td>
                      <td style={{ fontWeight: 800, color: '#34D399' }}>
                        {run.summary?.gwp100?.toFixed(4) || '—'} <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>kg CO2-Eq</span>
                      </td>
                      <td style={{ color: '#FCD34D' }}>
                        {run.summary?.acidification ? run.summary.acidification.toFixed(6) : '—'} <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>kg SO2-Eq</span>
                      </td>
                      <td>
                        <span
                          className="badge"
                          style={{
                            background: 'rgba(6, 182, 212, 0.1)',
                            color: '#38BDF8',
                            border: '1px solid rgba(6, 182, 212, 0.25)',
                            fontSize: '0.75rem',
                          }}
                        >
                          {run.metadata_info?.matrix_hash || 'sha256:legacy'}
                        </span>
                      </td>
                      <td style={{ color: 'var(--text-dim)', fontSize: '0.8rem' }}>
                        {new Date(run.created_at).toLocaleString()}
                      </td>
                      <td style={{ textAlign: 'center' }}>
                        <button
                          className="btn btn-secondary btn-sm"
                          style={{ padding: '0.3rem 0.6rem' }}
                          onClick={() => setSelectedRunModal(run)}
                          title="Inspect run parameters and payload"
                        >
                          <Eye size={14} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        )}

        {activeSource === 'product_runs' && (
          filteredProductRuns.length === 0 ? (
            <p style={{ color: 'var(--text-dim)', textAlign: 'center', padding: '3rem 1rem', fontStyle: 'italic' }}>
              No product model calculation runs found.
            </p>
          ) : (
            <div className="data-table-container">
              <table className="data-table">
                <thead>
                  <tr>
                    <th style={{ width: '70px' }}>Run ID</th>
                    <th>Product Name</th>
                    <th>Impact Method</th>
                    <th>Carbon Footprint</th>
                    <th>Freight %</th>
                    <th>Calculated At</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredProductRuns.map((run) => (
                    <tr key={run.run_id}>
                      <td><span className="badge badge-purple">#{run.run_id}</span></td>
                      <td style={{ fontWeight: 700 }}>{run.product_name}</td>
                      <td style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }} title={run.method_name}>
                        {run.method_name?.split('/')[0]?.trim()}
                      </td>
                      <td style={{ fontWeight: 800, color: '#34D399' }}>
                        {run.total_score?.toFixed(4)} {run.method_unit}
                      </td>
                      <td><span className="badge badge-amber">{run.transport_percentage?.toFixed(1)}%</span></td>
                      <td style={{ color: 'var(--text-dim)', fontSize: '0.8rem' }}>
                        {new Date(run.calculated_at).toLocaleString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        )}
      </div>

      {/* Run Inspection Modal */}
      {selectedRunModal && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(0,0,0,0.8)',
            backdropFilter: 'blur(8px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            padding: '1.5rem',
          }}
        >
          <div
            className="glass-panel"
            style={{
              width: '100%',
              maxWidth: '750px',
              background: '#0B0F19',
              border: '1px solid rgba(255,255,255,0.15)',
              maxHeight: '90vh',
              display: 'flex',
              flexDirection: 'column',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
              <div>
                <h3 style={{ fontSize: '1.2rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <Database size={20} color="#10B981" />
                  PostgreSQL Run Audit: {selectedRunModal.product_name}
                </h3>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                  UUID: {selectedRunModal.run_id} &bull; Recorded: {new Date(selectedRunModal.created_at).toLocaleString()}
                </span>
              </div>
              <button className="btn btn-secondary btn-sm" onClick={() => setSelectedRunModal(null)}>
                ✕ Close
              </button>
            </div>

            {/* Impact Summary Badges */}
            <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', marginBottom: '1rem' }}>
              {selectedRunModal.summary && Object.entries(selectedRunModal.summary).map(([k, v]) => (
                <div
                  key={k}
                  style={{
                    background: 'rgba(16, 185, 129, 0.08)',
                    border: '1px solid rgba(16, 185, 129, 0.25)',
                    padding: '0.5rem 0.85rem',
                    borderRadius: '6px',
                  }}
                >
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>{k}</div>
                  <div style={{ fontSize: '1.1rem', fontWeight: 800, color: '#34D399' }}>
                    {typeof v === 'number' ? v.toFixed(6) : v}
                  </div>
                </div>
              ))}

              {selectedRunModal.metadata_info?.matrix_hash && (
                <div
                  style={{
                    background: 'rgba(6, 182, 212, 0.08)',
                    border: '1px solid rgba(6, 182, 212, 0.25)',
                    padding: '0.5rem 0.85rem',
                    borderRadius: '6px',
                  }}
                >
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Matrix Fingerprint</div>
                  <div style={{ fontSize: '0.95rem', fontWeight: 700, color: '#38BDF8' }}>
                    {selectedRunModal.metadata_info.matrix_hash}
                  </div>
                </div>
              )}
            </div>

            {/* Request Data JSON Preview */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.4rem' }}>
              <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-muted)' }}>
                Original Calculation Payload (JSON)
              </span>
              <button
                className="btn btn-secondary btn-sm"
                onClick={() => handleCopyJson(selectedRunModal.request_data || selectedRunModal)}
              >
                {copied ? <CheckCircle2 size={13} color="#10B981" /> : <Copy size={13} />}
                <span>{copied ? 'Copied!' : 'Copy JSON'}</span>
              </button>
            </div>

            <pre
              className="code-block"
              style={{
                flex: 1,
                overflowY: 'auto',
                fontSize: '0.8rem',
                maxHeight: '350px',
                background: '#06080F',
              }}
            >
              {JSON.stringify(selectedRunModal.request_data || selectedRunModal, null, 2)}
            </pre>
          </div>
        </div>
      )}
    </div>
  )
}
