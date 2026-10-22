import React, { useState, useEffect } from 'react'
import { History, Database, BarChart3, Clock, RefreshCw, CheckCircle2, Award, Truck, Layers, Filter } from 'lucide-react'
import { fetchHistory, fetchDatabaseStatus } from '../apiClient'

export default function LcaHistory({ onSelectRun }) {
  const [history, setHistory] = useState([])
  const [dbStatus, setDbStatus] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [filterProduct, setFilterProduct] = useState('')

  const loadHistoryData = async () => {
    try {
      setIsLoading(true)
      const [h, s] = await Promise.all([
        fetchHistory(filterProduct || null, 100),
        fetchDatabaseStatus(),
      ])
      setHistory(h)
      setDbStatus(s)
    } catch (err) {
      console.warn('Could not load history:', err)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    loadHistoryData()
  }, [filterProduct])

  // Compute product benchmark averages from history
  const productBenchmarks = {}
  history.forEach((run) => {
    if (!productBenchmarks[run.product_name]) {
      productBenchmarks[run.product_name] = {
        name: run.product_name,
        latestScore: run.total_score,
        unit: run.method_unit,
        runsCount: 1,
      }
    } else {
      productBenchmarks[run.product_name].runsCount += 1
    }
  })

  const benchmarkList = Object.values(productBenchmarks)
  const maxScore = benchmarkList.length > 0 ? Math.max(...benchmarkList.map((b) => b.latestScore), 0.01) : 1.0

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
              Permanent record of every Brightway calculation run for compliance, benchmarking, and audits.
            </p>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
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
              <span>Engine: {dbStatus?.active_database?.toUpperCase() || 'SQL'} ({history.length} Runs Logged)</span>
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

      {/* 1. Product Footprint Benchmark Card */}
      {benchmarkList.length > 0 && (
        <div className="glass-panel" style={{ marginBottom: '1.75rem' }}>
          <h3 style={{ fontSize: '1.1rem', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <BarChart3 size={20} color="#06B6D4" />
            Product Portfolio Carbon Benchmark
          </h3>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            {benchmarkList.map((item, idx) => {
              const pct = (item.latestScore / maxScore) * 100
              return (
                <div key={idx} style={{ background: 'rgba(15, 23, 42, 0.4)', padding: '0.9rem', borderRadius: '8px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.4rem' }}>
                    <span style={{ fontWeight: 700, fontSize: '0.95rem' }}>{item.name}</span>
                    <span style={{ fontWeight: 800, color: '#34D399', fontSize: '1.05rem' }}>
                      {item.latestScore.toFixed(4)} <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{item.unit}</span>
                    </span>
                  </div>

                  <div className="progress-track">
                    <div
                      className="progress-fill"
                      style={{
                        width: `${Math.max(pct, 2)}%`,
                        background: idx === 0 ? 'linear-gradient(90deg, #8B5CF6, #06B6D4)' : 'linear-gradient(90deg, #10B981, #34D399)',
                      }}
                    />
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* 2. Audit Trail Log Table */}
      <div className="glass-panel">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.5rem' }}>
          <h3 style={{ fontSize: '1.1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Clock size={19} color="#F59E0B" />
            Calculation Run Audit Logs ({history.length})
          </h3>
        </div>

        {history.length === 0 ? (
          <p style={{ color: 'var(--text-dim)', textAlign: 'center', padding: '3rem 1rem', fontStyle: 'italic' }}>
            No calculations logged yet. Run any assessment in the "LCA Analytics" tab to record your first audit entry.
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
                {history.map((run) => (
                  <tr key={run.run_id}>
                    <td>
                      <span className="badge badge-purple">#{run.run_id}</span>
                    </td>
                    <td style={{ fontWeight: 700 }}>{run.product_name}</td>
                    <td style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }} title={run.method_name}>
                      {run.method_name.split('/')[0]?.trim()}
                    </td>
                    <td style={{ fontWeight: 800, color: '#34D399' }}>
                      {run.total_score.toFixed(4)} {run.method_unit}
                    </td>
                    <td>
                      <span className="badge badge-amber">{run.transport_percentage.toFixed(1)}%</span>
                    </td>
                    <td style={{ color: 'var(--text-dim)', fontSize: '0.8rem' }}>
                      {new Date(run.calculated_at).toLocaleString()}
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
}
