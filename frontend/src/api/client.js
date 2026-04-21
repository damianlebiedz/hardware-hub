/**
 * API client for Hardware Hub.
 *
 * All backend calls go through this module so that the base URL and common
 * headers are configured in one place.  In development, Vite proxies /api
 * to localhost:8000.  In the Docker stack, nginx proxies /api to the backend
 * container, so the same relative paths work without any environment-specific
 * URL configuration.
 */

const BASE = '/api'

/** Return the stored user object from localStorage, or null. */
export function getStoredUser() {
  try {
    const raw = localStorage.getItem('hardware_hub_user')
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

/** Build the X-User-Role header value from the stored user. */
function roleHeader() {
  const user = getStoredUser()
  return user ? { 'X-User-Role': user.role } : {}
}

/** Generic fetch wrapper — throws on non-2xx responses. */
async function request(method, path, body) {
  const headers = { 'Content-Type': 'application/json', ...roleHeader() }
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    let detail = res.statusText
    try { detail = (await res.json()).detail ?? detail } catch { /* ignored */ }
    throw new Error(detail)
  }
  // 204 No Content has no body
  if (res.status === 204) return null
  return res.json()
}

// ── Auth ────────────────────────────────────────────────────────────────────

/** Log in with email and password. */
export const login = (email, password) => request('POST', '/auth/login', { email, password })

// ── Admin ───────────────────────────────────────────────────────────────────

/** Create a new user account (admin only). Always creates a 'user'-role account. */
export const createUser = (email, password) =>
  request('POST', '/admin/users', { email, password })

// ── Hardware ─────────────────────────────────────────────────────────────────

/** List all hardware, with optional filter query params. */
export function listHardware(params = {}) {
  const qs = new URLSearchParams()
  if (params.status) qs.set('status', params.status)
  if (params.brand)  qs.set('brand',  params.brand)
  if (params.name)   qs.set('name',   params.name)
  const query = qs.toString()
  return request('GET', `/hardware${query ? '?' + query : ''}`)
}

/** Create a new hardware item (admin only). */
export const createHardware = (data) => request('POST', '/hardware', data)

/** Partially update a hardware item (admin only — toggles status, etc.). */
export const updateHardware = (id, data) => request('PUT', `/hardware/${id}`, data)

/** Permanently delete a hardware item (admin only). */
export const deleteHardware = (id) => request('DELETE', `/hardware/${id}`)

// ── Rentals ──────────────────────────────────────────────────────────────────

/** Rent a hardware item. */
export const rentHardware = (userId, hardwareId) =>
  request('POST', '/rentals/rent', { user_id: userId, hardware_id: hardwareId })

/** Return a rented item. */
export const returnHardware = (rentalId) =>
  request('POST', '/rentals/return', { rental_id: rentalId })

/** Get active rentals for the given user. */
export const myRentals = (userId) => request('GET', `/rentals/my?user_id=${userId}`)

// ── AI ────────────────────────────────────────────────────────────────────────

/** Send messy legacy JSON to the AI seed importer. */
export const aiSeed = (rawArray) => request('POST', '/ai/seed', rawArray)

/** Natural-language hardware search. */
export const aiSearch = (query) => request('POST', '/ai/search', { query })
