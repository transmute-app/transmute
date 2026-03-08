import { useEffect, useState } from 'react'
import { useAuth, type AuthUser, type UserRole } from '../AuthContext'
import { apiJson } from '../utils/api'

interface UserDraft {
  username: string
  email: string
  full_name: string
  role: UserRole
  disabled: boolean
  password: string
}

interface CreateDraft extends UserDraft {}

const EMPTY_CREATE_DRAFT: CreateDraft = {
  username: '',
  email: '',
  full_name: '',
  role: 'member',
  disabled: false,
  password: '',
}

function makeDraft(user: AuthUser): UserDraft {
  return {
    username: user.username,
    email: user.email ?? '',
    full_name: user.full_name ?? '',
    role: user.role,
    disabled: user.disabled,
    password: '',
  }
}

function Users() {
  const { user: currentUser, replaceUser } = useAuth()
  const [users, setUsers] = useState<AuthUser[]>([])
  const [drafts, setDrafts] = useState<Record<string, UserDraft>>({})
  const [createDraft, setCreateDraft] = useState<CreateDraft>(EMPTY_CREATE_DRAFT)
  const [loading, setLoading] = useState(true)
  const [savingId, setSavingId] = useState<string | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  const syncDrafts = (nextUsers: AuthUser[]) => {
    setDrafts(Object.fromEntries(nextUsers.map(user => [user.uuid, makeDraft(user)])))
  }

  const loadUsers = async () => {
    setLoading(true)
    setError(null)
    try {
      const payload = await apiJson<{ users: AuthUser[] }>('/api/users')
      setUsers(payload.users)
      syncDrafts(payload.users)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load users')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadUsers()
  }, [])

  const updateDraft = (userId: string, field: keyof UserDraft, value: string | boolean) => {
    setDrafts(prev => ({
      ...prev,
      [userId]: {
        ...prev[userId],
        [field]: value,
      },
    }))
  }

  const handleCreate = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setCreating(true)
    setError(null)
    setMessage(null)
    try {
      await apiJson<AuthUser>('/api/users', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username: createDraft.username,
          email: createDraft.email || null,
          full_name: createDraft.full_name || null,
          password: createDraft.password,
          role: createDraft.role,
          disabled: createDraft.disabled,
        }),
      })
      setCreateDraft(EMPTY_CREATE_DRAFT)
      setMessage('User created successfully.')
      await loadUsers()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create user')
    } finally {
      setCreating(false)
    }
  }

  const handleSave = async (userId: string) => {
    const draft = drafts[userId]
    if (!draft) return
    setSavingId(userId)
    setError(null)
    setMessage(null)
    try {
      const updatedUser = await apiJson<AuthUser>(`/api/users/${encodeURIComponent(userId)}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username: draft.username,
          email: draft.email || null,
          full_name: draft.full_name || null,
          role: draft.role,
          disabled: draft.disabled,
          ...(draft.password ? { password: draft.password } : {}),
        }),
      })

      setUsers(prev => prev.map(user => (user.uuid === userId ? updatedUser : user)))
      setDrafts(prev => ({ ...prev, [userId]: makeDraft(updatedUser) }))
      if (currentUser?.uuid === userId) {
        replaceUser(updatedUser)
      }
      setMessage(`Updated ${updatedUser.username}.`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update user')
    } finally {
      setSavingId(null)
    }
  }

  const handleDelete = async (userId: string) => {
    if (currentUser?.uuid === userId) {
      setError('Deleting the currently signed-in admin from this screen is blocked.')
      return
    }
    setDeletingId(userId)
    setError(null)
    setMessage(null)
    try {
      await apiJson<{ message: string }>(`/api/users/${encodeURIComponent(userId)}`, { method: 'DELETE' })
      const nextUsers = users.filter(user => user.uuid !== userId)
      setUsers(nextUsers)
      syncDrafts(nextUsers)
      setMessage('User deleted successfully.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete user')
    } finally {
      setDeletingId(null)
    }
  }

  return (
    <div className="min-h-full bg-gradient-to-br from-surface-dark to-surface-light p-8 pb-12">
      <div className="max-w-4xl mx-auto">
        <div className="flex justify-between items-center mb-6 min-h-[4rem]">
          <div>
            <h1 className="text-3xl font-bold text-primary">User Management</h1>
            <p className="mt-1 text-text-muted text-sm">Create accounts, rotate credentials, update roles, and disable access.</p>
          </div>
          <div className="rounded-lg border border-primary/20 bg-primary/10 px-4 py-2 text-sm text-primary-light">
            {users.length} user{users.length === 1 ? '' : 's'} configured
          </div>
        </div>

        {message && <div className="p-3 bg-success/10 border border-success/40 rounded-lg text-sm text-green-200 mb-4">{message}</div>}
        {error && <div className="p-3 bg-primary/20 border border-primary rounded-lg text-primary-light text-sm mb-4">{error}</div>}

        <form onSubmit={handleCreate} className="grid gap-4 bg-surface-light rounded-xl p-6 mb-6 md:grid-cols-2">
          <div>
            <label className="mb-2 block text-sm font-medium text-text">Username</label>
            <input value={createDraft.username} onChange={event => setCreateDraft(prev => ({ ...prev, username: event.target.value }))} className="w-full rounded-lg border border-surface-light bg-surface-dark px-4 py-3 text-sm text-text outline-none focus:ring-2 focus:ring-primary/20" required />
          </div>
          <div>
            <label className="mb-2 block text-sm font-medium text-text">Email</label>
            <input value={createDraft.email} onChange={event => setCreateDraft(prev => ({ ...prev, email: event.target.value }))} className="w-full rounded-lg border border-surface-light bg-surface-dark px-4 py-3 text-sm text-text outline-none focus:ring-2 focus:ring-primary/20" type="email" />
          </div>
          <div>
            <label className="mb-2 block text-sm font-medium text-text">Full name</label>
            <input value={createDraft.full_name} onChange={event => setCreateDraft(prev => ({ ...prev, full_name: event.target.value }))} className="w-full rounded-lg border border-surface-light bg-surface-dark px-4 py-3 text-sm text-text outline-none focus:ring-2 focus:ring-primary/20" />
          </div>
          <div>
            <label className="mb-2 block text-sm font-medium text-text">Role</label>
            <select value={createDraft.role} onChange={event => setCreateDraft(prev => ({ ...prev, role: event.target.value as UserRole }))} className="w-full rounded-lg border border-surface-light bg-surface-dark px-4 py-3 text-sm text-text outline-none focus:ring-2 focus:ring-primary/20">
              <option value="member">Member</option>
              <option value="admin">Admin</option>
            </select>
          </div>
          <div>
            <label className="mb-2 block text-sm font-medium text-text">Password</label>
            <input value={createDraft.password} onChange={event => setCreateDraft(prev => ({ ...prev, password: event.target.value }))} className="w-full rounded-lg border border-surface-light bg-surface-dark px-4 py-3 text-sm text-text outline-none focus:ring-2 focus:ring-primary/20" type="password" required minLength={8} />
            <p className="mt-1 text-xs text-text-muted">Must be at least 8 characters.</p>
          </div>
          <div className="flex items-end gap-4 md:col-span-2">
            <label className="inline-flex items-center gap-3 text-sm text-text-muted">
              <input type="checkbox" checked={createDraft.disabled} onChange={event => setCreateDraft(prev => ({ ...prev, disabled: event.target.checked }))} className="h-4 w-4 rounded border-white/20 bg-surface-dark/60 text-primary" />
              Start disabled
            </label>
            <button type="submit" disabled={creating} className="ml-auto bg-success hover:bg-success-dark text-white font-semibold py-2 px-8 rounded-lg transition duration-200 shadow-md hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed">
              {creating ? 'Creating...' : 'Create User'}
            </button>
          </div>
        </form>

        {loading ? (
          <p className="text-sm text-text-muted">Loading users...</p>
        ) : (
          <div className="space-y-4">
            {users.map(user => {
              const draft = drafts[user.uuid] ?? makeDraft(user)
              return (
                <section key={user.uuid} className="bg-surface-light rounded-xl p-6">
                  <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <h2 className="text-lg font-semibold text-text">{user.username}</h2>
                      <p className="text-sm text-text-muted">UUID: {user.uuid}</p>
                    </div>
                    <div className="flex items-center gap-3 text-sm">
                      <span className="rounded-full border border-primary/20 bg-primary/10 px-3 py-1 text-primary-light">{user.role}</span>
                      {user.disabled && <span className="rounded-full border border-primary/30 bg-primary/15 px-3 py-1 text-primary-light">Disabled</span>}
                    </div>
                  </div>

                  <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                    <label>
                      <span className="mb-2 block text-sm font-medium text-text">Username</span>
                      <input value={draft.username} onChange={event => updateDraft(user.uuid, 'username', event.target.value)} className="w-full rounded-lg border border-surface-light bg-surface-dark px-4 py-3 text-sm text-text outline-none focus:ring-2 focus:ring-primary/20" />
                    </label>
                    <label>
                      <span className="mb-2 block text-sm font-medium text-text">Email</span>
                      <input value={draft.email} onChange={event => updateDraft(user.uuid, 'email', event.target.value)} className="w-full rounded-lg border border-surface-light bg-surface-dark px-4 py-3 text-sm text-text outline-none focus:ring-2 focus:ring-primary/20" type="email" />
                    </label>
                    <label>
                      <span className="mb-2 block text-sm font-medium text-text">Full name</span>
                      <input value={draft.full_name} onChange={event => updateDraft(user.uuid, 'full_name', event.target.value)} className="w-full rounded-lg border border-surface-light bg-surface-dark px-4 py-3 text-sm text-text outline-none focus:ring-2 focus:ring-primary/20" />
                    </label>
                    <label>
                      <span className="mb-2 block text-sm font-medium text-text">New password</span>
                      <input value={draft.password} onChange={event => updateDraft(user.uuid, 'password', event.target.value)} className="w-full rounded-lg border border-surface-light bg-surface-dark px-4 py-3 text-sm text-text outline-none focus:ring-2 focus:ring-primary/20" type="password" placeholder="Leave blank to keep current" minLength={8} />
                      <p className="mt-1 text-xs text-text-muted">Min 8 characters if changing.</p>
                    </label>
                    <label>
                      <span className="mb-2 block text-sm font-medium text-text">Role</span>
                      <select value={draft.role} onChange={event => updateDraft(user.uuid, 'role', event.target.value)} disabled={currentUser?.uuid === user.uuid} className={`w-full rounded-lg border border-surface-light bg-surface-dark px-4 py-3 text-sm text-text outline-none focus:ring-2 focus:ring-primary/20${currentUser?.uuid === user.uuid ? ' opacity-50 cursor-not-allowed' : ''}`} title={currentUser?.uuid === user.uuid ? 'You cannot change your own role' : undefined}>
                        <option value="member">Member</option>
                        <option value="admin">Admin</option>
                      </select>
                    </label>
                    <div className="flex items-end">
                      <label className="inline-flex items-center gap-3 text-sm text-text-muted">
                        <input type="checkbox" checked={draft.disabled} onChange={event => updateDraft(user.uuid, 'disabled', event.target.checked)} disabled={currentUser?.uuid === user.uuid} className={`h-4 w-4 rounded border-white/20 bg-surface-dark/60 text-primary${currentUser?.uuid === user.uuid ? ' opacity-50 cursor-not-allowed' : ''}`} />
                        Disabled
                      </label>
                    </div>
                  </div>

                  <div className="mt-5 flex flex-wrap items-center justify-between gap-3">
                    <div className="text-sm text-text-muted">{currentUser?.uuid === user.uuid ? 'This is your current account.' : 'Managed account.'}</div>
                    <div className="flex gap-3">
                      <button type="button" onClick={() => handleDelete(user.uuid)} disabled={deletingId === user.uuid || currentUser?.uuid === user.uuid} className="bg-primary/20 hover:bg-primary/40 text-primary-light font-semibold py-2 px-6 rounded-lg transition duration-200 shadow-md hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed">
                        {deletingId === user.uuid ? 'Deleting...' : 'Delete'}
                      </button>
                      <button type="button" onClick={() => handleSave(user.uuid)} disabled={savingId === user.uuid} className="bg-success hover:bg-success-dark text-white font-semibold py-2 px-6 rounded-lg transition duration-200 shadow-md hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed">
                        {savingId === user.uuid ? 'Saving...' : 'Save Changes'}
                      </button>
                    </div>
                  </div>
                </section>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}

export default Users