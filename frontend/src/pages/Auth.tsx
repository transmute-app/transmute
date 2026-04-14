import { useEffect, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { FaKey, FaUserPlus, FaArrowUpRightFromSquare } from 'react-icons/fa6'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../AuthContext'
import { apiJson } from '../utils/api'
import PasswordField from '../components/PasswordField'

interface OidcConfig {
  enabled: boolean
  display_name: string
  allow_unauthenticated: boolean
  auto_launch: boolean
}

function Auth() {
  const navigate = useNavigate()
  const location = useLocation()
  const { bootstrapStatus, login, createBootstrapUser, loginAsGuest } = useAuth()
  const { t } = useTranslation()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [email, setEmail] = useState('')
  const [fullName, setFullName] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [oidcConfig, setOidcConfig] = useState<OidcConfig | null>(null)
  const [showLocalLogin, setShowLocalLogin] = useState(false)

  const requiresSetup = bootstrapStatus?.requires_setup ?? false

  useEffect(() => {
    apiJson<OidcConfig>('/api/oidc/config', {}, { auth: false })
      .then(setOidcConfig)
      .catch(() => setOidcConfig({ enabled: false, display_name: '', allow_unauthenticated: false, auto_launch: false }))
  }, [])

  const [suppressAutoLaunch] = useState(() => {
    if (sessionStorage.getItem('logged_out')) {
      sessionStorage.removeItem('logged_out')
      return true
    }
    return false
  })

  useEffect(() => {
    if (oidcConfig?.auto_launch && oidcConfig.enabled && !requiresSetup && !suppressAutoLaunch) {
      window.location.href = '/api/oidc/login'
    }
  }, [oidcConfig, requiresSetup, suppressAutoLaunch])

  const returnTo = typeof location.state === 'object' && location.state && 'from' in location.state
    ? String(location.state.from)
    : '/'

  // While config is loading or auto-launch redirect is pending, show nothing
  const autoLaunching = oidcConfig?.auto_launch && oidcConfig.enabled && !requiresSetup && !suppressAutoLaunch
  if (oidcConfig === null || autoLaunching) {
    return <div className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(var(--color-primary),0.35),_transparent_38%),linear-gradient(135deg,_rgb(var(--color-surface-dark)),_rgb(var(--color-surface-light))_55%,_rgb(var(--color-surface-dark)))]" />
  }

  // When OIDC is enabled and not in setup mode, default to showing the OIDC-primary view
  const oidcPrimary = !!oidcConfig?.enabled && !requiresSetup && !showLocalLogin

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setSubmitting(true)
    setError(null)

    try {
      if (requiresSetup) {
        await createBootstrapUser({ username, password, email, full_name: fullName })
      } else {
        await login({ username, password })
      }
      navigate(returnTo, { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : t('auth.authFailed'))
    } finally {
      setSubmitting(false)
    }
  }

  const handleGuestLogin = async () => {
    setSubmitting(true)
    setError(null)
    try {
      await loginAsGuest()
      navigate(returnTo, { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : t('auth.guestFailed'))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(var(--color-primary),0.35),_transparent_38%),linear-gradient(135deg,_rgb(var(--color-surface-dark)),_rgb(var(--color-surface-light))_55%,_rgb(var(--color-surface-dark)))] px-6 py-10 text-text">
      <div className="mx-auto flex min-h-[calc(100vh-5rem)] max-w-xl items-center justify-center">
        <section className="w-full">
          {oidcPrimary ? (
            /* ── OIDC-primary view ── */
            <div className="w-full rounded-[2rem] border border-white/10 bg-surface-dark/80 p-8 shadow-2xl backdrop-blur">
              <div className="mb-8 flex items-center gap-3">
                <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/20 text-primary-light">
                  <FaKey size={20} />
                </div>
                <div>
                  <h2 className="text-2xl font-bold text-text">{t('auth.logIn')}</h2>
                  <p className="text-sm text-text-muted">{t('auth.signInWithProvider', { provider: oidcConfig.display_name })}</p>
                </div>
              </div>

              {error && (
                <div className="mb-5 rounded-xl border border-primary/40 bg-primary/10 px-4 py-3 text-sm text-primary-light">
                  {error}
                </div>
              )}

              <a
                href="/api/oidc/login"
                className="flex w-full items-center justify-center gap-2 rounded-xl bg-primary px-5 py-3.5 font-semibold text-white transition hover:bg-primary-dark"
              >
                <FaArrowUpRightFromSquare size={14} />
                {t('auth.signInWith', { provider: oidcConfig.display_name })}
              </a>

              {/* Secondary options */}
              <div className="mt-6 flex items-center gap-3">
                <div className="h-px flex-1 bg-white/10" />
                <span className="text-xs text-text-muted">or</span>
                <div className="h-px flex-1 bg-white/10" />
              </div>
              <div className={`mt-4 flex gap-3 ${oidcConfig?.allow_unauthenticated ? 'flex-row' : 'flex-col'}`}>
                <button
                  type="button"
                  onClick={() => setShowLocalLogin(true)}
                  className="flex flex-1 items-center justify-center gap-2 rounded-xl border border-white/10 bg-surface-light/70 px-5 py-3.5 font-semibold text-text transition hover:border-primary/40 hover:bg-surface-light"
                >
                  {t('auth.useLocalAccount')}
                </button>
                {oidcConfig?.allow_unauthenticated && (
                  <button
                    type="button"
                    onClick={handleGuestLogin}
                    disabled={submitting}
                    className="flex flex-1 items-center justify-center gap-2 rounded-xl border border-white/10 bg-surface-light/70 px-5 py-3.5 font-semibold text-text transition hover:border-primary/40 hover:bg-surface-light disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {t('auth.useAsGuest')}
                  </button>
                )}
              </div>
            </div>
          ) : (
            /* ── Local login / bootstrap form ── */
            <form onSubmit={handleSubmit} className="w-full rounded-[2rem] border border-white/10 bg-surface-dark/80 p-8 shadow-2xl backdrop-blur">
              <div className="mb-8 flex items-center gap-3">
                <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/20 text-primary-light">
                  {requiresSetup ? <FaUserPlus size={20} /> : <FaKey size={20} />}
                </div>
                <div>
                  <h2 className="text-2xl font-bold text-text">{requiresSetup ? t('auth.createAdmin') : t('auth.logIn')}</h2>
                  <p className="text-sm text-text-muted">{requiresSetup ? t('auth.initialAdmin') : t('auth.useCredentials')}</p>
                </div>
              </div>

              <div className="space-y-4">
                <label className="block">
                  <span className="mb-2 block text-sm font-medium text-text">
                    {t('fields.username')}
                    <span aria-hidden="true" className="text-red-500 text-lg font-semibold leading-none">*</span>
                  </span>
                  <input
                    value={username}
                    onChange={event => setUsername(event.target.value)}
                    className="w-full rounded-xl border border-white/10 bg-surface-light/70 px-4 py-3 text-text outline-none transition focus:border-primary/60 focus:ring-2 focus:ring-primary/20"
                    placeholder="operator"
                    required
                  />
                </label>

                {requiresSetup && (
                  <>
                    <label className="block">
                      <span className="mb-2 block text-sm font-medium text-text">{t('fields.fullName')}</span>
                      <input
                        value={fullName}
                        onChange={event => setFullName(event.target.value)}
                        className="w-full rounded-xl border border-white/10 bg-surface-light/70 px-4 py-3 text-text outline-none transition focus:border-primary/60 focus:ring-2 focus:ring-primary/20"
                        placeholder="Alex Operator"
                      />
                    </label>
                    <label className="block">
                      <span className="mb-2 block text-sm font-medium text-text">{t('fields.email')}</span>
                      <input
                        value={email}
                        onChange={event => setEmail(event.target.value)}
                        className="w-full rounded-xl border border-white/10 bg-surface-light/70 px-4 py-3 text-text outline-none transition focus:border-primary/60 focus:ring-2 focus:ring-primary/20"
                        placeholder="alex@example.com"
                        type="email"
                      />
                    </label>
                  </>
                )}

                <label className="block">
                  <span className="mb-2 block text-sm font-medium text-text">
                    {t('fields.password')}
                    <span aria-hidden="true" className="text-red-500 text-lg font-semibold leading-none">*</span>
                  </span>
                  <PasswordField
                    value={password}
                    onChange={event => setPassword(event.target.value)}
                    inputClassName="rounded-xl border border-white/10 bg-surface-light/70 px-4 py-3 text-text outline-none transition focus:border-primary/60 focus:ring-2 focus:ring-primary/20"
                    toggleButtonClassName="rounded-xl border border-white/10 bg-surface-light/70 px-4 text-text-muted transition hover:text-text focus:outline-none focus:ring-2 focus:ring-primary/20"
                    placeholder="••••••••"
                    required
                    minLength={requiresSetup ? 8 : undefined}
                  />
                  {requiresSetup && <p className="mt-1 text-xs text-text-muted">{t('auth.passwordMin8')}</p>}
                </label>
              </div>

              {error && (
                <div className="mt-5 rounded-xl border border-primary/40 bg-primary/10 px-4 py-3 text-sm text-primary-light">
                  {error}
                </div>
              )}

              <button
                type="submit"
                disabled={submitting}
                className="mt-6 w-full rounded-xl bg-primary px-5 py-3.5 font-semibold text-white transition hover:bg-primary-dark disabled:cursor-not-allowed disabled:opacity-60"
              >
                {submitting ? t('auth.working') : requiresSetup ? t('auth.createAdminAccount') : t('auth.signIn')}
              </button>

              {/* Secondary options for local login view */}
              {(oidcConfig?.enabled || (oidcConfig?.allow_unauthenticated && !requiresSetup)) && (
                <>
                  <div className="mt-6 flex items-center gap-3">
                    <div className="h-px flex-1 bg-white/10" />
                    <span className="text-xs text-text-muted">{t('auth.or')}</span>
                    <div className="h-px flex-1 bg-white/10" />
                  </div>
                  <div className={`mt-4 flex gap-3 ${oidcConfig?.enabled && oidcConfig?.allow_unauthenticated ? 'flex-row' : 'flex-col'}`}>
                    {oidcConfig?.enabled && (
                      <a
                        href="/api/oidc/login"
                        className="flex flex-1 items-center justify-center gap-2 rounded-xl border border-white/10 bg-surface-light/70 px-5 py-3.5 font-semibold text-text transition hover:border-primary/40 hover:bg-surface-light"
                      >
                        <FaArrowUpRightFromSquare size={14} />
                        {requiresSetup ? t('auth.bootstrapWith', { provider: oidcConfig.display_name }) : t('auth.signInWith', { provider: oidcConfig.display_name })}
                      </a>
                    )}
                    {oidcConfig?.allow_unauthenticated && !requiresSetup && (
                      <button
                        type="button"
                        onClick={handleGuestLogin}
                        disabled={submitting}
                        className="flex flex-1 items-center justify-center gap-2 rounded-xl border border-white/10 bg-surface-light/70 px-5 py-3.5 font-semibold text-text transition hover:border-primary/40 hover:bg-surface-light disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        {t('auth.useAsGuest')}
                      </button>
                    )}
                  </div>
                </>
              )}
            </form>
          )}
        </section>
      </div>
    </div>
  )
}

export default Auth