import { useCallback, useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { FaBan, FaDownload, FaTrash } from 'react-icons/fa'
import {
  cancelJob,
  downloadJobOutput,
  isTerminalJobStatus,
  listJobs,
  type ConversionJob,
  type ConversionJobStatus,
} from '../utils/jobs'
import { downloadBlob } from '../utils/download'
import { stripExtension } from '../utils/filename'
import { ApiError } from '../utils/api'

const POLL_INTERVAL_MS = 2500

function formatBytes(bytes: number | null | undefined): string {
  if (!bytes && bytes !== 0) return ''
  if (bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1)
  const value = bytes / Math.pow(1024, i)
  return `${value % 1 === 0 ? value : value.toFixed(1)} ${units[i]}`
}

function formatTimestamp(value: string | null | undefined): string {
  if (!value) return ''
  // Backend returns SQLite timestamps in UTC without TZ; treat as UTC.
  const normalized = value.includes('T') ? value : value.replace(' ', 'T') + 'Z'
  const date = new Date(normalized)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString()
}

const STATUS_BADGE_CLASS: Record<ConversionJobStatus, string> = {
  queued: 'bg-surface-light text-text-muted border-text-muted/30',
  running: 'bg-primary/15 text-primary-light border-primary/40',
  completed: 'bg-success/15 text-success border-success/40',
  failed: 'bg-primary/20 text-primary-light border-primary/50',
  cancelled: 'bg-surface-light text-text-muted border-text-muted/30',
}

function jobsHaveActiveWork(jobs: ConversionJob[]): boolean {
  return jobs.some(j => !isTerminalJobStatus(j.status))
}

function Queue() {
  const { t } = useTranslation()
  const [jobs, setJobs] = useState<ConversionJob[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [busyJobId, setBusyJobId] = useState<string | null>(null)
  const isMountedRef = useRef(true)

  useEffect(() => {
    isMountedRef.current = true
    return () => {
      isMountedRef.current = false
    }
  }, [])

  const refresh = useCallback(async (): Promise<ConversionJob[] | null> => {
    try {
      const next = await listJobs()
      if (!isMountedRef.current) return null
      setJobs(next)
      setError(null)
      return next
    } catch (err) {
      if (!isMountedRef.current) return null
      const message = err instanceof Error ? err.message : t('queue.loadFailed')
      setError(message)
      return null
    }
  }, [t])

  // Initial load.
  useEffect(() => {
    let cancelled = false
    ;(async () => {
      await refresh()
      if (!cancelled && isMountedRef.current) setLoading(false)
    })()
    return () => {
      cancelled = true
    }
  }, [refresh])

  // Poll while any job is active. The interval restarts whenever activity changes.
  const hasActiveWork = jobsHaveActiveWork(jobs)
  useEffect(() => {
    if (!hasActiveWork) return
    const handle = window.setInterval(() => {
      void refresh()
    }, POLL_INTERVAL_MS)
    return () => window.clearInterval(handle)
  }, [hasActiveWork, refresh])

  const handleCancel = async (job: ConversionJob) => {
    setBusyJobId(job.id)
    try {
      const updated = await cancelJob(job.id)
      if (!isMountedRef.current) return
      setJobs(prev => prev.map(j => (j.id === updated.id ? updated : j)))
    } catch (err) {
      if (!isMountedRef.current) return
      const message = err instanceof Error ? err.message : t('queue.cancelFailed')
      setError(message)
    } finally {
      if (isMountedRef.current) setBusyJobId(null)
    }
  }

  const handleDownload = async (job: ConversionJob) => {
    setBusyJobId(job.id)
    try {
      const blob = await downloadJobOutput(job)
      const base = stripExtension(job.source_filename || 'download')
      const ext = job.output_format.startsWith('.') ? job.output_format : `.${job.output_format}`
      downloadBlob(blob, `${base}${ext}`)
    } catch (err) {
      if (!isMountedRef.current) return
      const detail = err instanceof ApiError ? err.detail : err instanceof Error ? err.message : ''
      setError(detail || t('queue.downloadFailed'))
    } finally {
      if (isMountedRef.current) setBusyJobId(null)
    }
  }

  return (
    <div className="min-h-full bg-gradient-to-br from-surface-dark to-surface-light p-8 pb-12">
      <div className="max-w-5xl mx-auto">
        <div className="flex justify-between items-center mb-6 min-h-[4rem]">
          <h1 className="text-3xl font-bold text-primary">{t('queue.title')}</h1>
          {hasActiveWork && (
            <span className="text-xs uppercase tracking-[0.18em] text-text-muted">
              {t('queue.polling')}
            </span>
          )}
        </div>

        {error && (
          <div className="p-3 bg-primary/20 border border-primary rounded-lg text-primary-light text-sm mb-4">
            {error}
          </div>
        )}

        {loading && <p className="text-text-muted text-sm">{t('queue.loading')}</p>}

        {!loading && jobs.length === 0 && (
          <p className="text-text-muted text-sm">{t('queue.noJobs')}</p>
        )}

        {!loading && jobs.length > 0 && (
          <div className="overflow-x-auto rounded-xl border border-surface-light bg-surface-dark/60">
            <table className="min-w-full text-sm">
              <thead className="border-b border-surface-light bg-surface-light/40 text-text-muted">
                <tr>
                  <th className="py-3 px-4 text-left font-semibold">{t('queue.col.source')}</th>
                  <th className="py-3 px-4 text-left font-semibold">{t('queue.col.target')}</th>
                  <th className="py-3 px-4 text-left font-semibold">{t('queue.col.status')}</th>
                  <th className="py-3 px-4 text-left font-semibold">{t('queue.col.created')}</th>
                  <th className="py-3 px-4 text-right font-semibold">{t('queue.col.actions')}</th>
                </tr>
              </thead>
              <tbody>
                {jobs.map(job => {
                  const badgeClass = STATUS_BADGE_CLASS[job.status]
                  const statusLabel = t(`queue.status.${job.status}`)
                  const sourceName = job.source_filename || job.source_file_id
                  const sourceSize = formatBytes(job.source_size_bytes)
                  const isBusy = busyJobId === job.id
                  const canCancel = job.status === 'queued'
                  const canDownload = job.status === 'completed' && !!job.output_file_id
                  return (
                    <tr key={job.id} className="border-t border-surface-light">
                      <td className="py-3 px-4 align-top">
                        <div className="font-medium text-text break-all">{sourceName}</div>
                        {(job.source_media_type || sourceSize) && (
                          <div className="text-xs text-text-muted mt-1">
                            {[job.source_media_type, sourceSize].filter(Boolean).join(' · ')}
                          </div>
                        )}
                      </td>
                      <td className="py-3 px-4 align-top">
                        <div className="text-text">{job.output_format}</div>
                        {job.quality && (
                          <div className="text-xs text-text-muted mt-1">{job.quality}</div>
                        )}
                      </td>
                      <td className="py-3 px-4 align-top">
                        <span
                          className={`inline-block rounded-full border px-2 py-0.5 text-xs font-semibold ${badgeClass}`}
                        >
                          {statusLabel}
                        </span>
                        {job.status === 'running' && typeof job.progress === 'number' && (
                          <div className="text-xs text-text-muted mt-1">{job.progress}%</div>
                        )}
                        {job.status === 'failed' && job.error_message && (
                          <div className="text-xs text-primary-light mt-1 break-words max-w-xs">
                            {job.error_message}
                          </div>
                        )}
                      </td>
                      <td className="py-3 px-4 align-top text-text-muted text-xs">
                        {formatTimestamp(job.created_at)}
                      </td>
                      <td className="py-3 px-4 align-top text-right">
                        <div className="inline-flex gap-2">
                          {canDownload && (
                            <button
                              type="button"
                              onClick={() => handleDownload(job)}
                              disabled={isBusy}
                              className="inline-flex items-center gap-2 rounded-lg bg-success/20 hover:bg-success/30 text-success font-semibold py-1.5 px-3 text-xs transition disabled:opacity-50"
                              title={t('queue.actions.download')}
                              aria-label={t('queue.actions.download')}
                            >
                              <FaDownload />
                              {t('queue.actions.download')}
                            </button>
                          )}
                          {canCancel && (
                            <button
                              type="button"
                              onClick={() => handleCancel(job)}
                              disabled={isBusy}
                              className="inline-flex items-center gap-2 rounded-lg bg-primary/20 hover:bg-primary/30 text-primary-light font-semibold py-1.5 px-3 text-xs transition disabled:opacity-50"
                              title={t('queue.actions.cancel')}
                              aria-label={t('queue.actions.cancel')}
                            >
                              <FaBan />
                              {t('queue.actions.cancel')}
                            </button>
                          )}
                          {!canDownload && !canCancel && job.status === 'failed' && (
                            <span
                              className="inline-flex items-center gap-2 text-text-muted text-xs"
                              title={t('queue.actions.noActions')}
                            >
                              <FaTrash className="opacity-40" />
                            </span>
                          )}
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

export default Queue
