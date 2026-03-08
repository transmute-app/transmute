const AUTH_TOKEN_KEY = 'transmute-access-token'
export const AUTH_EXPIRED_EVENT = 'transmute:auth-expired'

export class ApiError extends Error {
  status: number
  detail: string

  constructor(status: number, detail: string) {
    super(detail)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

function getErrorDetail(payload: unknown, fallback: string) {
  if (typeof payload === 'string' && payload.trim()) return payload
  if (payload && typeof payload === 'object') {
    const maybeDetail = (payload as { detail?: unknown }).detail
    if (typeof maybeDetail === 'string' && maybeDetail.trim()) return maybeDetail
  }
  return fallback
}

export function getStoredToken() {
  try {
    return localStorage.getItem(AUTH_TOKEN_KEY)
  } catch {
    return null
  }
}

export function setStoredToken(token: string | null) {
  try {
    if (token) {
      localStorage.setItem(AUTH_TOKEN_KEY, token)
      return
    }
    localStorage.removeItem(AUTH_TOKEN_KEY)
  } catch {
    // Ignore storage failures in unsupported environments.
  }
}

type FetchOptions = {
  auth?: boolean
}

async function buildApiError(response: Response) {
  const contentType = response.headers.get('content-type') || ''
  let payload: unknown = null

  try {
    if (contentType.includes('application/json')) {
      payload = await response.json()
    } else {
      payload = await response.text()
    }
  } catch {
    payload = null
  }

  return new ApiError(response.status, getErrorDetail(payload, response.statusText || 'Request failed'))
}

export async function apiFetch(input: RequestInfo | URL, init: RequestInit = {}, options: FetchOptions = {}) {
  const shouldUseAuth = options.auth !== false
  const headers = new Headers(init.headers)

  if (shouldUseAuth) {
    const token = getStoredToken()
    if (token && !headers.has('Authorization')) {
      headers.set('Authorization', `Bearer ${token}`)
    }
  }

  const response = await fetch(input, { ...init, headers })

  if (response.status === 401 && shouldUseAuth && getStoredToken()) {
    window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT))
  }

  return response
}

export const authFetch = (input: RequestInfo | URL, init: RequestInit = {}) => apiFetch(input, init, { auth: true })
export const publicFetch = (input: RequestInfo | URL, init: RequestInit = {}) => apiFetch(input, init, { auth: false })

export async function apiJson<T>(input: RequestInfo | URL, init: RequestInit = {}, options: FetchOptions = {}) {
  const response = await apiFetch(input, init, options)
  if (!response.ok) throw await buildApiError(response)
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export async function apiBlob(input: RequestInfo | URL, init: RequestInit = {}, options: FetchOptions = {}) {
  const response = await apiFetch(input, init, options)
  if (!response.ok) throw await buildApiError(response)
  return response.blob()
}

export async function apiText(input: RequestInfo | URL, init: RequestInit = {}, options: FetchOptions = {}) {
  const response = await apiFetch(input, init, options)
  if (!response.ok) throw await buildApiError(response)
  return response.text()
}