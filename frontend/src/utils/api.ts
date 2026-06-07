const AUTH_TOKEN_KEY = 'transmute-access-token'
export const AUTH_EXPIRED_EVENT = 'transmute:auth-expired'

declare global {
  interface Window {
    // Injected into index.html at runtime by the backend; "" at the domain root.
    __BASE_PATH__?: string
  }
}

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

    if (typeof maybeDetail === 'object' && Array.isArray(maybeDetail)) {
      for(const item of maybeDetail) {
        const maybePydanticError = (item as {msg?: unknown, type?:unknown, loc?:unknown}).msg
        if(typeof maybePydanticError === 'string' && maybePydanticError.trim()) return maybePydanticError
      }
    }
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

/**
 * HTTP client for the backend API. Prefixes every absolute ("/...") path with
 * the reverse-proxy sub-path, attaches the bearer token, and surfaces ApiError
 * on non-2xx responses for the json/blob/text helpers.
 */
export class ApiClient {
  /** Normalized sub-path with no trailing slash ("" at the domain root). */
  readonly basePath: string

  constructor(basePath: string = window.__BASE_PATH__ ?? '') {
    this.basePath = basePath.replace(/\/+$/, '')
  }

  /** Prefix an absolute ("/...") path with the sub-path; other inputs pass through. */
  url(path: string): string {
    return path.startsWith('/') ? `${this.basePath}${path}` : path
  }

  async fetch(input: RequestInfo | URL, init: RequestInit = {}, options: FetchOptions = {}) {
    if (typeof input === 'string') input = this.url(input)

    const shouldUseAuth = options.auth !== false
    const headers = new Headers(init.headers)

    if (shouldUseAuth) {
      const token = getStoredToken()
      if (token && !headers.has('Authorization')) {
        headers.set('Authorization', `Bearer ${token}`)
      }
    }

    const response = await window.fetch(input, { ...init, headers })

    if (response.status === 401 && shouldUseAuth && getStoredToken()) {
      window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT))
    }

    return response
  }

  async json<T>(input: RequestInfo | URL, init: RequestInit = {}, options: FetchOptions = {}) {
    const response = await this.fetch(input, init, options)
    if (!response.ok) throw await buildApiError(response)
    if (response.status === 204) return undefined as T
    return response.json() as Promise<T>
  }

  async blob(input: RequestInfo | URL, init: RequestInit = {}, options: FetchOptions = {}) {
    const response = await this.fetch(input, init, options)
    if (!response.ok) throw await buildApiError(response)
    return response.blob()
  }

  async text(input: RequestInfo | URL, init: RequestInit = {}, options: FetchOptions = {}) {
    const response = await this.fetch(input, init, options)
    if (!response.ok) throw await buildApiError(response)
    return response.text()
  }
}

/** Shared client configured from the runtime sub-path. */
export const api = new ApiClient()

// Backward-compatible function exports delegating to the shared client.
export const apiFetch = (input: RequestInfo | URL, init: RequestInit = {}, options: FetchOptions = {}) => api.fetch(input, init, options)
export const authFetch = (input: RequestInfo | URL, init: RequestInit = {}) => api.fetch(input, init, { auth: true })
export const publicFetch = (input: RequestInfo | URL, init: RequestInit = {}) => api.fetch(input, init, { auth: false })
export const apiJson = <T,>(input: RequestInfo | URL, init: RequestInit = {}, options: FetchOptions = {}) => api.json<T>(input, init, options)
export const apiBlob = (input: RequestInfo | URL, init: RequestInit = {}, options: FetchOptions = {}) => api.blob(input, init, options)
export const apiText = (input: RequestInfo | URL, init: RequestInit = {}, options: FetchOptions = {}) => api.text(input, init, options)
