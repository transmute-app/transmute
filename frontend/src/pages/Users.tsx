import { useEffect, useState } from 'react'
import { useAuth, type AuthUser, type UserRole } from '../AuthContext'
import { useTranslation } from 'react-i18next'
import PasswordField from '../components/PasswordField'
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
  const { t } = useTranslation()
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
      setError(err instanceof Error ? err.message : t('users.loadFailed'))
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
      setMessage(t('users.created'))
      await loadUsers()
    } catch (err) {
      setError(err instanceof Error ? err.message : t('users.createFailed'))
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
      setMessage(t('users.updated', { username: updatedUser.username }))
    } catch (err) {
      setError(err instanceof Error ? err.message : t('users.updateFailed'))
    } finally {
      setSavingId(null)
    }
  }

  const handleDelete = async (userId: string) => {
    if (currentUser?.uuid === userId) {
      setError(t('users.deleteSelfBlocked'))
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
      setMessage(t('users.deleted'))
    } catch (err) {
      setError(err instanceof Error ? err.message : t('users.deleteFailed'))
    } finally {
      setDeletingId(null)
    }
  }

  return (
    <div className="min-h-full bg-gradient-to-br from-surface-dark to-surface-light p-8 pb-12">
      <div className="max-w-4xl mx-auto">
        <div className="flex justify-between items-center mb-6 min-h-[4rem]">
          <h1 className="text-3xl font-bold text-primary">{t('users.title')}</h1>
          <div className="rounded-lg border border-primary/20 bg-primary/10 px-4 py-2 text-sm text-primary-light">
            {t('users.usersConfigured', { count: users.length })}
          </div>
        </div>

        {message && <div className="p-3 bg-success/10 border border-success/40 rounded-lg text-sm text-green-200 mb-4">{message}</div>}
        {error && <div className="p-3 bg-primary/20 border border-primary rounded-lg text-primary-light text-sm mb-4">{error}</div>}

        <form onSubmit={handleCreate} className="grid gap-4 bg-surface-light rounded-xl p-6 mb-6 md:grid-cols-2">
          <div>
            <label className="mb-2 block text-sm font-medium text-text">
              {t('fields.username')}
              <span aria-hidden="true" className="text-red-500 text-lg font-semibold leading-none">*</span>
            </label>
            <input value={createDraft.username} onChange={event => setCreateDraft(prev => ({ ...prev, username: event.target.value }))} className="w-full rounded-lg border border-surface-light bg-surface-dark px-4 py-3 text-sm text-text outline-none focus:ring-2 focus:ring-primary/20" required />
          </div>
          <div>
            <label className="mb-2 block text-sm font-medium text-text">{t('fields.email')}</label>
            <input value={createDraft.email} onChange={event => setCreateDraft(prev => ({ ...prev, email: event.target.value }))} className="w-full rounded-lg border border-surface-light bg-surface-dark px-4 py-3 text-sm text-text outline-none focus:ring-2 focus:ring-primary/20" type="email" />
          </div>
          <div>
            <label className="mb-2 block text-sm font-medium text-text">{t('fields.fullName')}</label>
            <input value={createDraft.full_name} onChange={event => setCreateDraft(prev => ({ ...prev, full_name: event.target.value }))} className="w-full rounded-lg border border-surface-light bg-surface-dark px-4 py-3 text-sm text-text outline-none focus:ring-2 focus:ring-primary/20" />
          </div>
          <div>
            <label className="mb-2 block text-sm font-medium text-text">{t('fields.role')}</label>
            <select value={createDraft.role} onChange={event => setCreateDraft(prev => ({ ...prev, role: event.target.value as UserRole }))} className="w-full rounded-lg border border-surface-light bg-surface-dark px-4 py-3 text-sm text-text outline-none focus:ring-2 focus:ring-primary/20">
              <option value="member">{t('users.member')}</option>
              <option value="admin">{t('users.admin')}</option>
            </select>
          </div>
          <div>
            <label className="mb-2 block text-sm font-medium text-text">
              {t('fields.password')}
              <span aria-hidden="true" className="text-red-500 text-lg font-semibold leading-none">*</span>
            </label>
            <PasswordField value={createDraft.password} onChange={event => setCreateDraft(prev => ({ ...prev, password: event.target.value }))} inputClassName="rounded-lg border border-surface-light bg-surface-dark px-4 py-3 text-sm text-text outline-none focus:ring-2 focus:ring-primary/20" toggleButtonClassName="rounded-lg border border-surface-light bg-surface-dark px-4 text-text-muted transition hover:bg-primary/20 hover:text-primary-light focus:outline-none focus:ring-2 focus:ring-primary/20" required minLength={8} />
            <p className="mt-1 text-xs text-text-muted">{t('users.passwordMustBe8')}</p>
          </div>
          <div className="flex items-end gap-4 md:col-span-2">
            <label className="inline-flex items-center gap-3 text-sm text-text-muted">
              <input type="checkbox" checked={createDraft.disabled} onChange={event => setCreateDraft(prev => ({ ...prev, disabled: event.target.checked }))} className="h-4 w-4 rounded border-white/20 bg-surface-dark/60 text-primary" />
              {t('users.startDisabled')}
            </label>
            <button type="submit" disabled={creating} className="ml-auto bg-success hover:bg-success-dark text-white font-semibold py-2 px-8 rounded-lg transition duration-200 shadow-md hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed">
              {creating ? t('users.creating') : t('users.createUser')}
            </button>
          </div>
        </form>

        {loading ? (
          <p className="text-sm text-text-muted">{t('users.loadingUsers')}</p>
        ) : (
          <div className="space-y-4">
            {users.map(user => {
              const draft = drafts[user.uuid] ?? makeDraft(user)
              return (
                <section key={user.uuid} className="bg-surface-light rounded-xl p-6">
                  <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <h2 className="text-lg font-semibold text-text">{user.username}</h2>
                      <p className="text-sm text-text-muted">{t('users.uuid', { uuid: user.uuid })}</p>
                    </div>
                    <div className="flex items-center gap-3 text-sm">
                      <span className="rounded-full border border-primary/20 bg-primary/10 px-3 py-1 text-primary-light">{user.role}</span>
                      {user.disabled && <span className="rounded-full border border-primary/30 bg-primary/15 px-3 py-1 text-primary-light">{t('users.disabled')}</span>}
                    </div>
                  </div>

                  <div className="grid gap-4 md:grid-cols-2">
                    <label>
                      <span className="mb-2 block text-sm font-medium text-text">{t('fields.username')}</span>
                      <input value={draft.username} onChange={event => updateDraft(user.uuid, 'username', event.target.value)} className="w-full rounded-lg border border-surface-light bg-surface-dark px-4 py-3 text-sm text-text outline-none focus:ring-2 focus:ring-primary/20" />
                    </label>
                    <label>
                      <span className="mb-2 block text-sm font-medium text-text">{t('fields.email')}</span>
                      <input value={draft.email} onChange={event => updateDraft(user.uuid, 'email', event.target.value)} className="w-full rounded-lg border border-surface-light bg-surface-dark px-4 py-3 text-sm text-text outline-none focus:ring-2 focus:ring-primary/20" type="email" />
                    </label>
                    <label>
                      <span className="mb-2 block text-sm font-medium text-text">{t('fields.fullName')}</span>
                      <input value={draft.full_name} onChange={event => updateDraft(user.uuid, 'full_name', event.target.value)} className="w-full rounded-lg border border-surface-light bg-surface-dark px-4 py-3 text-sm text-text outline-none focus:ring-2 focus:ring-primary/20" />
                    </label>
                    {user.has_usable_password && (
                    <label className="min-w-0">
                      <span className="mb-2 block text-sm font-medium text-text">{t('fields.newPassword')}</span>
                      <PasswordField value={draft.password} onChange={event => updateDraft(user.uuid, 'password', event.target.value)} containerClassName="flex min-w-0 items-stretch gap-2" inputClassName="min-w-0 rounded-lg border border-surface-light bg-surface-dark px-4 py-3 text-sm text-text outline-none focus:ring-2 focus:ring-primary/20" toggleButtonClassName="shrink-0 rounded-lg border border-surface-light bg-surface-dark px-4 text-text-muted transition hover:bg-primary/20 hover:text-primary-light focus:outline-none focus:ring-2 focus:ring-primary/20" placeholder={t('users.passwordPlaceholder')} minLength={8} />
                      <p className="mt-1 text-xs text-text-muted">{t('users.passwordHint')}</p>
                    </label>
                    )}
                    <label>
                      <span className="mb-2 block text-sm font-medium text-text">{t('fields.role')}</span>
                      <select value={draft.role} onChange={event => updateDraft(user.uuid, 'role', event.target.value)} disabled={currentUser?.uuid === user.uuid} className={`w-full rounded-lg border border-surface-light bg-surface-dark px-4 py-3 text-sm text-text outline-none focus:ring-2 focus:ring-primary/20${currentUser?.uuid === user.uuid ? ' opacity-50 cursor-not-allowed' : ''}`} title={currentUser?.uuid === user.uuid ? t('users.cannotChangeOwnRole') : undefined}>
                        <option value="member">{t('users.member')}</option>
                        <option value="admin">{t('users.admin')}</option>
                      </select>
                    </label>
                    <div className="flex items-end">
                      <label className="inline-flex items-center gap-3 text-sm text-text-muted">
                        <input type="checkbox" checked={draft.disabled} onChange={event => updateDraft(user.uuid, 'disabled', event.target.checked)} disabled={currentUser?.uuid === user.uuid} className={`h-4 w-4 rounded border-white/20 bg-surface-dark/60 text-primary${currentUser?.uuid === user.uuid ? ' opacity-50 cursor-not-allowed' : ''}`} />
                        {t('users.disabled')}
                      </label>
                    </div>
                  </div>

                  <div className="mt-5 flex flex-wrap items-center justify-between gap-3">
                    <div className="text-sm text-text-muted">{currentUser?.uuid === user.uuid ? t('users.thisIsYou') : t('users.managedAccount')}</div>
                    <div className="flex gap-3">
                      <button type="button" onClick={() => handleDelete(user.uuid)} disabled={deletingId === user.uuid || currentUser?.uuid === user.uuid} className="bg-primary/20 hover:bg-primary/40 text-primary-light font-semibold py-2 px-6 rounded-lg transition duration-200 shadow-md hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed">
                        {deletingId === user.uuid ? t('users.deleting') : t('users.delete')}
                      </button>
                      <button type="button" onClick={() => handleSave(user.uuid)} disabled={savingId === user.uuid} className="bg-success hover:bg-success-dark text-white font-semibold py-2 px-6 rounded-lg transition duration-200 shadow-md hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed">
                        {savingId === user.uuid ? t('users.saving') : t('users.saveChanges')}
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