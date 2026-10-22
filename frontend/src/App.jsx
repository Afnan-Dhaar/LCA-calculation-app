import React, { useState, useEffect } from 'react'
import Navbar from './components/Navbar'
import ProductBuilder from './components/ProductBuilder'
import LcaAnalytics from './components/LcaAnalytics'
import ProductCatalog from './components/ProductCatalog'
import ApiInspector from './components/ApiInspector'
import LcaHistory from './components/LcaHistory'
import {
  fetchHealth,
  fetchProducts,
  saveProduct,
  deleteProduct,
  calculateLcaOnPayload,
  calculateLcaOnSaved,
} from './apiClient'
import { SAMPLE_PRODUCTS } from './sampleData'
import { CheckCircle2, AlertCircle } from 'lucide-react'

export default function App() {
  const [activeTab, setActiveTab] = useState('builder')
  const [health, setHealth] = useState(null)
  const [products, setProducts] = useState([])
  const [currentProduct, setCurrentProduct] = useState(SAMPLE_PRODUCTS[0])
  const [selectedProductId, setSelectedProductId] = useState('')
  const [lcaResult, setLcaResult] = useState(null)
  const [isSaving, setIsSaving] = useState(false)
  const [isCalculating, setIsCalculating] = useState(false)
  const [toasts, setToasts] = useState([])

  // Toast Notification helper
  const showToast = (message, type = 'success') => {
    const id = Date.now()
    setToasts((prev) => [...prev, { id, message, type }])
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id))
    }, 3500)
  }

  // Load initial backend health and products
  const loadData = async () => {
    const h = await fetchHealth()
    setHealth(h)

    try {
      const prods = await fetchProducts()
      setProducts(prods)
      if (prods.length > 0 && !selectedProductId) {
        setSelectedProductId(prods[0].product_id)
      }
    } catch (err) {
      console.warn('Could not fetch saved products:', err)
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  // Save product handler
  const handleSaveProduct = async () => {
    if (!currentProduct.product_id.trim() || !currentProduct.product_name.trim()) {
      showToast('Please provide both Product ID and Product Name', 'error')
      return
    }

    try {
      setIsSaving(true)
      const res = await saveProduct(currentProduct)
      showToast(`Product '${res.product_name}' successfully saved to disk!`, 'success')
      await loadData()
    } catch (err) {
      showToast(`Failed to save: ${err.message}`, 'error')
    } finally {
      setIsSaving(false)
    }
  }

  // Calculate LCA on active builder product
  const handleCalculateCurrent = async (method = null) => {
    try {
      setIsCalculating(true)
      const res = await calculateLcaOnPayload(currentProduct, method)
      setLcaResult(res)
      setSelectedProductId('__current_builder__')
      setActiveTab('analytics')
      showToast(`LCA computed: ${res.total_score.toFixed(4)} ${res.method_unit}`, 'success')
    } catch (err) {
      showToast(`Calculation failed: ${err.message}`, 'error')
    } finally {
      setIsCalculating(false)
    }
  }

  // Calculate LCA on a saved product
  const handleCalculateSaved = async (productId, method = null) => {
    if (!productId) return
    try {
      setIsCalculating(true)
      setSelectedProductId(productId)
      const res = await calculateLcaOnSaved(productId, method)
      setLcaResult(res)
      setActiveTab('analytics')
      showToast(`LCA computed for ${res.product_name}: ${res.total_score.toFixed(4)} ${res.method_unit}`, 'success')
    } catch (err) {
      showToast(`Calculation failed: ${err.message}`, 'error')
    } finally {
      setIsCalculating(false)
    }
  }

  // Delete product
  const handleDeleteProduct = async (productId) => {
    if (!window.confirm(`Are you sure you want to permanently delete product '${productId}'?`)) {
      return
    }

    try {
      await deleteProduct(productId)
      showToast(`Product '${productId}' deleted from storage`, 'success')
      await loadData()
    } catch (err) {
      showToast(`Delete failed: ${err.message}`, 'error')
    }
  }

  // Edit product in builder
  const handleEditProduct = (prod) => {
    setCurrentProduct(JSON.parse(JSON.stringify(prod)))
    setActiveTab('builder')
    showToast(`Loaded '${prod.product_name}' into builder`, 'success')
  }

  // Create new blank product
  const handleCreateNew = () => {
    const newId = `product_${Date.now().toString().slice(-4)}`
    setCurrentProduct({
      product_id: newId,
      product_name: 'New Custom Product',
      functional_unit_amount: 1.0,
      functional_unit: 'unit',
      processes: [
        {
          process_id: 'process_1',
          process_name: 'Primary Manufacturing Stage',
          stage: 'Manufacturing',
          exchanges: [
            { flow_name: 'Plastic granules', exchange_type: 'input', amount: 0.5, unit: 'kg' },
            { flow_name: 'Electricity, grid average', exchange_type: 'input', amount: 0.2, unit: 'kWh' },
          ],
          transportation: [
            { transport_mode: 'truck', distance: 50.0, distance_unit: 'km', transported_mass: 0.5, mass_unit: 'kg' },
          ],
        },
      ],
    })
    setActiveTab('builder')
  }

  return (
    <div className="app-container">
      {/* Top Navbar */}
      <Navbar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        health={health}
        savedCount={products.length}
      />

      {/* Main View Port */}
      <main className="main-content">
        {activeTab === 'builder' && (
          <ProductBuilder
            product={currentProduct}
            setProduct={setCurrentProduct}
            onSave={handleSaveProduct}
            onCalculate={handleCalculateCurrent}
            isSaving={isSaving}
            isCalculating={isCalculating}
          />
        )}

        {activeTab === 'analytics' && (
          <LcaAnalytics
            result={lcaResult}
            products={products}
            currentProduct={currentProduct}
            selectedProductId={selectedProductId}
            setSelectedProductId={setSelectedProductId}
            onCalculateSaved={handleCalculateSaved}
            onCalculateCurrent={handleCalculateCurrent}
            isCalculating={isCalculating}
          />
        )}

        {activeTab === 'catalog' && (
          <ProductCatalog
            products={products}
            onRefresh={loadData}
            onEditProduct={handleEditProduct}
            onCalculateProduct={handleCalculateSaved}
            onDeleteProduct={handleDeleteProduct}
            onCreateNew={handleCreateNew}
          />
        )}

        {activeTab === 'history' && (
          <LcaHistory />
        )}

        {activeTab === 'api' && (
          <ApiInspector
            product={currentProduct}
            onCalculatePayload={async (p) => {
              try {
                setIsCalculating(true)
                const res = await calculateLcaOnPayload(p)
                setLcaResult(res)
                setActiveTab('analytics')
                showToast(`Calculated: ${res.total_score.toFixed(4)} ${res.method_unit}`, 'success')
              } catch (err) {
                showToast(`Failed: ${err.message}`, 'error')
              } finally {
                setIsCalculating(false)
              }
            }}
            isCalculating={isCalculating}
          />
        )}
      </main>

      {/* Toast Notifications */}
      <div className="toast-container">
        {toasts.map((t) => (
          <div
            key={t.id}
            className="toast"
            style={{ borderLeftColor: t.type === 'error' ? '#F43F5E' : '#10B981' }}
          >
            {t.type === 'error' ? (
              <AlertCircle size={18} color="#F43F5E" />
            ) : (
              <CheckCircle2 size={18} color="#10B981" />
            )}
            <span>{t.message}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
