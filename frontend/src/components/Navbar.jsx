import React from 'react'
import { Activity, Layers, BarChart3, Database, Code2, Clock, Sparkles, CheckCircle2, AlertCircle } from 'lucide-react'

export default function Navbar({ activeTab, setActiveTab, health, savedCount, dbStatus }) {
  const isHealthy = health?.status === 'healthy'

  return (
    <header className="navbar">
      <div className="nav-brand">
        <div className="brand-logo" id="brand-logo-icon">
          <Activity size={22} strokeWidth={2.5} />
        </div>
        <div className="brand-text">
          <h1>EcoSphere LCA</h1>
          <span>Brightway Studio v1.0</span>
        </div>
      </div>

      <nav className="nav-tabs" aria-label="Main Navigation">
        <button
          id="nav-tab-builder"
          className={`nav-tab-btn ${activeTab === 'builder' ? 'active' : ''}`}
          onClick={() => setActiveTab('builder')}
        >
          <Layers size={17} />
          <span>Product Builder</span>
        </button>

        <button
          id="nav-tab-analytics"
          className={`nav-tab-btn ${activeTab === 'analytics' ? 'active' : ''}`}
          onClick={() => setActiveTab('analytics')}
        >
          <BarChart3 size={17} />
          <span>LCA Analytics</span>
        </button>

        <button
          id="nav-tab-catalog"
          className={`nav-tab-btn ${activeTab === 'catalog' ? 'active' : ''}`}
          onClick={() => setActiveTab('catalog')}
        >
          <Database size={17} />
          <span>Catalog ({savedCount})</span>
        </button>

        <button
          id="nav-tab-history"
          className={`nav-tab-btn ${activeTab === 'history' ? 'active' : ''}`}
          onClick={() => setActiveTab('history')}
        >
          <Clock size={17} />
          <span>Audit History</span>
        </button>

        <button
          id="nav-tab-api"
          className={`nav-tab-btn ${activeTab === 'api' ? 'active' : ''}`}
          onClick={() => setActiveTab('api')}
        >
          <Code2 size={17} />
          <span>API & Payload</span>
        </button>
      </nav>

      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
        {dbStatus?.matrix_hash && (
          <div
            className="badge"
            style={{
              background: 'rgba(6, 182, 212, 0.12)',
              color: '#38BDF8',
              border: '1px solid rgba(6, 182, 212, 0.3)',
              fontSize: '0.75rem',
              padding: '0.35rem 0.65rem',
            }}
            title={`Active Database: ${dbStatus.active_database?.toUpperCase()} | Fingerprint: ${dbStatus.matrix_hash}`}
          >
            <span>{dbStatus.matrix_hash}</span>
          </div>
        )}

        <div className="nav-status" id="backend-health-indicator" title={isHealthy ? `Project: ${health.brightway_project} | ${health.installed_methods_count} LCIA Methods` : 'Backend offline'}>
          <div className="pulse-dot" style={{ backgroundColor: isHealthy ? '#10B981' : '#F43F5E' }} />
          <span>{isHealthy ? `Brightway (${health.installed_methods_count || 762} Methods)` : 'Engine Disconnected'}</span>
        </div>
      </div>
    </header>
  )
}
