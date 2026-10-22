import React from 'react'
import { Database, Play, Edit3, Trash2, Box, RefreshCw, Plus, Layers } from 'lucide-react'

export default function ProductCatalog({
  products,
  onRefresh,
  onEditProduct,
  onCalculateProduct,
  onDeleteProduct,
  onCreateNew,
}) {
  return (
    <div className="product-catalog-view">
      <div className="glass-panel" style={{ marginBottom: '1.75rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <h2 style={{ fontSize: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
              <Database size={24} color="#10B981" />
              Persisted Product Library
            </h2>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>
              All product life cycle definitions stored permanently in <code>saved_products.json</code>.
            </p>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <button
              id="btn-refresh-catalog"
              className="btn btn-secondary"
              onClick={onRefresh}
            >
              <RefreshCw size={15} />
              <span>Refresh Library</span>
            </button>

            <button
              id="btn-create-new-product"
              className="btn btn-primary"
              onClick={onCreateNew}
            >
              <Plus size={15} />
              <span>Create Product</span>
            </button>
          </div>
        </div>
      </div>

      {products.length === 0 ? (
        <div className="glass-panel" style={{ textAlign: 'center', padding: '4rem 2rem' }}>
          <Box size={48} color="#94A3B8" style={{ marginBottom: '1rem', opacity: 0.5 }} />
          <h3 style={{ fontSize: '1.25rem', marginBottom: '0.5rem' }}>Storage is Empty</h3>
          <p style={{ color: 'var(--text-muted)', maxWidth: '400px', margin: '0 auto 1.5rem auto', fontSize: '0.9rem' }}>
            No products have been saved to <code>saved_products.json</code> yet. Create or load an example in the Product Builder.
          </p>
          <button className="btn btn-primary" onClick={onCreateNew}>
            Open Product Builder
          </button>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: '1.5rem' }}>
          {products.map((p) => {
            const processCount = p.processes?.length || 0
            const totalInputs = p.processes?.reduce((acc, pr) => acc + (pr.exchanges?.filter(e => e.exchange_type === 'input').length || 0), 0) || 0
            const totalEmissions = p.processes?.reduce((acc, pr) => acc + (pr.exchanges?.filter(e => e.exchange_type === 'output').length || 0), 0) || 0
            const totalTransport = p.processes?.reduce((acc, pr) => acc + (pr.transportation?.length || 0), 0) || 0

            return (
              <div
                key={p.product_id}
                className="glass-panel"
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                  borderTop: '3px solid #10B981',
                }}
              >
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.75rem' }}>
                    <h3 style={{ fontSize: '1.2rem', fontWeight: 700, lineHeight: 1.3 }}>
                      {p.product_name}
                    </h3>
                    <span className="badge badge-emerald">{p.product_id}</span>
                  </div>

                  <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginBottom: '1.25rem' }}>
                    Functional Unit: <strong style={{ color: '#FFF' }}>{p.functional_unit_amount} {p.functional_unit}</strong>
                  </p>

                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.6rem', marginBottom: '1.25rem' }}>
                    <div style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '0.6rem 0.85rem', borderRadius: '6px', fontSize: '0.8rem' }}>
                      <span style={{ color: 'var(--text-dim)', display: 'block' }}>Processes</span>
                      <strong style={{ fontSize: '1rem', color: '#38BDF8' }}>{processCount} stages</strong>
                    </div>

                    <div style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '0.6rem 0.85rem', borderRadius: '6px', fontSize: '0.8rem' }}>
                      <span style={{ color: 'var(--text-dim)', display: 'block' }}>Inputs & Emissions</span>
                      <strong style={{ fontSize: '1rem', color: '#34D399' }}>{totalInputs + totalEmissions} flows</strong>
                    </div>
                  </div>

                  <div style={{ fontSize: '0.8rem', color: 'var(--text-dim)', marginBottom: '1.25rem' }}>
                    Logistics: <strong>{totalTransport} freight leg(s)</strong>
                  </div>
                </div>

                <div style={{ display: 'flex', gap: '0.5rem', borderTop: '1px solid var(--border-subtle)', paddingTop: '1rem' }}>
                  <button
                    className="btn btn-primary btn-sm"
                    style={{ flex: 1 }}
                    onClick={() => onCalculateProduct(p.product_id)}
                  >
                    <Play size={13} fill="currentColor" /> Assess LCA
                  </button>

                  <button
                    className="btn btn-secondary btn-sm"
                    onClick={() => onEditProduct(p)}
                    title="Edit in Product Builder"
                  >
                    <Edit3 size={13} />
                  </button>

                  <button
                    className="btn btn-danger btn-sm"
                    onClick={() => onDeleteProduct(p.product_id)}
                    title="Delete product"
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
