import { useEffect, useState } from 'react'
import { FaCopy, FaKey, FaPlus, FaTrash } from 'react-icons/fa6'
import { useAuth } from '../AuthContext'
import { apiJson } from '../utils/api'

interface ApiKey {
  id: string
  name: string
  prefix: string
  created_at: string | null
}

interface ApiKeyCreated extends ApiKey {
  raw_key: string
}

function Account() {
  const { user, replaceUser } = useAuth()
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [fullName, setFullName] = useState('')
  const [password, setPassword] = useState('')
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  // API key state
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([])
  const [newKeyName, setNewKeyName] = useState('')
  const [creatingKey, setCreatingKey] = useState(false)
  const [newlyCreatedKey, setNewlyCreatedKey] = useState<string | null>(null)
  const [keyError, setKeyError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    if (!user) return
    setUsername(user.username)
    setEmail(user.email ?? '')
    setFullName(user.full_name ?? '')
  }, [user])

  // Fetch API keys
  useEffect(() => {
    loadApiKeys()
  }, [])

  const loadApiKeys = async () => {
    try {
      const data = await apiJson<{ api_keys: ApiKey[] }>('/api/api-keys')
      setApiKeys(data.api_keys)
    } catch {
      // silently fail on initial load
    }
  }

  const handleCreateKey = async () => {
    if (!newKeyName.trim()) return
    setCreatingKey(true)
    setKeyError(null)
    setNewlyCreatedKey(null)
    try {
      const data = await apiJson<ApiKeyCreated>('/api/api-keys', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: newKeyName.trim() }),
      })
      setNewlyCreatedKey(data.raw_key)
      setNewKeyName('')
      loadApiKeys()
    } catch (err) {
      setKeyError(err instanceof Error ? err.message : 'Failed to create API key')
    } finally {
      setCreatingKey(false)
    }
  }

  const handleDeleteKey = async (id: string) => {
    try {
      await apiJson(`/api/api-keys/${id}`, { method: 'DELETE' })
      setApiKeys(prev => prev.filter(k => k.id !== id))
    } catch (err) {
      setKeyError(err instanceof Error ? err.message : 'Failed to delete API key')
    }
  }

  const handleCopyKey = async (key: string) => {
    await navigator.clipboard.writeText(key)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  if (!user) return null

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setSaving(true)
    setMessage(null)
    setError(null)

    try {
      const updatedUser = await apiJson<typeof user>('/api/users/me', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username,
          email: email || null,
          full_name: fullName || null,
          ...(password ? { password } : {}),
        }),
      })
      replaceUser(updatedUser)
      setPassword('')
      setMessage('Account updated successfully.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update account')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="min-h-full bg-gradient-to-br from-surface-dark to-surface-light p-8 pb-12">
      <div className="max-w-4xl mx-auto">
        <div className="flex justify-between items-center mb-6 min-h-[4rem]">
          <div>
            <h1 className="text-3xl font-bold text-primary">My Account</h1>
            <p className="mt-1 text-text-muted text-sm">Update your username, contact fields, and password. Your role stays server-controlled.</p>
          </div>
          <div className="rounded-lg border border-primary/20 bg-primary/10 px-4 py-2 text-sm text-primary-light">
            Signed in as <span className="font-semibold">{user.role}</span>
          </div>
        </div>

        {message && <div className="p-3 bg-success/10 border border-success/40 rounded-lg text-sm text-green-200 mb-4">{message}</div>}
        {error && <div className="p-3 bg-primary/20 border border-primary rounded-lg text-primary-light text-sm mb-4">{error}</div>}

        <form onSubmit={handleSubmit} className="bg-surface-light rounded-xl p-6">
          <div className="grid gap-4 md:grid-cols-2">
            <label className="block">
              <span className="mb-2 block text-sm font-medium text-text">Username</span>
              <input value={username} onChange={event => setUsername(event.target.value)} className="w-full rounded-lg border border-surface-light bg-surface-dark px-4 py-3 text-sm text-text outline-none focus:ring-2 focus:ring-primary/20" required />
            </label>
            <label className="block">
              <span className="mb-2 block text-sm font-medium text-text">Email</span>
              <input value={email} onChange={event => setEmail(event.target.value)} className="w-full rounded-lg border border-surface-light bg-surface-dark px-4 py-3 text-sm text-text outline-none focus:ring-2 focus:ring-primary/20" type="email" />
            </label>
            <label className="block md:col-span-2">
              <span className="mb-2 block text-sm font-medium text-text">Full name</span>
              <input value={fullName} onChange={event => setFullName(event.target.value)} className="w-full rounded-lg border border-surface-light bg-surface-dark px-4 py-3 text-sm text-text outline-none focus:ring-2 focus:ring-primary/20" />
            </label>
            <label className="block md:col-span-2">
              <span className="mb-2 block text-sm font-medium text-text">New password</span>
              <input value={password} onChange={event => setPassword(event.target.value)} className="w-full rounded-lg border border-surface-light bg-surface-dark px-4 py-3 text-sm text-text outline-none focus:ring-2 focus:ring-primary/20" type="password" placeholder="Leave blank to keep the current password" minLength={8} />
              <p className="mt-1 text-xs text-text-muted">Min 8 characters if changing.</p>
            </label>
          </div>

          <div className="mt-6 flex items-center justify-between gap-4">
            <div className="text-sm text-text-muted">Role: <span className="font-semibold text-text">{user.role}</span></div>
            <button type="submit" disabled={saving} className="bg-success hover:bg-success-dark text-white font-semibold py-2 px-8 rounded-lg transition duration-200 shadow-md hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed">
              {saving ? 'Saving...' : 'Save Account'}
            </button>
          </div>
        </form>

        {/* API Keys Section */}
        <div className="mt-8 bg-surface-light rounded-xl p-6">
          <div className="flex items-center gap-2 mb-4">
            <FaKey className="text-primary" />
            <h2 className="text-xl font-bold text-text">API Keys</h2>
          </div>
          <p className="text-sm text-text-muted mb-4">
            Use API keys to authenticate with the API without a password. Pass the key as a Bearer token.
          </p>

          {keyError && <div className="p-3 bg-primary/20 border border-primary rounded-lg text-primary-light text-sm mb-4">{keyError}</div>}

          {/* Newly created key banner */}
          {newlyCreatedKey && (
            <div className="p-4 bg-success/10 border border-success/40 rounded-lg mb-4">
              <p className="text-sm font-semibold text-green-200 mb-2">Key created! Copy it now — you won't see it again.</p>
              <div className="flex items-center gap-2">
                <code className="flex-1 bg-surface-dark rounded px-3 py-2 text-sm text-text font-mono break-all select-all">{newlyCreatedKey}</code>
                <button onClick={() => handleCopyKey(newlyCreatedKey)} className="shrink-0 p-2 rounded-lg bg-surface-dark hover:bg-primary/20 text-text-muted hover:text-primary transition" title="Copy">
                  <FaCopy />
                </button>
              </div>
              {copied && <p className="text-xs text-green-300 mt-1">Copied!</p>}
            </div>
          )}

          {/* Create new key */}
          <div className="flex gap-2 mb-4">
            <input
              value={newKeyName}
              onChange={e => setNewKeyName(e.target.value)}
              placeholder="Key name (e.g. CI Pipeline)"
              className="flex-1 rounded-lg border border-surface-light bg-surface-dark px-4 py-2 text-sm text-text outline-none focus:ring-2 focus:ring-primary/20"
              onKeyDown={e => e.key === 'Enter' && handleCreateKey()}
            />
            <button onClick={handleCreateKey} disabled={creatingKey || !newKeyName.trim()} className="flex items-center gap-2 bg-success hover:bg-success-dark text-white font-semibold py-2 px-4 rounded-lg transition duration-200 shadow-md hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed text-sm">
              <FaPlus className="text-xs" />
              {creatingKey ? 'Creating...' : 'Create Key'}
            </button>
          </div>

          {/* Keys list */}
          {apiKeys.length === 0 ? (
            <p className="text-sm text-text-muted italic">No API keys yet.</p>
          ) : (
            <div className="space-y-2">
              {apiKeys.map(key => (
                <div key={key.id} className="flex items-center justify-between bg-surface-dark rounded-lg px-4 py-3">
                  <div>
                    <span className="text-sm font-medium text-text">{key.name}</span>
                    <span className="ml-3 text-xs text-text-muted font-mono">{key.prefix}...</span>
                    {key.created_at && <span className="ml-3 text-xs text-text-muted">{new Date(key.created_at).toLocaleDateString()}</span>}
                  </div>
                  <button onClick={() => handleDeleteKey(key.id)} className="p-2 rounded-lg hover:bg-primary/20 text-text-muted hover:text-primary-light transition" title="Delete key">
                    <FaTrash className="text-sm" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default Account