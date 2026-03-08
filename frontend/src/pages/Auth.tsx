import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { FaKey, FaUserPlus } from 'react-icons/fa6'
import { useAuth } from '../AuthContext'

function Auth() {
  const navigate = useNavigate()
  const location = useLocation()
  const { bootstrapStatus, login, createBootstrapUser } = useAuth()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [email, setEmail] = useState('')
  const [fullName, setFullName] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const returnTo = typeof location.state === 'object' && location.state && 'from' in location.state
    ? String(location.state.from)
    : '/'

  const requiresSetup = bootstrapStatus?.requires_setup ?? false

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
      setError(err instanceof Error ? err.message : 'Authentication failed')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(var(--color-primary),0.35),_transparent_38%),linear-gradient(135deg,_rgb(var(--color-surface-dark)),_rgb(var(--color-surface-light))_55%,_rgb(var(--color-surface-dark)))] px-6 py-10 text-text">
      <div className="mx-auto flex min-h-[calc(100vh-5rem)] max-w-xl items-center justify-center">
        <section className="w-full">
          <form onSubmit={handleSubmit} className="w-full rounded-[2rem] border border-white/10 bg-surface-dark/80 p-8 shadow-2xl backdrop-blur">
            <div className="mb-8 flex items-center gap-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/20 text-primary-light">
                {requiresSetup ? <FaUserPlus size={20} /> : <FaKey size={20} />}
              </div>
              <div>
                <h2 className="text-2xl font-bold text-text">{requiresSetup ? 'Create Admin' : 'Log In'}</h2>
                <p className="text-sm text-text-muted">{requiresSetup ? 'This account will become the initial administrator.' : 'Use your Transmute username and password.'}</p>
              </div>
            </div>

            <div className="space-y-4">
              <label className="block">
                <span className="mb-2 block text-sm font-medium text-text">Username</span>
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
                    <span className="mb-2 block text-sm font-medium text-text">Full name</span>
                    <input
                      value={fullName}
                      onChange={event => setFullName(event.target.value)}
                      className="w-full rounded-xl border border-white/10 bg-surface-light/70 px-4 py-3 text-text outline-none transition focus:border-primary/60 focus:ring-2 focus:ring-primary/20"
                      placeholder="Alex Operator"
                    />
                  </label>
                  <label className="block">
                    <span className="mb-2 block text-sm font-medium text-text">Email</span>
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
                <span className="mb-2 block text-sm font-medium text-text">Password</span>
                <input
                  value={password}
                  onChange={event => setPassword(event.target.value)}
                  className="w-full rounded-xl border border-white/10 bg-surface-light/70 px-4 py-3 text-text outline-none transition focus:border-primary/60 focus:ring-2 focus:ring-primary/20"
                  placeholder="••••••••"
                  type="password"
                  required
                  minLength={requiresSetup ? 8 : undefined}
                />
                {requiresSetup && <p className="mt-1 text-xs text-text-muted">Must be at least 8 characters.</p>}
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
              {submitting ? 'Working...' : requiresSetup ? 'Create Admin Account' : 'Sign In'}
            </button>
          </form>
        </section>
      </div>
    </div>
  )
}

export default Auth