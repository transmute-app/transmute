import { lazy, Suspense, useState, useEffect, useCallback, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import FileTable, { FileInfo, ConversionInfo, FileTableRow, JobStatus } from '../components/FileTable'
import { isPreviewable } from '../components/previewUtils'
import { authFetch as fetch } from '../utils/api'
import { downloadBlob } from '../utils/download'
import { stripExtension } from '../utils/filename'
import { cancelJob, deleteJob, listJobs, retryJob, isTerminalJobStatus, type ConversionJob } from '../utils/jobs'

const PreviewModal = lazy(() => import('../components/PreviewModal'))

interface OriginalFileInfo {
  id: string
  original_filename: string
  media_type: string
  extension: string
  size_bytes: number
  created_at: string
}

interface ConversionRecord {
  id: string
  original_filename: string
  media_type: string
  extension: string
  size_bytes: number
  created_at: string
  quality?: string
  original_file?: OriginalFileInfo
}

const POLL_INTERVAL_MS = 2500

function History() {
  const [conversions, setConversions] = useState<ConversionRecord[]>([])
  const [jobs, setJobs] = useState<ConversionJob[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [downloadingId, setDownloadingId] = useState<string | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [cancellingId, setCancellingId] = useState<string | null>(null)
  const [retryingId, setRetryingId] = useState<string | null>(null)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [deletingSelected, setDeletingSelected] = useState(false)
  const [downloadingSelected, setDownloadingSelected] = useState(false)
  const [previewConversion, setPreviewConversion] = useState<ConversionRecord | null>(null)
  const { t } = useTranslation()
  const isMountedRef = useRef(true)

  const refresh = useCallback(async () => {
    try {
      const [convResp, jobsList] = await Promise.all([
        fetch('/api/conversions/complete'),
        listJobs(),
      ])
      if (!convResp.ok) throw new Error(t('history.fetchFailed'))
      const convData = await convResp.json()
      if (!isMountedRef.current) return
      setConversions(convData.conversions)
      // Hide completed jobs from the jobs list — the completed conversions
      // already represent them with full original-file metadata.
      setJobs(jobsList.filter(j => j.status !== 'completed'))
      setError(null)
    } catch (err) {
      if (isMountedRef.current) {
        setError(err instanceof Error ? err.message : t('history.loadFailed'))
      }
    }
  }, [t])

  useEffect(() => {
    isMountedRef.current = true
    refresh().finally(() => {
      if (isMountedRef.current) setLoading(false)
    })
    return () => {
      isMountedRef.current = false
    }
  }, [refresh])

  // Poll while at least one job is non-terminal.
  const hasActiveJobs = jobs.some(j => !isTerminalJobStatus(j.status))
  useEffect(() => {
    if (!hasActiveJobs) return
    const handle = window.setInterval(() => { void refresh() }, POLL_INTERVAL_MS)
    return () => window.clearInterval(handle)
  }, [hasActiveJobs, refresh])

  const handleDownload = async (conversion: ConversionRecord) => {
    setDownloadingId(conversion.id)
    try {
      const response = await fetch(`/api/files/${conversion.id}`)
      if (!response.ok) throw new Error('Download failed')

      let filename = stripExtension(conversion.original_filename || 'download')
      filename += conversion.extension || ''

      const blob = await response.blob();
      downloadBlob(blob, filename);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Download failed')
    } finally {
      setDownloadingId(null)
    }
  }

  const handleDelete = async (conversionId: string) => {
    setDeletingId(conversionId)
    try {
      const response = await fetch(`/api/conversions/${conversionId}`, { method: 'DELETE' })
      if (!response.ok) throw new Error(t('history.deleteFailed'))
      setConversions(prev => prev.filter(c => c.id !== conversionId))
    } catch (err) {
      setError(err instanceof Error ? err.message : t('history.deleteFailed'))
    } finally {
      setDeletingId(null)
    }
  }

  const handleCancelJob = async (jobId: string) => {
    setCancellingId(jobId)
    setError(null)
    try {
      const updated = await cancelJob(jobId)
      setJobs(prev => prev.map(j => (j.id === jobId ? updated : j)))
    } catch (err) {
      setError(err instanceof Error ? err.message : t('history.cancelFailed'))
    } finally {
      setCancellingId(null)
    }
  }

  const handleRetryJob = async (jobId: string) => {
    setRetryingId(jobId)
    setError(null)
    try {
      const updated = await retryJob(jobId)
      setJobs(prev => prev.map(j => (j.id === jobId ? updated : j)))
    } catch (err) {
      setError(err instanceof Error ? err.message : t('history.retryFailed'))
    } finally {
      setRetryingId(null)
    }
  }

  const handleDeleteJob = async (jobId: string) => {
    setDeletingId(jobId)
    setError(null)
    try {
      await deleteJob(jobId)
      setJobs(prev => prev.filter(j => j.id !== jobId))
    } catch (err) {
      setError(err instanceof Error ? err.message : t('history.deleteFailed'))
    } finally {
      setDeletingId(null)
    }
  }

  const toggleSelection = (id: string) => {
    setSelectedIds(prev => {
      const newSet = new Set(prev)
      if (newSet.has(id)) {
        newSet.delete(id)
      } else {
        newSet.add(id)
      }
      return newSet
    })
  }

  const toggleSelectAll = () => {
    if (selectedIds.size === conversions.length) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(conversions.map(c => c.id)))
    }
  }

  const handleDeleteSelected = async () => {
    if (selectedIds.size === 0) return
    setDeletingSelected(true)
    setError(null)

    const idsToDelete = Array.from(selectedIds)

    const results = await Promise.allSettled(
      idsToDelete.map(async (conversionId) => {
        const response = await fetch(`/api/conversions/${conversionId}`, { method: 'DELETE' })
        if (!response.ok) throw new Error(`Delete failed for ${conversionId}`)
        setConversions(prev => prev.filter(c => c.id !== conversionId))
        setSelectedIds(prev => {
          const newSet = new Set(prev)
          newSet.delete(conversionId)
          return newSet
        })
      })
    )

    const errors = results
      .filter((r): r is PromiseRejectedResult => r.status === 'rejected')
      .map(r => (r.reason instanceof Error ? r.reason.message : t('history.deleteFailed')))

    if (errors.length > 0) {
      setError(errors.join('; '))
    }

    setDeletingSelected(false)
  }

  const handleDownloadSelected = async () => {
    if (selectedIds.size === 0) return
    setDownloadingSelected(true)
    setError(null)

    try {
      const response = await fetch('/api/files/batch', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          file_ids: Array.from(selectedIds)
        })
      })

      if (!response.ok) throw new Error('Batch download failed')

      const filename = `transmute_batch_${new Date().toISOString().split('T')[0]}.zip`
      const blob = await response.blob()
      downloadBlob(blob, filename);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Batch download failed')
    } finally {
      setDownloadingSelected(false)
    }
  }

  // Build merged rows: non-completed jobs first (newest first), then completed
  // conversions (already newest-first from the API).
  const jobRows: FileTableRow[] = jobs
    .slice()
    .sort((a, b) => {
      const da = a.created_at ? new Date(a.created_at).getTime() : 0
      const db = b.created_at ? new Date(b.created_at).getTime() : 0
      return db - da
    })
    .map(job => {
      const ext = job.source_extension || ''
      const fileInfo: FileInfo = {
        id: job.source_file_id,
        original_filename: job.source_filename || job.source_file_id,
        media_type: job.source_media_type || '',
        extension: ext,
        size_bytes: job.source_size_bytes || 0,
        created_at: job.created_at || undefined,
      }
      const targetExt = job.output_format.startsWith('.') ? job.output_format : `.${job.output_format}`
      const placeholderConversion: ConversionInfo = {
        id: job.id,
        original_filename: job.source_filename || '',
        media_type: job.output_format,
        extension: targetExt,
        size_bytes: 0,
        created_at: job.created_at || '',
        quality: job.quality || undefined,
      }
      const status: JobStatus = job.status
      return {
        id: `job:${job.id}`,
        file: fileInfo,
        conversion: placeholderConversion,
        jobStatus: status,
        statusMessage: job.error_message || undefined,
        status: status === 'failed' || status === 'cancelled' ? 'failed' : undefined,
        selectable: false,
        onCancel: status === 'queued' ? () => handleCancelJob(job.id) : undefined,
        onRetry: status === 'failed' || status === 'cancelled' ? () => handleRetryJob(job.id) : undefined,
        onDelete: status === 'failed' || status === 'cancelled' ? () => handleDeleteJob(job.id) : undefined,
        isCancelling: cancellingId === job.id,
        isRetrying: retryingId === job.id,
        isDeleting: deletingId === job.id,
      }
    })

  const conversionRows: FileTableRow[] = conversions.map(conversion => {
    const originalFile = conversion.original_file
    const fileInfo: FileInfo = {
      id: originalFile?.id || conversion.id,
      original_filename: originalFile?.original_filename || conversion.original_filename,
      media_type: originalFile?.media_type || conversion.media_type,
      extension: originalFile?.extension || conversion.extension,
      size_bytes: originalFile?.size_bytes || conversion.size_bytes,
      created_at: originalFile?.created_at || conversion.created_at,
    }
    const conversionInfo: ConversionInfo = {
      id: conversion.id,
      original_filename: conversion.original_filename,
      media_type: conversion.media_type,
      extension: conversion.extension,
      size_bytes: conversion.size_bytes,
      created_at: conversion.created_at,
      quality: conversion.quality,
    }
    return {
      id: conversion.id,
      file: fileInfo,
      conversion: conversionInfo,
      jobStatus: 'completed' as JobStatus,
      onDownload: () => handleDownload(conversion),
      onDelete: () => handleDelete(conversion.id),
      onPreview: isPreviewable(conversion.media_type)
        ? () => {
            const name = conversion.original_filename || 'download'
            const base = stripExtension(name)
            setPreviewConversion({ ...conversion, original_filename: base + (conversion.extension || '') })
          }
        : undefined,
      isDeleting: deletingId === conversion.id,
      isDownloading: downloadingId === conversion.id,
    }
  })

  const allRows = [...jobRows, ...conversionRows]

  return (
    <div className="min-h-full bg-gradient-to-br from-surface-dark to-surface-light p-8 pb-12">
      <div className="max-w-6xl mx-auto">
        <div className="flex justify-between items-center mb-6 min-h-[4rem]">
          <h1 className="text-3xl font-bold text-primary">{t('history.title')}</h1>
          <div className="flex gap-3">
            {selectedIds.size > 0 && (
              <>
                <button
                  onClick={handleDownloadSelected}
                  disabled={downloadingSelected}
                  className="bg-success hover:bg-success-dark text-white font-semibold py-2 px-6 rounded-lg transition duration-200 shadow-md hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {downloadingSelected ? t('history.downloadingSelected') : t('history.downloadSelected', { count: selectedIds.size })}
                </button>
                <button
                  onClick={handleDeleteSelected}
                  disabled={deletingSelected}
                  className="bg-primary/20 hover:bg-primary/40 text-primary-light font-semibold py-2 px-6 rounded-lg transition duration-200 shadow-md hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {deletingSelected ? t('history.deleting') : t('history.deleteSelected', { count: selectedIds.size })}
                </button>
              </>
            )}
          </div>
        </div>

        {error && (
          <div className="p-3 bg-primary/20 border border-primary rounded-lg text-primary-light text-sm mb-4">
            {error}
          </div>
        )}

        {loading && (
          <p className="text-text-muted text-sm">{t('history.loading')}</p>
        )}

        {!loading && allRows.length === 0 && (
          <p className="text-text-muted text-sm">{t('history.noConversions')}</p>
        )}

        {!loading && allRows.length > 0 && (
          <FileTable
            rows={allRows}
            showCheckbox={true}
            showStatus={true}
            selectedIds={selectedIds}
            onToggleSelect={toggleSelection}
            onToggleSelectAll={toggleSelectAll}
          />
        )}

        {previewConversion && (
          <Suspense fallback={null}>
            <PreviewModal
              fileId={previewConversion.id}
              filename={previewConversion.original_filename}
              mediaType={previewConversion.media_type}
              onClose={() => setPreviewConversion(null)}
            />
          </Suspense>
        )}
      </div>
    </div>
  )
}

export default History
