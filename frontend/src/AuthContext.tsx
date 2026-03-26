import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { AUTH_EXPIRED_EVENT, apiJson, getStoredToken, setStoredToken } from './utils/api'

export type UserRole = 'admin' | 'member' | 'guest'

export interface AuthUser {
  uuid: string
  username: string
  email: string | null
  full_name: string | null
  role: UserRole
  disabled: boolean
  is_guest: boolean
}

interface BootstrapStatus {
  requires_setup: boolean
  user_count: number
}

interface AuthResponse {
  access_token: string
  token_type: string
  expires_in: number
  user: AuthUser
}

interface LoginInput {
  username: string
  password: string
}

interface BootstrapInput extends LoginInput {
  email?: string
  full_name?: string
}

interface AuthContextValue {
  status: 'loading' | 'authenticated' | 'unauthenticated'
  user: AuthUser | null
  bootstrapStatus: BootstrapStatus | null
  isAdmin: boolean
  login: (input: LoginInput) => Promise<void>
  createBootstrapUser: (input: BootstrapInput) => Promise<void>
  loginAsGuest: () => Promise<void>
  logout: () => void
  refreshUser: () => Promise<void>
  replaceUser: (user: AuthUser) => void
}

const AuthContext = createContext<AuthContextValue>({
  status: 'loading',
  user: null,
  bootstrapStatus: null,
  isAdmin: false,
  login: async () => {},
  createBootstrapUser: async () => {},
  loginAsGuest: async () => {},
  logout: () => {},
  refreshUser: async () => {},
  replaceUser: () => {},
})

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthContextValue['status']>('loading')
  const [user, setUser] = useState<AuthUser | null>(null)
  const [bootstrapStatus, setBootstrapStatus] = useState<BootstrapStatus | null>(null)

  const logout = () => {
    setStoredToken(null)
    setUser(null)
    setStatus('unauthenticated')
  }

  const replaceUser = (nextUser: AuthUser) => {
    setUser(nextUser)
    setStatus('authenticated')
  }

  const refreshUser = async () => {
    const nextUser = await apiJson<AuthUser>('/api/users/me')
    replaceUser(nextUser)
  }

  const applyAuthResponse = (payload: AuthResponse) => {
    setStoredToken(payload.access_token)
    setUser(payload.user)
    setStatus('authenticated')
    setBootstrapStatus(prev => prev ? { ...prev, requires_setup: false, user_count: Math.max(prev.user_count, 1) } : { requires_setup: false, user_count: 1 })
  }

  const login = async ({ username, password }: LoginInput) => {
    const payload = await apiJson<AuthResponse>(
      '/api/users/authenticate',
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      },
      { auth: false },
    )
    applyAuthResponse(payload)
  }

  const createBootstrapUser = async ({ username, password, email, full_name }: BootstrapInput) => {
    await apiJson<AuthUser>(
      '/api/users',
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password, email: email || null, full_name: full_name || null, role: 'member', disabled: false }),
      },
      { auth: false },
    )
    await login({ username, password })
  }

  const loginAsGuest = async () => {
    const payload = await apiJson<AuthResponse>(
      '/api/guest/session',
      { method: 'POST' },
      { auth: false },
    )
    applyAuthResponse(payload)
  }

  useEffect(() => {
    let active = true

    const initialize = async () => {
      try {
        const nextBootstrapStatus = await apiJson<BootstrapStatus>('/api/users/bootstrap-status', {}, { auth: false })
        if (!active) return
        setBootstrapStatus(nextBootstrapStatus)
      } catch {
        if (!active) return
        setBootstrapStatus({ requires_setup: false, user_count: 0 })
      }

      // Pick up a one-time code returned by the OIDC callback redirect
      // and exchange it for a JWT. The real token never appears in URLs or logs.
      const params = new URLSearchParams(window.location.search)
      const oidcCode = params.get('oidc_code')
      if (oidcCode) {
        params.delete('oidc_code')
        const clean = params.toString()
        window.history.replaceState({}, '', window.location.pathname + (clean ? `?${clean}` : ''))
        try {
          const { access_token } = await apiJson<{ access_token: string }>(
            '/api/oidc/exchange',
            {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ code: oidcCode }),
            },
            { auth: false },
          )
          setStoredToken(access_token)
        } catch {
          // Code was invalid or expired — fall through to unauthenticated
        }
      }

      const token = getStoredToken()
      if (!token) {
        if (active) setStatus('unauthenticated')
        return
      }

      try {
        const nextUser = await apiJson<AuthUser>('/api/users/me')
        if (!active) return
        setUser(nextUser)
        setStatus('authenticated')
      } catch {
        if (!active) return
        logout()
      }
    }

    initialize()

    const handleExpired = () => {
      if (active) logout()
    }

    window.addEventListener(AUTH_EXPIRED_EVENT, handleExpired)
    return () => {
      active = false
      window.removeEventListener(AUTH_EXPIRED_EVENT, handleExpired)
    }
  }, [])

  return (
    <AuthContext.Provider
      value={{
        status,
        user,
        bootstrapStatus,
        isAdmin: user?.role === 'admin',
        login,
        createBootstrapUser,
        loginAsGuest,
        logout,
        refreshUser,
        replaceUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}