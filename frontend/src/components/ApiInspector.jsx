import React, { useState } from 'react'
import { Code2, Copy, Download, ExternalLink, Play, Check, Sparkles } from 'lucide-react'
import { SENIOR_REFINERY_PAYLOAD } from '../sampleData'

export default function ApiInspector({ product, onCalculatePayload, isCalculating }) {
  const [copiedPayload, setCopiedPayload] = useState(false)
  const [copiedCurl, setCopiedCurl] = useState(false)
  const [customJson, setCustomJson] = useState('')

  const jsonString = JSON.stringify(product, null, 2)

  const curlCommand = `curl -X POST "http://127.0.0.1:8000/api/lca/calculate" \\
  -H "Content-Type: application/json" \\
  -d '${JSON.stringify({ product })}'`

  const handleCopy = (text, type) => {
    navigator.clipboard.writeText(text)
    if (type === 'payload') {
      setCopiedPayload(true)
      setTimeout(() => setCopiedPayload(false), 2000)
    } else {
      setCopiedCurl(true)
      setTimeout(() => setCopiedCurl(false), 2000)
    }
  }

  const handleDownload = () => {
    const blob = new Blob([jsonString], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${product.product_id || 'product'}_payload.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  const handleExecuteCustomJson = () => {
    try {
      const parsed = JSON.parse(customJson)
      // Only unwrap if wrapped in { product: { product_id, processes... } }
      let targetProduct = parsed
      if (parsed.product && parsed.product.processes) {
        targetProduct = parsed.product
      }
      onCalculatePayload(targetProduct)
    } catch (err) {
      alert(`Invalid JSON format: ${err.message}`)
    }
  }

  const handleLoadSeniorPayload = () => {
    setCustomJson(JSON.stringify(SENIOR_REFINERY_PAYLOAD, null, 2))
  }

  return (
    <div className="api-inspector-view">
      {/* Top Banner */}
      <div className="glass-panel" style={{ marginBottom: '1.75rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <h2 style={{ fontSize: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
              <Code2 size={24} color="#C084FC" />
              REST API & Payload Inspector
            </h2>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>
              Inspect the exact JSON schema and cURL requests executed against the FastAPI Brightway microservice.
            </p>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <a
              href="http://127.0.0.1:8000/docs"
              target="_blank"
              rel="noreferrer"
              className="btn btn-outline-emerald"
            >
              <span>Open Swagger UI</span>
              <ExternalLink size={14} />
            </a>

            <a
              href="http://127.0.0.1:8000/redoc"
              target="_blank"
              rel="noreferrer"
              className="btn btn-secondary"
            >
              <span>ReDoc</span>
              <ExternalLink size={14} />
            </a>
          </div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(450px, 1fr))', gap: '1.5rem', marginBottom: '1.75rem' }}>
        {/* 1. Current Product Payload */}
        <div className="glass-panel">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <h3 style={{ fontSize: '1.1rem' }}>Active Product Payload</h3>
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <button
                className="btn btn-secondary btn-sm"
                onClick={() => handleCopy(jsonString, 'payload')}
              >
                {copiedPayload ? <Check size={14} color="#10B981" /> : <Copy size={14} />}
                <span>{copiedPayload ? 'Copied!' : 'Copy'}</span>
              </button>
              <button
                className="btn btn-secondary btn-sm"
                onClick={handleDownload}
              >
                <Download size={14} />
                <span>Export</span>
              </button>
            </div>
          </div>
          <pre className="code-block" style={{ maxHeight: '420px' }}>
            <code>{jsonString}</code>
          </pre>
        </div>

        {/* 2. cURL Request Generator */}
        <div className="glass-panel">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <h3 style={{ fontSize: '1.1rem' }}>cURL Terminal Command</h3>
            <button
              className="btn btn-secondary btn-sm"
              onClick={() => handleCopy(curlCommand, 'curl')}
            >
              {copiedCurl ? <Check size={14} color="#10B981" /> : <Copy size={14} />}
              <span>{copiedCurl ? 'Copied!' : 'Copy'}</span>
            </button>
          </div>
          <pre className="code-block" style={{ maxHeight: '420px', whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
            <code>{curlCommand}</code>
          </pre>
        </div>
      </div>

      {/* 3. Direct JSON Paste Runner */}
      <div className="glass-panel">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem', flexWrap: 'wrap', gap: '0.75rem' }}>
          <div>
            <h3 style={{ fontSize: '1.1rem' }}>Direct JSON Payload Tester</h3>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', margin: 0 }}>
              Paste any custom product JSON structure (supports both multi-process and Senior's flat refinery format with ISO mass allocation):
            </p>
          </div>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button
              className="btn btn-secondary btn-sm"
              onClick={handleLoadSeniorPayload}
              title="Populate editor with Senior's Diesel Refinery mass allocation payload"
            >
              <Sparkles size={14} color="#F59E0B" />
              <span>Load Senior's Refinery Payload</span>
            </button>
            {customJson && (
              <button
                className="btn btn-secondary btn-sm"
                onClick={() => setCustomJson('')}
              >
                Clear
              </button>
            )}
          </div>
        </div>

        <textarea
          className="form-control"
          style={{ width: '100%', minHeight: '220px', fontFamily: 'var(--font-mono)', fontSize: '0.825rem', marginBottom: '1rem', background: '#090D16' }}
          placeholder='Paste Senior refinery payload or canonical product JSON...'
          value={customJson}
          onChange={(e) => setCustomJson(e.target.value)}
        />
        <button
          className="btn btn-primary"
          onClick={handleExecuteCustomJson}
          disabled={!customJson.trim() || isCalculating}
        >
          <Play size={15} fill="currentColor" />
          <span>{isCalculating ? 'Computing Assessment...' : 'Execute Payload Calculation'}</span>
        </button>
      </div>
    </div>
  )
}
