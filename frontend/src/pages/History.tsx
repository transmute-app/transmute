import { lazy, Suspense, useState, useEffect, useCallback, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import FileTable, { FileInfo, ConversionInfo, FileTableRow, JobStatus } from '../components/FileTable'
import { isPreviewable } from '../components/previewUtils'
import { authFetch as fetch } from '../utils/api'
import { parseUtcTimestamp } from '../utils/datetime'
import { downloadBlob } from '../utils/download'
import { stripExtension } from '../utils/filename'
import Pagination from '../components/Pagination'
import { withPagination, type PaginationMetadata } from '../utils/pagination'
import { cancelJob, deleteJob, listJobs, retryJob, isTerminalJobStatus, type ConversionJob,
  cancelCompressionJob, deleteCompressionJob, listCompressionJobs, retryCompressionJob, type CompressionJob } from '../utils/jobs'

const PreviewModal = lazy(() => import('../components/PreviewModal'))

type HistoryMode = 'convert' | 'compress'

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

interface CompressionRecord {
  id: string
  original_filename: string
  media_type: string
  extension: string
  size_bytes: number
  created_at: string
  compression_level?: string
  original_file?: OriginalFileInfo
}

const POLL_INTERVAL_MS = 2500

function History() {
  const [conversions, setConversions] = useState<ConversionRecord[]>([])
  const [jobs, setJobs] = useState<ConversionJob[]>([])
  const [compressions, setCompressions] = useState<CompressionRecord[]>([])
  const [compressionJobs, setCompressionJobs] = useState<CompressionJob[]>([])
  const [mode, setMode] = useState<HistoryMode>('convert')
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
  const [conversionPage, setConversionPage] = useState(1)
  const [compressionPage, setCompressionPage] = useState(1)
  const [conversionPagination, setConversionPagination] = useState<PaginationMetadata | null>(null)
  const [compressionPagination, setCompressionPagination] = useState<PaginationMetadata | null>(null)
  const { t } = useTranslation()
  const isMountedRef = useRef(true)

  const refresh = useCallback(async () => {
    try {
      const [convResp, jobsList, compResp, compJobsList] = await Promise.all([
        fetch(withPagination('/api/conversions/complete', conversionPage)),
        listJobs(undefined, 1, 100, false),
        fetch(withPagination('/api/compressions/complete', compressionPage)),
        listCompressionJobs(undefined, 1, 100, false),
      ])
      if (!convResp.ok) throw new Error(t('history.fetchFailed'))
      if (!compResp.ok) throw new Error(t('history.fetchFailed'))
      const convData = await convResp.json() as {
        conversions: ConversionRecord[]
        pagination: PaginationMetadata
      }
      const compData = await compResp.json() as {
        compressions: CompressionRecord[]
        pagination: PaginationMetadata
      }
      if (!isMountedRef.current) return
      setConversions(convData.conversions)
      setCompressions(compData.compressions)
      setConversionPagination(convData.pagination)
      setCompressionPagination(compData.pagination)
      if (conversionPage > Math.max(1, convData.pagination.total_pages)) {
        setConversionPage(Math.max(1, convData.pagination.total_pages))
      }
      if (compressionPage > Math.max(1, compData.pagination.total_pages)) {
        setCompressionPage(Math.max(1, compData.pagination.total_pages))
      }
      // Hide completed jobs from the jobs list — the completed conversions
      // already represent them with full original-file metadata.
      setJobs(jobsList)
      setCompressionJobs(compJobsList)
      setError(null)
    } catch (err) {
      if (isMountedRef.current) {
        setError(err instanceof Error ? err.message : t('history.loadFailed'))
      }
    }
  }, [compressionPage, conversionPage, t])

  useEffect(() => {
    isMountedRef.current = true
    setLoading(true)
    refresh().finally(() => {
      if (isMountedRef.current) setLoading(false)
    })
    return () => {
      isMountedRef.current = false
    }
  }, [refresh])

  useEffect(() => {
    setSelectedIds(new Set())
  }, [compressionPage, conversionPage])

  // Poll while at least one job is non-terminal.
  const hasActiveJobs = jobs.some(j => !isTerminalJobStatus(j.status))
    || compressionJobs.some(j => !isTerminalJobStatus(j.status))
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
      await refresh()
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

  const handleDownloadCompression = async (compression: CompressionRecord) => {
    setDownloadingId(compression.id)
    try {
      const response = await fetch(`/api/files/${compression.id}`)
      if (!response.ok) throw new Error('Download failed')
      let filename = stripExtension(compression.original_filename || 'download')
      filename += compression.extension || ''
      const blob = await response.blob()
      downloadBlob(blob, filename)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Download failed')
    } finally {
      setDownloadingId(null)
    }
  }

  const handleDeleteCompression = async (compressionId: string) => {
    setDeletingId(compressionId)
    try {
      const response = await fetch(`/api/compressions/${compressionId}`, { method: 'DELETE' })
      if (!response.ok) throw new Error(t('history.deleteFailed'))
      setCompressions(prev => prev.filter(c => c.id !== compressionId))
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : t('history.deleteFailed'))
    } finally {
      setDeletingId(null)
    }
  }

  const handleCancelCompressionJob = async (jobId: string) => {
    setCancellingId(jobId)
    setError(null)
    try {
      const updated = await cancelCompressionJob(jobId)
      setCompressionJobs(prev => prev.map(j => (j.id === jobId ? updated : j)))
    } catch (err) {
      setError(err instanceof Error ? err.message : t('history.cancelFailed'))
    } finally {
      setCancellingId(null)
    }
  }

  const handleRetryCompressionJob = async (jobId: string) => {
    setRetryingId(jobId)
    setError(null)
    try {
      const updated = await retryCompressionJob(jobId)
      setCompressionJobs(prev => prev.map(j => (j.id === jobId ? updated : j)))
    } catch (err) {
      setError(err instanceof Error ? err.message : t('history.retryFailed'))
    } finally {
      setRetryingId(null)
    }
  }

  const handleDeleteCompressionJob = async (jobId: string) => {
    setDeletingId(jobId)
    setError(null)
    try {
      await deleteCompressionJob(jobId)
      setCompressionJobs(prev => prev.filter(j => j.id !== jobId))
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
    const currentCompleted = mode === 'compress' ? compressions : conversions
    if (selectedIds.size === currentCompleted.length && currentCompleted.length > 0) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(currentCompleted.map(c => c.id)))
    }
  }

  const handleModeChange = (next: HistoryMode) => {
    if (next === mode) return
    setMode(next)
    setSelectedIds(new Set())
    setError(null)
  }

  const handleDeleteSelected = async () => {
    if (selectedIds.size === 0) return
    setDeletingSelected(true)
    setError(null)

    const idsToDelete = Array.from(selectedIds)
    const basePath = mode === 'compress' ? '/api/compressions' : '/api/conversions'

    const results = await Promise.allSettled(
      idsToDelete.map(async (recordId) => {
        const response = await fetch(`${basePath}/${recordId}`, { method: 'DELETE' })
        if (!response.ok) throw new Error(`Delete failed for ${recordId}`)
        if (mode === 'compress') {
          setCompressions(prev => prev.filter(c => c.id !== recordId))
        } else {
          setConversions(prev => prev.filter(c => c.id !== recordId))
        }
        setSelectedIds(prev => {
          const newSet = new Set(prev)
          newSet.delete(recordId)
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

    await refresh()

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
      const da = parseUtcTimestamp(a.created_at)?.getTime() ?? 0
      const db = parseUtcTimestamp(b.created_at)?.getTime() ?? 0
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

  const allRows = conversionPage === 1 ? [...jobRows, ...conversionRows] : conversionRows

  // Compression job rows (non-completed compression jobs).
  const compressionJobRows: FileTableRow[] = compressionJobs
    .slice()
    .sort((a, b) => {
      const da = parseUtcTimestamp(a.created_at)?.getTime() ?? 0
      const db = parseUtcTimestamp(b.created_at)?.getTime() ?? 0
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
      // Compression preserves the source format; show level instead of format/quality.
      const placeholderConversion: ConversionInfo = {
        id: job.id,
        original_filename: job.source_filename || '',
        media_type: job.source_media_type || '',
        extension: ext,
        size_bytes: 0,
        created_at: job.created_at || '',
        compression_level: job.compression_level || undefined,
      }
      const status: JobStatus = job.status
      return {
        id: `comp-job:${job.id}`,
        file: fileInfo,
        conversion: placeholderConversion,
        jobType: 'compression',
        jobStatus: status,
        statusMessage: job.error_message || undefined,
        status: status === 'failed' || status === 'cancelled' ? 'failed' : undefined,
        selectable: false,
        onCancel: status === 'queued' ? () => handleCancelCompressionJob(job.id) : undefined,
        onRetry: status === 'failed' || status === 'cancelled' ? () => handleRetryCompressionJob(job.id) : undefined,
        onDelete: status === 'failed' || status === 'cancelled' ? () => handleDeleteCompressionJob(job.id) : undefined,
        isCancelling: cancellingId === job.id,
        isRetrying: retryingId === job.id,
        isDeleting: deletingId === job.id,
      }
    })

  const compressionRows: FileTableRow[] = compressions.map(compression => {
    const originalFile = compression.original_file
    const fileInfo: FileInfo = {
      id: originalFile?.id || compression.id,
      original_filename: originalFile?.original_filename || compression.original_filename,
      media_type: originalFile?.media_type || compression.media_type,
      extension: originalFile?.extension || compression.extension,
      size_bytes: originalFile?.size_bytes || compression.size_bytes,
      created_at: originalFile?.created_at || compression.created_at,
    }
    const conversionInfo: ConversionInfo = {
      id: compression.id,
      original_filename: compression.original_filename,
      media_type: compression.media_type,
      extension: compression.extension,
      size_bytes: compression.size_bytes,
      created_at: compression.created_at,
      compression_level: compression.compression_level,
    }
    return {
      id: compression.id,
      file: fileInfo,
      conversion: conversionInfo,
      jobType: 'compression',
      jobStatus: 'completed' as JobStatus,
      onDownload: () => handleDownloadCompression(compression),
      onDelete: () => handleDeleteCompression(compression.id),
      onPreview: isPreviewable(compression.media_type)
        ? () => {
            const name = compression.original_filename || 'download'
            const base = stripExtension(name)
            setPreviewConversion({ ...compression, original_filename: base + (compression.extension || '') })
          }
        : undefined,
      isDeleting: deletingId === compression.id,
      isDownloading: downloadingId === compression.id,
    }
  })

  const compressAllRows = compressionPage === 1
    ? [...compressionJobRows, ...compressionRows]
    : compressionRows
  const displayedRows = mode === 'compress' ? compressAllRows : allRows
  const displayedPagination = mode === 'compress' ? compressionPagination : conversionPagination

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

        <div className="mb-6 inline-flex rounded-lg border border-surface-dark bg-surface-dark/40 p-1" role="tablist">
          <button
            role="tab"
            aria-selected={mode === 'convert'}
            onClick={() => handleModeChange('convert')}
            className={`px-4 py-1.5 text-sm font-medium rounded-md transition duration-150 ${
              mode === 'convert' ? 'bg-primary text-text shadow' : 'text-text-muted hover:text-text'
            }`}
          >
            {t('history.tabConvert')}
          </button>
          <button
            role="tab"
            aria-selected={mode === 'compress'}
            onClick={() => handleModeChange('compress')}
            className={`px-4 py-1.5 text-sm font-medium rounded-md transition duration-150 ${
              mode === 'compress' ? 'bg-primary text-text shadow' : 'text-text-muted hover:text-text'
            }`}
          >
            {t('history.tabCompress')}
          </button>
        </div>

        {error && (
          <div className="p-3 bg-primary/20 border border-primary rounded-lg text-primary-light text-sm mb-4">
            {error}
          </div>
        )}

        {loading && (
          <p className="text-text-muted text-sm">{t('history.loading')}</p>
        )}

        {!loading && displayedRows.length === 0 && (
          <p className="text-text-muted text-sm">
            {mode === 'compress' ? t('history.noCompressions') : t('history.noConversions')}
          </p>
        )}

        {!loading && displayedRows.length > 0 && (
          <>
            <FileTable
              rows={displayedRows}
              showCheckbox={true}
              showStatus={true}
              typeColumnLabel={mode === 'compress' ? t('table.compressionLevel') : undefined}
              selectedIds={selectedIds}
              onToggleSelect={toggleSelection}
              onToggleSelectAll={toggleSelectAll}
            />
            {displayedPagination && (
              <Pagination
                pagination={displayedPagination}
                onPageChange={mode === 'compress' ? setCompressionPage : setConversionPage}
                disabled={loading || deletingSelected}
              />
            )}
          </>
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
