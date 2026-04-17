import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { apiJson } from '../utils/api'

interface UserStats {
  user_uuid: string
  username: string
  files_uploaded: number
  conversions: number
  storage_bytes: number
}

interface StatsData {
  total_files_uploaded: number
  total_conversions: number
  total_storage_bytes: number
  users: UserStats[]
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1)
  const value = bytes / Math.pow(1024, i)
  return `${value % 1 === 0 ? value : value.toFixed(1)} ${units[i]}`
}

function Stats() {
  const [stats, setStats] = useState<StatsData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const { t } = useTranslation()

  useEffect(() => {
    apiJson<StatsData>('/api/stats')
      .then(setStats)
      .catch(err => setError(err instanceof Error ? err.message : t('stats.loadFailed')))
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-surface-dark to-surface-light text-text-muted">
        <p className="text-sm uppercase tracking-[0.2em]">{t('stats.loadingStats')}</p>
      </div>
    )
  }

  if (error || !stats) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-surface-dark to-surface-light">
        <p className="text-sm text-primary-light">{error ?? t('stats.noDataAvailable')}</p>
      </div>
    )
  }

  const maxBytes = Math.max(...stats.users.map(u => u.storage_bytes), 1)
  const sortedByStorage = [...stats.users].sort((a, b) => b.storage_bytes - a.storage_bytes)

  return (
    <div className="min-h-full bg-gradient-to-br from-surface-dark to-surface-light p-8 pb-12">
      <div className="max-w-4xl mx-auto">
        <div className="flex justify-between items-center mb-6 min-h-[4rem]">
          <h1 className="text-3xl font-bold text-primary">{t('stats.title')}</h1>
        </div>

        <div className="mb-6 rounded-xl border border-surface-light bg-surface-light/50 px-4 py-3">
          <p className="text-sm text-text-muted">{t('stats.snapshotNotice')}</p>
        </div>

        {/* Summary cards */}
        <div className="grid gap-4 sm:grid-cols-3 mb-8">
          <div className="rounded-xl border border-surface-light bg-surface-light/70 p-5">
            <p className="text-xs uppercase tracking-[0.15em] text-text-muted">{t('stats.currentUploadedFiles')}</p>
            <p className="mt-2 text-2xl font-bold text-text">{stats.total_files_uploaded.toLocaleString()}</p>
          </div>
          <div className="rounded-xl border border-surface-light bg-surface-light/70 p-5">
            <p className="text-xs uppercase tracking-[0.15em] text-text-muted">{t('stats.currentConvertedFiles')}</p>
            <p className="mt-2 text-2xl font-bold text-text">{stats.total_conversions.toLocaleString()}</p>
          </div>
          <div className="rounded-xl border border-surface-light bg-surface-light/70 p-5">
            <p className="text-xs uppercase tracking-[0.15em] text-text-muted">{t('stats.storageInUse')}</p>
            <p className="mt-2 text-2xl font-bold text-text">{formatBytes(stats.total_storage_bytes)}</p>
          </div>
        </div>

        {/* Storage bar chart */}
        <div className="rounded-xl border border-surface-light bg-surface-light/70 p-6 mb-8">
          <h2 className="text-lg font-semibold text-text mb-4">{t('stats.storageByUser')}</h2>
          {sortedByStorage.length === 0 ? (
            <p className="text-sm text-text-muted">{t('stats.noData')}</p>
          ) : (
            <div className="space-y-3">
              {sortedByStorage.map(user => {
                const pct = maxBytes > 0 ? (user.storage_bytes / maxBytes) * 100 : 0
                return (
                  <div key={user.user_uuid} className="flex items-center gap-3">
                    <span className="w-28 shrink-0 truncate text-sm text-text" title={user.username}>
                      {user.username}
                    </span>
                    <div className="relative flex-1 h-7 rounded-lg bg-surface-dark overflow-hidden">
                      <div
                        className="h-full rounded-lg bg-primary/70 transition-all duration-500"
                        style={{ width: `${Math.max(pct, 0.5)}%` }}
                      />
                      <span className="absolute inset-y-0 right-2 flex items-center text-xs font-medium text-text-muted">
                        {formatBytes(user.storage_bytes)}
                      </span>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {/* User activity table */}
        <div className="rounded-xl border border-surface-light bg-surface-light/70 p-6">
          <h2 className="text-lg font-semibold text-text mb-4">{t('stats.activityByUser')}</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm text-left">
              <thead>
                <tr className="border-b border-surface-dark text-text-muted uppercase text-xs tracking-wider">
                  <th className="py-3 pr-4">{t('stats.user')}</th>
                  <th className="py-3 px-4 text-right">{t('stats.uploads')}</th>
                  <th className="py-3 px-4 text-right">{t('stats.conversions')}</th>
                  <th className="py-3 pl-4 text-right">{t('stats.storage')}</th>
                </tr>
              </thead>
              <tbody>
                {sortedByStorage.map(user => (
                  <tr key={user.user_uuid} className="border-b border-surface-dark/50 last:border-0">
                    <td className="py-3 pr-4 font-medium text-text">{user.username}</td>
                    <td className="py-3 px-4 text-right text-text-muted">{user.files_uploaded.toLocaleString()}</td>
                    <td className="py-3 px-4 text-right text-text-muted">{user.conversions.toLocaleString()}</td>
                    <td className="py-3 pl-4 text-right text-text-muted">{formatBytes(user.storage_bytes)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  )
}

export default Stats
