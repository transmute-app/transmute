import { lazy, Suspense, useState, useEffect, useRef, useMemo, useCallback } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { FaCheckCircle, FaSyncAlt, FaDownload, FaTimes } from 'react-icons/fa'
import { FaListCheck } from 'react-icons/fa6'
import { useTranslation } from 'react-i18next'
import FileTable, { FileInfo, ConversionInfo } from '../components/FileTable'
import { isPreviewable } from '../components/previewUtils'
import { authFetch as fetch, apiJson } from '../utils/api'
import { downloadBlob } from '../utils/download'
import { stripExtension } from '../utils/filename'
import {
  createJob,
  isTerminalJobStatus,
  listJobs,
  type ConversionJob,
} from '../utils/jobs'

const PreviewModal = lazy(() => import('../components/PreviewModal'))

interface PendingFile {
  file: FileInfo
  selectedFormat: string
  selectedQuality?: string
  status: 'pending' | 'queued' | 'running' | 'failed'
  errorMessage?: string
}

interface CompletedConversion {
  file: FileInfo
  conversion: ConversionInfo
}

function getIsMacPlatform() {
  if (typeof navigator === 'undefined') return false

  const platform = (navigator as Navigator & { userAgentData?: { platform?: string } }).userAgentData?.platform
    || navigator.platform
    || navigator.userAgent
  return /mac|iphone|ipad|ipod/i.test(platform)
}

function HotkeyHint({ label, className = '' }: { label: string; className?: string }) {
  return (
    <span className={`text-[11px] tracking-[0.12em] ${className || 'text-text-muted/70'}`}>
      {label}
    </span>
  )
}

function UrlUploadPlaceholder({
  value,
  disabled,
  onChange,
  onSubmit,
  compact = false,
}: {
  value: string
  disabled: boolean
  onChange: (value: string) => void
  onSubmit: () => void
  compact?: boolean
}) {
  const { t } = useTranslation()
  const isValidUrl = value.trim().length > 0 && /^https?:\/\/.+/i.test(value.trim())

  return (
    <div className={`flex ${compact ? 'flex-col gap-2 sm:flex-row sm:items-center' : 'flex-col gap-2 sm:flex-row sm:items-center'}`}>
      <input
        type="url"
        inputMode="url"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={(event) => { if (event.key === 'Enter' && isValidUrl && !disabled) onSubmit() }}
        placeholder={t('converter.urlUploadHint')}
        disabled={disabled}
        className="w-full rounded-lg border border-surface-dark bg-transparent px-3 py-2 text-sm text-text outline-none transition duration-200 placeholder:text-text-muted/60 focus:border-primary/60 focus:ring-2 focus:ring-primary/20 disabled:cursor-not-allowed disabled:opacity-60"
      />
      <button
        type="button"
        disabled={disabled || !isValidUrl}
        onClick={onSubmit}
        className="rounded-lg border border-surface-dark bg-transparent px-4 py-2 text-sm font-semibold text-text-muted transition duration-200 hover:border-primary/60 hover:text-primary disabled:cursor-not-allowed disabled:opacity-60"
      >
        {t('converter.addUrl')}
      </button>
    </div>
  )
}

async function getResponseDetail(response: Response) {
  try {
    const errorData = await response.json()
    return typeof errorData?.detail === 'string' ? errorData.detail : response.statusText
  } catch {
    return response.statusText
  }
}

function isReadyPendingFile(status: PendingFile['status']) {
  return status === 'pending' || status === 'failed'
}

function isSubmittedPendingFile(status: PendingFile['status']) {
  return status === 'queued' || status === 'running'
}

function Converter() {
  const location = useLocation()
  const navigate = useNavigate()
  const { t } = useTranslation()
  const [pendingFiles, setPendingFiles] = useState<PendingFile[]>([])
  const [completedConversions, setCompletedConversions] = useState<CompletedConversion[]>([])
  const [uploading, setUploading] = useState(false)
  const [uploadCount, setUploadCount] = useState(0)
  const [ignoredUploadCount, setIgnoredUploadCount] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [submittingJobs, setSubmittingJobs] = useState(false)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [downloadingId, setDownloadingId] = useState<string | null>(null)
  const [downloadingAll, setDownloadingAll] = useState(false)
  const [autoDownload, setAutoDownload] = useState(false)
  const [dragOver, setDragOver] = useState(false)
  const [urlInput, setUrlInput] = useState('')
  const [defaultFormats, setDefaultFormats] = useState<Record<string, string>>({})
  const [formatAliases, setFormatAliases] = useState<Record<string, string>>({})
  const [defaultQualities, setDefaultQualities] = useState<Record<string, string>>({})
  const [previewFile, setPreviewFile] = useState<{ id: string; filename: string; mediaType: string } | null>(null)
  const [activeJobCount, setActiveJobCount] = useState(0)

  // Keep mutable references so polling can read latest values without
  // forcing the interval effect to restart on every render.
  const submittedJobsRef = useRef<Map<string, ConversionJob>>(new Map())
  const knownStatusRef = useRef<Map<string, ConversionJob['status']>>(new Map())
  const pendingFilesRef = useRef(pendingFiles)
  const autoDownloadRef = useRef(autoDownload)
  const handleDownloadRef = useRef<(c: ConversionInfo) => Promise<void>>(async () => {})
  const handleJobTransitionRef = useRef<(job: ConversionJob) => Promise<void>>(async () => {})
  const pollJobsRef = useRef<() => Promise<boolean>>(async () => false)

  // Load auto-download setting, default format mappings, and default quality mappings
  useEffect(() => {
    fetch('/api/settings')
      .then(r => r.ok ? r.json() : Promise.reject())
      .then(data => setAutoDownload(!!data.auto_download))
      .catch(() => {})
    fetch('/api/default-formats')
      .then(r => r.ok ? r.json() : Promise.reject())
      .then((data: { defaults: { input_format: string; output_format: string }[]; aliases: Record<string, string> }) => {
        const map: Record<string, string> = {}
        for (const d of data.defaults) map[d.input_format] = d.output_format
        setDefaultFormats(map)
        setFormatAliases(data.aliases || {})
      })
      .catch(() => {})
    fetch('/api/default-qualities')
      .then(r => r.ok ? r.json() : Promise.reject())
      .then((data: { defaults: { output_format: string; quality: string }[] }) => {
        const map: Record<string, string> = {}
        for (const d of data.defaults) map[d.output_format] = d.quality
        setDefaultQualities(map)
      })
      .catch(() => {})
  }, [])

  // Handle files passed from Files page
  useEffect(() => {
    if (location.state?.files) {
      const incomingFiles = location.state.files as FileInfo[]
      const newPendingFiles: PendingFile[] = incomingFiles.map(file => {
        const sortedFormats = file.compatible_formats
          ? Object.keys(file.compatible_formats).sort()
          : []
        const inputExt = file.extension?.replace(/^\./, '') || file.media_type || ''
        const normalizedExt = formatAliases[inputExt] || inputExt
        const userDefault = defaultFormats[normalizedExt] || defaultFormats[inputExt]
        const selectedFormat = (userDefault && sortedFormats.includes(userDefault))
          ? userDefault
          : sortedFormats[0] || ''
        const qualities = (selectedFormat && file.compatible_formats?.[selectedFormat]) || []
        const defaultQuality = defaultQualities[selectedFormat]
        return {
          file,
          selectedFormat,
          selectedQuality: qualities.length > 0
            ? (defaultQuality && qualities.includes(defaultQuality) ? defaultQuality : (qualities.includes('medium') ? 'medium' : undefined))
            : undefined,
          status: 'pending',
        }
      })
      setPendingFiles(prev => [...newPendingFiles, ...prev])
      // Clear the location state to prevent re-adding on refresh
      navigate(location.pathname, { replace: true })
    }
  }, [location.state, location.pathname, navigate, defaultFormats, formatAliases, defaultQualities])

  const processFiles = async (files: File[]) => {
    if (files.length === 0) return

    setUploading(true)
    setError(null)
    setIgnoredUploadCount(0)
    setUploadCount(files.length)

    const promises = files.map(async (file) => {
      try {
        const formData = new FormData()
        formData.append('file', file)

        const response = await fetch('/api/files', {
          method: 'POST',
          body: formData,
        })

        if (!response.ok) {
          const detail = await getResponseDetail(response)
          if (response.status === 422) {
            setIgnoredUploadCount((prev) => prev + 1)
            return null
          }
          throw new Error(`Upload failed for ${file.name}: ${detail}`)
        }

        const data = await response.json()
        const fileInfo: FileInfo = {
          id: data.metadata.id,
          original_filename: data.metadata.original_filename,
          media_type: data.metadata.media_type,
          extension: data.metadata.extension,
          size_bytes: data.metadata.size_bytes,
          created_at: data.metadata.created_at,
          compatible_formats: data.metadata.compatible_formats,
        }

        const sortedFormats = fileInfo.compatible_formats
          ? Object.keys(fileInfo.compatible_formats).sort()
          : []
        const inputExt = fileInfo.extension?.replace(/^\./, '') || fileInfo.media_type || ''
        const normalizedExt = formatAliases[inputExt] || inputExt
        const userDefault = defaultFormats[normalizedExt] || defaultFormats[inputExt]
        const defaultFormat = (userDefault && sortedFormats.includes(userDefault))
          ? userDefault
          : sortedFormats[0] || ''

        const qualities = (defaultFormat && fileInfo.compatible_formats?.[defaultFormat]) || []
        const defaultQualityForFormat = defaultQualities[defaultFormat]
        const pending: PendingFile = {
          file: fileInfo,
          selectedFormat: defaultFormat,
          selectedQuality: qualities.length > 0
            ? (defaultQualityForFormat && qualities.includes(defaultQualityForFormat) ? defaultQualityForFormat : (qualities.includes('medium') ? 'medium' : undefined))
            : undefined,
          status: 'pending',
        }

        // Add to pending list immediately as each upload completes
        setPendingFiles((prev) => [...prev, pending])

        return pending
      } finally {
        setUploadCount((prev) => Math.max(prev - 1, 0))
      }
    })

    const results = await Promise.allSettled(promises)

    const errors = results
      .filter((r): r is PromiseRejectedResult => r.status === 'rejected')
      .map((r) => (r.reason instanceof Error ? r.reason.message : 'Upload failed'))

    if (errors.length > 0) {
      setError(errors.join('; '))
    }

    setUploading(false)
    setUploadCount(0)
  }

  const processUrlUpload = async () => {
    const url = urlInput.trim()
    if (!url) return

    setUploading(true)
    setError(null)
    setIgnoredUploadCount(0)
    setUploadCount(1)

    try {
      const response = await fetch('/api/files/url', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url }),
      })

      if (!response.ok) {
        const detail = await getResponseDetail(response)
        if (response.status === 422) {
          setIgnoredUploadCount(1)
        } else {
          throw new Error(detail)
        }
        return
      }

      const data = await response.json()
      // Endpoint returns a list of files — a single URL may resolve to
      // multiple files (e.g. a playlist).
      const uploadedFiles: FileInfo[] = Array.isArray(data.files)
        ? data.files.map((meta: FileInfo) => ({
            id: meta.id,
            original_filename: meta.original_filename,
            media_type: meta.media_type,
            extension: meta.extension,
            size_bytes: meta.size_bytes,
            created_at: meta.created_at,
            compatible_formats: meta.compatible_formats,
          }))
        : []

      if (uploadedFiles.length === 0) {
        setIgnoredUploadCount(1)
        return
      }

      setUploadCount(uploadedFiles.length)

      const pendings: PendingFile[] = uploadedFiles.map((fileInfo) => {
        const sortedFormats = fileInfo.compatible_formats
          ? Object.keys(fileInfo.compatible_formats).sort()
          : []
        const inputExt = fileInfo.extension?.replace(/^\./, '') || fileInfo.media_type || ''
        const normalizedExt = formatAliases[inputExt] || inputExt
        const userDefault = defaultFormats[normalizedExt] || defaultFormats[inputExt]
        const defaultFormat = (userDefault && sortedFormats.includes(userDefault))
          ? userDefault
          : sortedFormats[0] || ''

        const qualities = (defaultFormat && fileInfo.compatible_formats?.[defaultFormat]) || []
        const defaultQualityForFormat = defaultQualities[defaultFormat]
        return {
          file: fileInfo,
          selectedFormat: defaultFormat,
          selectedQuality: qualities.length > 0
            ? (defaultQualityForFormat && qualities.includes(defaultQualityForFormat) ? defaultQualityForFormat : (qualities.includes('medium') ? 'medium' : undefined))
            : undefined,
          status: 'pending',
        }
      })

      setPendingFiles((prev) => [...prev, ...pendings])
      setUrlInput('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'URL upload failed')
    } finally {
      setUploading(false)
      setUploadCount(0)
    }
  }

  const handleFileSelect = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files
    if (!files || files.length === 0) return
    await processFiles(Array.from(files))
    event.target.value = ''
  }

  const handleDrop = async (event: React.DragEvent) => {
    event.preventDefault()
    setDragOver(false)
    const files = Array.from(event.dataTransfer.files)
    await processFiles(files)
  }

  const handleDragOver = (event: React.DragEvent) => {
    event.preventDefault()
    setDragOver(true)
  }

  const handleDragLeave = () => {
    setDragOver(false)
  }

  const handleFormatChange = (fileId: string, format: string) => {
    setPendingFiles((prev) =>
      prev.map((pf) => {
        if (pf.file.id !== fileId) return pf
        const qualities = pf.file.compatible_formats?.[format] || []
        const dq = defaultQualities[format]
        const selectedQuality = qualities.length > 0
          ? (dq && qualities.includes(dq) ? dq : (qualities.includes('medium') ? 'medium' : undefined))
          : undefined
        return { ...pf, selectedFormat: format, selectedQuality, status: 'pending', errorMessage: undefined }
      })
    )
  }

  const handleQualityChange = (fileId: string, quality: string) => {
    setPendingFiles((prev) =>
      prev.map((pf) =>
        pf.file.id === fileId ? { ...pf, selectedQuality: quality } : pf
      )
    )
  }

  const handleDelete = async (fileId: string, isPending: boolean) => {
    setDeletingId(fileId)
    try {
      const response = await fetch(`/api/files/${fileId}`, { method: 'DELETE' })
      if (!response.ok) throw new Error(t('converter.deleteFailed'))

      if (isPending) {
        setPendingFiles((prev) => prev.filter((pf) => pf.file.id !== fileId))
      } else {
        setCompletedConversions((prev) => prev.filter((cc) => cc.file.id !== fileId))
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : t('converter.deleteFailed'))
    } finally {
      setDeletingId(null)
    }
  }

  const handleConvertAll = async () => {
    if (pendingFiles.length === 0) return

    setSubmittingJobs(true)
    setError(null)

    const filesToConvert = [...pendingFiles].filter(({ selectedFormat, status }) => !!selectedFormat && isReadyPendingFile(status))
    const fileIdsToConvert = new Set(filesToConvert.map(({ file }) => file.id))

    if (fileIdsToConvert.size === 0) {
      setSubmittingJobs(false)
      return
    }

    setPendingFiles((prev) =>
      prev.map((pf) =>
        fileIdsToConvert.has(pf.file.id)
          ? { ...pf, status: 'pending', errorMessage: undefined }
          : pf
      )
    )

    const promises = filesToConvert.map(async ({ file, selectedFormat, selectedQuality }) => {
      try {
        const job = await createJob({
          id: file.id,
          output_format: selectedFormat,
          quality: selectedQuality ?? null,
        })
        submittedJobsRef.current.set(job.id, job)
        knownStatusRef.current.set(job.id, job.status)

        // Keep submitted files visible in the pending list while the worker
        // processes them, but distinguish them from files still waiting for
        // the user to queue.
        setPendingFiles((prev) =>
          prev.map((pf) =>
            pf.file.id === file.id
              ? { ...pf, status: job.status === 'running' ? 'running' : 'queued', errorMessage: undefined }
              : pf
          )
        )

        // If the worker already took it to a terminal state (very fast), act now
        // so we don't have to wait a full poll interval.
        if (isTerminalJobStatus(job.status)) {
          await handleJobTransitionRef.current(job)
        }
        return job
      } catch (err) {
        const message = err instanceof Error ? err.message : `Conversion failed for ${file.original_filename}`
        setPendingFiles((prev) =>
          prev.map((pf) =>
            pf.file.id === file.id
              ? { ...pf, status: 'failed', errorMessage: message }
              : pf
          )
        )
        throw err
      }
    })

    const results = await Promise.allSettled(promises)

    const errors = results
      .filter((r): r is PromiseRejectedResult => r.status === 'rejected')
      .map((r) => (r.reason instanceof Error ? r.reason.message : 'Conversion failed'))

    if (errors.length > 0) {
      setError(errors.join('; '))
    }

    setSubmittingJobs(false)

    // Trigger an immediate poll so very-fast jobs surface without waiting for
    // the next interval, then let the polling effect take over.
    await pollJobsRef.current()
  }

  const triggerDownloads = async (conversions: CompletedConversion[]) => {
    if (conversions.length === 0) return
    if (conversions.length === 1) {
      await handleDownload(conversions[0].conversion)
    } else {
      setDownloadingAll(true)
      setError(null)
      try {
        const conversionIds = conversions.map(cc => cc.conversion.id)
        const response = await fetch('/api/files/batch', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ file_ids: conversionIds }),
        })
        if (!response.ok) throw new Error('Batch download failed')
        const filename = `transmute_batch_${new Date().toISOString().split('T')[0]}.zip`; 
        const blob = await response.blob();
        downloadBlob(blob, filename);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Batch download failed')
      } finally {
        setDownloadingAll(false)
      }
    }
  }

  const handleDownload = async (conversion: ConversionInfo) => {
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

  const handleDownloadAll = async () => {
    if (completedConversions.length === 0) return
    await triggerDownloads(completedConversions)
  }

  // Refresh per-render refs used by the polling loop.
  useEffect(() => { pendingFilesRef.current = pendingFiles }, [pendingFiles])
  useEffect(() => { autoDownloadRef.current = autoDownload }, [autoDownload])
  useEffect(() => { handleDownloadRef.current = handleDownload })

  // Apply a per-job status transition: completed -> move to completed list,
  // failed/cancelled -> mark the row as failed with a useful message.
  const handleJobTransition = useCallback(async (job: ConversionJob) => {
    const sourceId = job.source_file_id
    if (job.status === 'completed' && job.output_file_id) {
      const pf = pendingFilesRef.current.find(p => p.file.id === sourceId)
      const sourceFile = pf?.file
      if (!sourceFile) return

      // Best-effort enrich from the canonical conversion list so size/extension
      // match what the History page would show. Fall back to the job payload.
      let conversion: ConversionInfo
      try {
        const data = await apiJson<{ conversions: Array<ConversionInfo & { id: string }> }>(
          '/api/conversions/complete',
        )
        const match = data.conversions.find(c => c.id === job.output_file_id)
        if (match) {
          conversion = {
            id: match.id,
            original_filename: match.original_filename,
            media_type: match.media_type,
            extension: match.extension,
            size_bytes: match.size_bytes,
            created_at: match.created_at,
            quality: match.quality,
          }
        } else {
          throw new Error('not found')
        }
      } catch {
        const ext = job.output_format.startsWith('.') ? job.output_format : `.${job.output_format}`
        conversion = {
          id: job.output_file_id,
          original_filename: sourceFile.original_filename,
          media_type: job.output_format,
          extension: ext,
          size_bytes: 0,
          created_at: job.completed_at || new Date().toISOString(),
          quality: job.quality || undefined,
        }
      }

      setCompletedConversions(prev => [{ file: sourceFile, conversion }, ...prev])
      setPendingFiles(prev => prev.filter(p => p.file.id !== sourceId))

      if (autoDownloadRef.current) {
        try { await handleDownloadRef.current(conversion) } catch { /* ignore */ }
      }
      return
    }

    if (job.status === 'failed') {
      setPendingFiles(prev => prev.map(p =>
        p.file.id === sourceId
          ? { ...p, status: 'failed', errorMessage: job.error_message || t('table.statusLabel.failed') }
          : p
      ))
      return
    }

    if (job.status === 'queued' || job.status === 'running') {
      const pendingStatus: PendingFile['status'] = job.status
      setPendingFiles(prev => prev.map(p =>
        p.file.id === sourceId
          ? { ...p, status: pendingStatus, errorMessage: undefined }
          : p
      ))
      return
    }

    if (job.status === 'cancelled') {
      setPendingFiles(prev => prev.map(p =>
        p.file.id === sourceId
          ? { ...p, status: 'failed', errorMessage: t('table.statusLabel.cancelled') }
          : p
      ))
    }
  }, [t])

  useEffect(() => { handleJobTransitionRef.current = handleJobTransition }, [handleJobTransition])

  // Poll /api/jobs once. Returns true when at least one tracked job is still
  // non-terminal, so callers can decide whether to keep the spinner up.
  const pollJobs = useCallback(async (): Promise<boolean> => {
    const ids = Array.from(submittedJobsRef.current.keys())
    if (ids.length === 0) {
      setActiveJobCount(0)
      return false
    }
    try {
      const fresh = await listJobs()
      const byId = new Map(fresh.map(j => [j.id, j]))
      let activeRemaining = 0
      for (const id of ids) {
        const updated = byId.get(id)
        if (!updated) continue
        submittedJobsRef.current.set(id, updated)
        const prevStatus = knownStatusRef.current.get(id)
        if (prevStatus !== updated.status) {
          knownStatusRef.current.set(id, updated.status)
          await handleJobTransitionRef.current(updated)
        }
        if (!isTerminalJobStatus(updated.status)) activeRemaining++
      }
      setActiveJobCount(activeRemaining)
      return activeRemaining > 0
    } catch {
      // Suppress polling errors; the next tick will retry.
      return true
    }
  }, [])

  useEffect(() => { pollJobsRef.current = pollJobs }, [pollJobs])

  // Schedule polling while there are non-terminal tracked jobs.
  useEffect(() => {
    if (activeJobCount === 0) return
    const handle = window.setInterval(() => { void pollJobs() }, 2500)
    return () => window.clearInterval(handle)
  }, [activeJobCount, pollJobs])

  const clearIgnoredUploads = useCallback(() => {
    setIgnoredUploadCount(0)
  }, [])

  const handleClearPending = useCallback(() => {
    setPendingFiles([])
    clearIgnoredUploads()
  }, [clearIgnoredUploads])

  const handleClearCompleted = useCallback(() => {
    setCompletedConversions([])
    clearIgnoredUploads()
  }, [clearIgnoredUploads])

  // Pending files are always convertible; unsupported uploads are rejected by the API.
  const convertableFiles = useMemo(() =>
    pendingFiles.filter(pf => pf.file.compatible_formats && Object.keys(pf.file.compatible_formats).length > 0),
    [pendingFiles]
  )

  // Intersection of output formats shared by ALL convertable files
  const commonFormats = useMemo(() => {
    if (convertableFiles.length === 0) return []
    const sets = convertableFiles.map(pf =>
      new Set(pf.file.compatible_formats ? Object.keys(pf.file.compatible_formats) : [])
    )
    const first = sets[0]
    return [...first].filter(f => sets.every(s => s.has(f))).sort()
  }, [convertableFiles])

  // Intersection of qualities across convertable files that have quality options for their selected format
  const commonQualities = useMemo(() => {
    const qualityOrder: Record<string, number> = { low: 0, medium: 1, high: 2 }
    const qualitySets = convertableFiles
      .map(pf => {
        if (!pf.selectedFormat) return null
        const q = pf.file.compatible_formats?.[pf.selectedFormat]
        return q && q.length > 0 ? new Set(q) : null
      })
      .filter((s): s is Set<string> => s !== null)
    if (qualitySets.length === 0) return []
    const first = qualitySets[0]
    return [...first]
      .filter(q => qualitySets.every(s => s.has(q)))
      .sort((a, b) => (qualityOrder[a] ?? 99) - (qualityOrder[b] ?? 99))
  }, [convertableFiles])

  const handleBulkFormatChange = (format: string) => {
    setPendingFiles(prev =>
      prev.map(pf => {
        const formats = pf.file.compatible_formats ? Object.keys(pf.file.compatible_formats) : []
        if (!formats.includes(format)) return pf
        // If format isn't changing, preserve existing quality selection
        if (pf.selectedFormat === format) return pf
        const qualities = pf.file.compatible_formats?.[format] || []
        const dq = defaultQualities[format]
        const selectedQuality = qualities.length > 0
          ? (dq && qualities.includes(dq) ? dq : (qualities.includes('medium') ? 'medium' : undefined))
          : undefined
        return { ...pf, selectedFormat: format, selectedQuality, status: 'pending', errorMessage: undefined }
      })
    )
  }

  const handleBulkQualityChange = (quality: string) => {
    setPendingFiles(prev =>
      prev.map(pf => {
        if (!pf.selectedFormat) return pf
        const qualities = pf.file.compatible_formats?.[pf.selectedFormat] || []
        if (qualities.length === 0 || !qualities.includes(quality)) return pf
        return { ...pf, selectedQuality: quality }
      })
    )
  }

  const readyFilesToConvert = useMemo(() =>
    convertableFiles.filter(pf => isReadyPendingFile(pf.status)),
    [convertableFiles]
  )

  const hasConvertableFiles = convertableFiles.length > 0
  const hasCompletedConversions = completedConversions.length > 0
  const hasStarted = hasConvertableFiles || hasCompletedConversions

  const filePickerRef1 = useRef<HTMLInputElement>(null)
  const filePickerRef2 = useRef<HTMLInputElement>(null)
  const handleConvertAllRef = useRef(handleConvertAll)
  const isMacPlatform = getIsMacPlatform()

  const hotkeyLabels = {
    open: isMacPlatform ? '⌘O' : 'Ctrl+O',
    convert: isMacPlatform ? '⌘↵' : 'Ctrl+Enter',
    clear: 'Esc',
  }

  const hotkeys = useMemo<Record<string, () => void>>(() => ({
    'CTRL+O': () => {
      if(filePickerRef1.current) {
        filePickerRef1.current.click()
        return
      }
      if(filePickerRef2.current) {
        filePickerRef2.current.click()
      }
    },
    'CTRL+ENTER': () => {
      handleConvertAllRef.current()
    },
    'ESCAPE': () => {
      handleClearPending()
    },
  }), [handleClearPending])

  const keydownHandler = useCallback((event: KeyboardEvent) => {
      let shortcut = ''
      if(event.ctrlKey || event.metaKey) shortcut += 'CTRL+'
      if(event.shiftKey) shortcut += 'SHIFT+'
      if(event.altKey) shortcut += 'ALT+'
      shortcut += event.key.toUpperCase()

      if(hotkeys[shortcut]) {
        event.preventDefault()
        hotkeys[shortcut]()
      }
  }, [hotkeys])

  useEffect(() => {
    window.addEventListener('keydown', keydownHandler)

    return () => {
      window.removeEventListener('keydown', keydownHandler)
    }
  }, [keydownHandler])

  useEffect(() => {
    handleConvertAllRef.current = handleConvertAll;
  })

  // Initial landing page - shown before any files are selected
  if (!hasStarted && !uploading) {
    return (
      <div className="h-full bg-gradient-to-br from-surface-dark to-surface-light flex items-center justify-center p-4">
        <div className="bg-surface-light rounded-lg shadow-xl p-8 max-w-xl w-full border border-surface-dark">
          <h1 className="text-4xl font-bold text-center text-primary mb-2">
            {t('app.name')}
          </h1>
          <h3 className="text-md text-center text-text-muted mb-6">
            {t('app.tagline')}
          </h3>
          
          <div className="space-y-4">
            <label
              onDrop={handleDrop}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              className={`flex flex-col items-center justify-center w-full h-36 border-2 border-dashed rounded-lg cursor-pointer transition-colors duration-150 ${
                dragOver
                  ? 'border-primary bg-primary/10'
                  : 'border-surface-dark hover:border-primary/60 hover:bg-primary/5'
              } ${uploading ? 'opacity-50 pointer-events-none' : ''}`}
            >
              <div className="flex flex-col items-center justify-center gap-1 text-text-muted">
                <svg xmlns="http://www.w3.org/2000/svg" className="w-8 h-8 mb-1 opacity-60" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
                </svg>
                <span className="text-sm font-medium">
                  {uploading ? t('converter.uploading', { count: uploadCount }) : t('converter.dropFiles')}
                </span>
                <span className="text-xs opacity-60">{t('converter.clickToBrowse')}</span>
                <HotkeyHint label={hotkeyLabels.open} />
              </div>
              <input
                type="file"
                ref={filePickerRef1}
                multiple
                onChange={handleFileSelect}
                disabled={uploading}
                className="hidden"
              />
            </label>

            <UrlUploadPlaceholder
              value={urlInput}
              onChange={setUrlInput}
              onSubmit={processUrlUpload}
              disabled={uploading}
            />

            {error && (
              <div className="p-3 bg-primary/20 border border-primary rounded-lg text-primary-light text-sm">
                {error}
              </div>
            )}

            {ignoredUploadCount > 0 && (
              <div className="rounded-lg border border-text-muted/20 bg-surface-dark/40 px-3 py-2 text-xs text-text-muted">
                {t('converter.ignoredUnsupported', { count: ignoredUploadCount })}
              </div>
            )}
          </div>
        </div>
      </div>
    )
  }

  // File list view - shown once files have been selected
  return (
    <div className="min-h-screen bg-gradient-to-br from-surface-dark to-surface-light p-4 sm:p-8">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-3xl font-bold text-primary mb-6">{t('app.name')}</h1>

        {/* File input */}
        <div className="mb-6">
          <div className="space-y-3">
            <label
              onDrop={handleDrop}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              className={`flex items-center justify-center w-full h-20 border-2 border-dashed rounded-lg cursor-pointer transition-colors duration-150 ${
                dragOver
                  ? 'border-primary bg-primary/10'
                  : 'border-surface-dark hover:border-primary/60 hover:bg-primary/5'
              } ${uploading ? 'opacity-50 pointer-events-none' : ''}`}
            >
              <div className="flex items-center gap-3 text-text-muted">
                <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5 opacity-60" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
                </svg>
                <div className="flex flex-col items-center gap-1">
                  <span className="text-sm">
                    {uploading
                      ? t('converter.uploading', { count: uploadCount })
                      : t('converter.dropOrClick')}
                  </span>
                  <HotkeyHint label={hotkeyLabels.open} />
                </div>
              </div>
              <input
                type="file"
                ref={filePickerRef2}
                multiple
                onChange={handleFileSelect}
                disabled={uploading}
                className="hidden"
              />
            </label>

            <UrlUploadPlaceholder
              value={urlInput}
              onChange={setUrlInput}
              onSubmit={processUrlUpload}
              disabled={uploading}
              compact
            />
          </div>
        </div>

        {error && (
          <div className="p-3 bg-primary/20 border border-primary rounded-lg text-primary-light text-sm mb-4">
            {error}
          </div>
        )}

        {ignoredUploadCount > 0 && (
          <div className="mb-4 rounded-lg border border-text-muted/20 bg-surface-dark/40 px-3 py-2 text-xs text-text-muted">
            {t('converter.ignoredUnsupported', { count: ignoredUploadCount })}
          </div>
        )}

        {activeJobCount > 0 && (
          <div className="mb-4 flex flex-col gap-3 rounded-lg border border-success/40 bg-success/10 px-4 py-3 text-sm text-text sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-start gap-3">
              <span className="mt-0.5 inline-flex h-8 w-8 items-center justify-center rounded-full bg-success/20 text-success">
                <FaCheckCircle className="text-sm" />
              </span>
              <div>
                <p className="font-semibold text-text">{t('converter.jobsInQueue', { count: activeJobCount })}</p>
                <p className="mt-1 text-xs text-text-muted">{t('converter.jobsInProgressHint')}</p>
              </div>
            </div>
            <Link
              to="/history"
              className="inline-flex items-center gap-1.5 self-start rounded-lg border border-success/30 px-3 py-2 font-medium text-success transition duration-200 hover:bg-success/15 hover:text-success sm:self-auto"
            >
              <FaListCheck className="text-xs" />
              {t('converter.viewQueue')}
            </Link>
          </div>
        )}

        {/* Pending conversions section */}
        {hasConvertableFiles && (
          <div className="mb-8">
            <div className="flex justify-between items-center mb-4 gap-2">
              <h2 className="text-base sm:text-xl font-semibold text-text whitespace-nowrap">
                {t('converter.pending', { count: convertableFiles.length })}
              </h2>
              <div className="flex items-center gap-2 sm:gap-3">
                <button
                  onClick={handleConvertAll}
                  disabled={submittingJobs || readyFilesToConvert.length === 0}
                  className="flex items-center gap-1.5 sm:gap-2 bg-primary hover:bg-primary-dark text-text font-semibold py-2 px-3 sm:px-6 rounded-lg transition duration-200 shadow-md hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed text-sm"
                >
                  <FaSyncAlt className={`text-xs sm:text-sm ${submittingJobs ? 'animate-spin' : ''}`} />
                  <span className="hidden sm:inline">
                    {submittingJobs
                      ? t('converter.converting', { count: readyFilesToConvert.length })
                      : t('converter.convertFile', { count: readyFilesToConvert.length })}
                  </span>
                  <HotkeyHint label={hotkeyLabels.convert} className="text-text/80 hidden sm:inline" />
                </button>
                <button
                  onClick={handleClearPending}
                  disabled={submittingJobs}
                  className="flex items-center gap-1.5 sm:gap-2 text-sm text-text-muted hover:text-text border border-surface-dark hover:border-text-muted py-2 px-3 sm:px-4 rounded-lg transition duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <FaTimes className="text-xs sm:text-sm" />
                  <span className="hidden sm:inline">{t('converter.clear')}</span>
                  <HotkeyHint label={hotkeyLabels.clear} className="hidden sm:inline" />
                </button>
              </div>
            </div>
            <FileTable
                rows={convertableFiles.map(pf => ({
                  id: pf.file.id,
                  file: pf.file,
                  selectedFormat: pf.selectedFormat,
                  status: pf.status === 'failed' ? 'failed' : 'pending',
                  statusMessage: pf.errorMessage,
                  jobStatus: isSubmittedPendingFile(pf.status) ? pf.status : undefined,
                  onFormatChange: isReadyPendingFile(pf.status) ? (format: string) => handleFormatChange(pf.file.id, format) : undefined,
                  onQualityChange: isReadyPendingFile(pf.status) ? (quality: string) => handleQualityChange(pf.file.id, quality) : undefined,
                  selectedQuality: pf.selectedQuality,
                  onDelete: isReadyPendingFile(pf.status) ? () => handleDelete(pf.file.id, true) : undefined,
                  onPreview: isPreviewable(pf.file.media_type) ? () => setPreviewFile({ id: pf.file.id, filename: pf.file.original_filename, mediaType: pf.file.media_type }) : undefined,
                  isDeleting: deletingId === pf.file.id,
                }))}
                isPending={true}
                showDate={false}
                showStatus={true}
                converting={submittingJobs}
                bulkFormats={convertableFiles.length > 1 ? commonFormats : undefined}
                bulkQualities={convertableFiles.length > 1 ? commonQualities : undefined}
                onBulkFormatChange={handleBulkFormatChange}
                onBulkQualityChange={handleBulkQualityChange}
              />
          </div>
        )}

        {/* Completed conversions section */}
        {hasCompletedConversions && (
          <div>
            <div className="flex justify-between items-center mb-4 gap-2">
              <h2 className="text-base sm:text-xl font-semibold text-text whitespace-nowrap">
                {t('converter.completed', { count: completedConversions.length })}
              </h2>
              <div className="flex items-center gap-2 sm:gap-3">
                {completedConversions.length > 1 && (
                  <button
                    onClick={handleDownloadAll}
                    disabled={downloadingAll}
                    className="flex items-center gap-1.5 sm:gap-2 bg-success hover:bg-success-dark text-white font-semibold py-2 px-3 sm:px-6 rounded-lg transition duration-200 shadow-md hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed text-sm sm:text-base"
                  >
                    <FaDownload className="text-xs sm:text-sm" />
                    <span className="hidden sm:inline">
                      {downloadingAll ? t('converter.downloading') : t('converter.downloadAll', { count: completedConversions.length })}
                    </span>
                    <span className="sm:hidden">
                      {downloadingAll ? '...' : t('table.all')}
                    </span>
                  </button>
                )}
                <button
                  onClick={handleClearCompleted}
                  className="flex items-center gap-1.5 sm:gap-2 text-sm text-text-muted hover:text-text border border-surface-dark hover:border-text-muted py-2 px-3 sm:px-4 rounded-lg transition duration-200"
                >
                  <FaTimes className="text-xs sm:text-sm" />
                  <span className="hidden sm:inline">{t('converter.clear')}</span>
                </button>
              </div>
            </div>
            <FileTable
              rows={completedConversions.map(cc => ({
                id: cc.conversion.id,
                file: cc.file,
                conversion: cc.conversion,
                onDownload: () => handleDownload(cc.conversion),
                onDelete: () => handleDelete(cc.file.id, false),
                onPreview: isPreviewable(cc.conversion.media_type) ? () => { const name = cc.file.original_filename || 'download'; const base = stripExtension(name); setPreviewFile({ id: cc.conversion.id, filename: base + (cc.conversion.extension || ''), mediaType: cc.conversion.media_type }) } : undefined,
                isDeleting: deletingId === cc.file.id,
                isDownloading: downloadingId === cc.conversion.id,
              }))}
              showDate={false}
            />          </div>
        )}

        {previewFile && (
          <Suspense fallback={null}>
            <PreviewModal
              fileId={previewFile.id}
              filename={previewFile.filename}
              mediaType={previewFile.mediaType}
              onClose={() => setPreviewFile(null)}
            />
          </Suspense>
        )}
      </div>
    </div>
  )
}

export default Converter
