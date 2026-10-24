/**
 * API Client for Brightway FastAPI Service
 */

const BASE_URL = '' // Uses Vite reverse-proxy

export async function fetchHealth() {
  try {
    const res = await fetch('/health')
    if (!res.ok) throw new Error(`Health check failed: ${res.statusText}`)
    return await res.json()
  } catch (err) {
    console.warn('Backend offline or unreachable:', err)
    return { status: 'offline' }
  }
}

export async function fetchProducts() {
  const res = await fetch('/api/products')
  if (!res.ok) throw new Error('Failed to load products from storage')
  return await res.json()
}

export async function saveProduct(product) {
  const res = await fetch('/api/products', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(product),
  })
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}))
    throw new Error(errorData.detail?.validation_errors?.join(', ') || 'Failed to save product')
  }
  return await res.json()
}

export async function deleteProduct(productId) {
  const res = await fetch(`/api/products/${productId}`, {
    method: 'DELETE',
  })
  if (!res.ok) throw new Error(`Failed to delete product ${productId}`)
  return await res.json()
}

export async function calculateLcaOnPayload(product, method = null) {
  const payload = { product }
  if (method) payload.method = method

  const res = await fetch('/api/lca/calculate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}))
    const detailMsg = typeof errorData.detail === 'string'
      ? errorData.detail
      : (errorData.detail?.validation_errors?.join(', ') || JSON.stringify(errorData.detail || 'Brightway LCA calculation failed'))
    throw new Error(detailMsg)
  }
  return await res.json()
}

export async function calculateLcaOnSaved(productId, method = null) {
  const url = `/api/lca/calculate-saved/${productId}`
  const body = method ? { method } : {}
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}))
    const detailMsg = typeof errorData.detail === 'string'
      ? errorData.detail
      : (errorData.detail?.validation_errors?.join(', ') || JSON.stringify(errorData.detail || 'LCA calculation on saved product failed'))
    throw new Error(detailMsg)
  }
  return await res.json()
}

export async function fetchMethods(search = '', limit = 30) {
  const params = new URLSearchParams()
  if (search) params.append('search', search)
  params.append('limit', limit)

  const res = await fetch(`/api/methods?${params.toString()}`)
  if (!res.ok) throw new Error('Failed to fetch methods')
  return await res.json()
}

export async function fetchHistory(productId = null, limit = 50) {
  const params = new URLSearchParams()
  if (productId) params.append('product_id', productId)
  params.append('limit', limit)

  const res = await fetch(`/api/history?${params.toString()}`)
  if (!res.ok) throw new Error('Failed to load assessment history')
  return await res.json()
}

export async function fetchDatabaseStatus() {
  const res = await fetch('/api/database/status')
  if (!res.ok) return { active_database: 'unknown', is_postgresql: false }
  return await res.json()
}

// --------------------------------------------------
// /v1 Enterprise Dynamic API Methods
// --------------------------------------------------

export async function calculateV1Lca(payload) {
  const res = await fetch('/v1/lca/calculate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}))
    throw new Error(errorData.detail || 'PCF LCA calculation failed')
  }
  return await res.json()
}

export async function fetchRuns(limit = 50) {
  const res = await fetch(`/v1/runs?limit=${limit}`)
  if (!res.ok) throw new Error('Failed to load calculation runs')
  return await res.json()
}

export async function fetchRunById(runId) {
  const res = await fetch(`/v1/runs/${runId}`)
  if (!res.ok) throw new Error(`Failed to load run ${runId}`)
  return await res.json()
}

export async function fetchUnits() {
  const res = await fetch('/v1/units')
  if (!res.ok) throw new Error('Failed to load unit conversions')
  return await res.json()
}

export async function fetchActivities() {
  const res = await fetch('/v1/activities')
  if (!res.ok) throw new Error('Failed to load background activities')
  return await res.json()
}

export async function fetchFlows() {
  const res = await fetch('/v1/flows')
  if (!res.ok) throw new Error('Failed to load elementary flows')
  return await res.json()
}

export async function fetchV1Methods() {
  const res = await fetch('/v1/methods')
  if (!res.ok) throw new Error('Failed to load LCIA methods')
  return await res.json()
}

export async function fetchDatabaseVersion() {
  const res = await fetch('/v1/database/version')
  if (!res.ok) return { active_database: 'unknown', matrix_hash: 'unknown' }
  return await res.json()
}

export async function uploadExcelProducts(file) {
  const formData = new FormData()
  formData.append('file', file)
  const res = await fetch('/api/products/import-excel', {
    method: 'POST',
    body: formData,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Failed to import Excel file')
  }
  return await res.json()
}




