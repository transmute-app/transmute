import { useState, useEffect, useRef } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import FileTable, { FileInfo, ConversionInfo } from '../components/FileTable'
import PreviewModal, { isPreviewable } from '../components/PreviewModal'
import { authFetch as fetch } from '../utils/api'

interface PendingFile {
  file: FileInfo
  selectedFormat: string
  status: 'pending' | 'failed'
  errorMessage?: string
}

interface CompletedConversion {
  file: FileInfo
  conversion: ConversionInfo
}

function Converter() {
  const location = useLocation()
  const navigate = useNavigate()
  const [pendingFiles, setPendingFiles] = useState<PendingFile[]>([])
  const [completedConversions, setCompletedConversions] = useState<CompletedConversion[]>([])
  const [uploading, setUploading] = useState(false)
  const [uploadCount, setUploadCount] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [converting, setConverting] = useState(false)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [downloadingId, setDownloadingId] = useState<string | null>(null)
  const [downloadingAll, setDownloadingAll] = useState(false)
  const [autoDownload, setAutoDownload] = useState(false)
  const [dragOver, setDragOver] = useState(false)
  const [defaultFormats, setDefaultFormats] = useState<Record<string, string>>({})
  const [formatAliases, setFormatAliases] = useState<Record<string, string>>({})
  const [previewFile, setPreviewFile] = useState<{ id: string; filename: string; mediaType: string } | null>(null)

  // Load auto-download setting and default format mappings
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
  }, [])

  // Handle files passed from Files page
  useEffect(() => {
    if (location.state?.files) {
      const incomingFiles = location.state.files as FileInfo[]
      const newPendingFiles: PendingFile[] = incomingFiles.map(file => {
        const sortedFormats = file.compatible_formats
          ? [...file.compatible_formats].sort()
          : []
        const inputExt = file.extension?.replace(/^\./, '') || file.media_type || ''
        const normalizedExt = formatAliases[inputExt] || inputExt
        const userDefault = defaultFormats[normalizedExt] || defaultFormats[inputExt]
        const selectedFormat = (userDefault && sortedFormats.includes(userDefault))
          ? userDefault
          : sortedFormats[0] || ''
        return {
          file,
          selectedFormat,
          status: 'pending',
        }
      })
      setPendingFiles(prev => [...newPendingFiles, ...prev])
      // Clear the location state to prevent re-adding on refresh
      navigate(location.pathname, { replace: true })
    }
  }, [location.state, location.pathname, navigate, defaultFormats, formatAliases])

  const processFiles = async (files: File[]) => {
    if (files.length === 0) return

    setUploading(true)
    setError(null)
    setUploadCount(files.length)

    const promises = files.map(async (file) => {
      const formData = new FormData()
      formData.append('file', file)

      const response = await fetch('/api/files', {
        method: 'POST',
        body: formData,
      })

      if (!response.ok) {
        throw new Error(`Upload failed for ${file.name}: ${response.statusText}`)
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
        ? [...fileInfo.compatible_formats].sort()
        : []
      const inputExt = fileInfo.extension?.replace(/^\./, '') || fileInfo.media_type || ''
      const normalizedExt = formatAliases[inputExt] || inputExt
      const userDefault = defaultFormats[normalizedExt] || defaultFormats[inputExt]
      const defaultFormat = (userDefault && sortedFormats.includes(userDefault))
        ? userDefault
        : sortedFormats[0] || ''

      const pending: PendingFile = {
        file: fileInfo,
        selectedFormat: defaultFormat,
        status: 'pending',
      }

      // Add to pending list immediately as each upload completes
      setPendingFiles((prev) => [...prev, pending])
      setUploadCount((prev) => prev - 1)

      return pending
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
      prev.map((pf) =>
        pf.file.id === fileId ? { ...pf, selectedFormat: format, status: 'pending', errorMessage: undefined } : pf
      )
    )
  }

  const handleDelete = async (fileId: string, isPending: boolean) => {
    setDeletingId(fileId)
    try {
      const response = await fetch(`/api/files/${fileId}`, { method: 'DELETE' })
      if (!response.ok) throw new Error('Delete failed')

      if (isPending) {
        setPendingFiles((prev) => prev.filter((pf) => pf.file.id !== fileId))
      } else {
        setCompletedConversions((prev) => prev.filter((cc) => cc.file.id !== fileId))
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Delete failed')
    } finally {
      setDeletingId(null)
    }
  }

  const handleConvertAll = async () => {
    if (pendingFiles.length === 0) return

    setConverting(true)
    setError(null)

    const filesToConvert = [...pendingFiles].filter(({ selectedFormat }) => !!selectedFormat)
    const fileIdsToConvert = new Set(filesToConvert.map(({ file }) => file.id))

    setPendingFiles((prev) =>
      prev.map((pf) =>
        fileIdsToConvert.has(pf.file.id)
          ? { ...pf, status: 'pending', errorMessage: undefined }
          : pf
      )
    )

    const promises = filesToConvert.map(async ({ file, selectedFormat }) => {
      const inputFormat = file.extension?.replace(/^\./, '') || ''

      try {
        const response = await fetch('/api/conversions', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            id: file.id,
            input_format: inputFormat,
            output_format: selectedFormat,
          }),
        })

        if (!response.ok) {
          let detail = response.statusText
          try {
            const errorData = await response.json()
            detail = errorData.detail || detail
          } catch {
            // Fall back to status text when the response body is not JSON.
          }
          throw new Error(`Conversion failed for ${file.original_filename}: ${detail}`)
        }

        const data = await response.json()
        const conversionInfo: ConversionInfo = {
          id: data.id,
          original_filename: data.original_filename,
          media_type: data.media_type,
          extension: data.extension,
          size_bytes: data.size_bytes,
          created_at: data.created_at,
        }

        const completed: CompletedConversion = { file, conversion: conversionInfo }

        // Move to completed list immediately as it finishes
        setCompletedConversions((prev) => [completed, ...prev])
        setPendingFiles((prev) => prev.filter((pf) => pf.file.id !== file.id))

        if (autoDownload) {
          await handleDownload(conversionInfo)
        }

        return completed
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : `Conversion failed for ${file.original_filename}`
        setPendingFiles((prev) =>
          prev.map((pf) =>
            pf.file.id === file.id
              ? { ...pf, status: 'failed', errorMessage }
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

    setConverting(false)
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
        const blob = await response.blob()
        const url = window.URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `transmute_batch_${new Date().toISOString().split('T')[0]}.zip`
        document.body.appendChild(a)
        a.click()
        window.URL.revokeObjectURL(url)
        document.body.removeChild(a)
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

      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url

      let filename = conversion.original_filename || 'download'
      const lastDotIndex = filename.lastIndexOf('.')
      if (lastDotIndex > 0) {
        filename = filename.substring(0, lastDotIndex)
      }
      filename += conversion.extension || ''

      a.download = filename
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
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

  const hasPendingFiles = pendingFiles.length > 0
  const hasCompletedConversions = completedConversions.length > 0
  const hasStarted = hasPendingFiles || hasCompletedConversions

  const filePickerRef1 = useRef<HTMLInputElement>(null)
  const filePickerRef2 = useRef<HTMLInputElement>(null)
  const handleConvertAllRef = useRef(handleConvertAll);

  const hotkeys : Record<string, Function> = {
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
      handleConvertAllRef.current();
    },
    'ESCAPE': () => {
      setPendingFiles([])
    },
  }

  const keydownHandler = (event: KeyboardEvent) => {
      let shortcut = '';
      if(event.ctrlKey) shortcut += 'CTRL+'
      if(event.shiftKey) shortcut += 'SHIFT+'
      if(event.altKey) shortcut += 'ALT+'
      shortcut += event.key.toUpperCase()

      console.log(shortcut);

      if(hotkeys[shortcut]) {
        event.preventDefault()
        hotkeys[shortcut]()
      }
  }

  useEffect(() => {
    window.addEventListener('keydown', keydownHandler);
  }, [])

  useEffect(() => {
    handleConvertAllRef.current = handleConvertAll;
  })

  // Initial landing page - shown before any files are selected
  if (!hasStarted && !uploading) {
    return (
      <div className="h-full bg-gradient-to-br from-surface-dark to-surface-light flex items-center justify-center p-4">
        <div className="bg-surface-light rounded-lg shadow-xl p-8 max-w-xl w-full border border-surface-dark">
          <h1 className="text-4xl font-bold text-center text-primary mb-2">
            Transmute
          </h1>
          <h3 className="text-md text-center text-text-muted mb-6">
            Drop a file, pick a format, Transmute.
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
                  {uploading ? `Uploading ${uploadCount} file${uploadCount > 1 ? 's' : ''}...` : 'Drop files here'}
                </span>
                <span className="text-xs opacity-60">or click to browse</span>
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

            {error && (
              <div className="p-3 bg-primary/20 border border-primary rounded-lg text-primary-light text-sm">
                {error}
              </div>
            )}
          </div>
        </div>
      </div>
    )
  }

  // File list view - shown once files have been selected
  return (
    <div className="min-h-screen bg-gradient-to-br from-surface-dark to-surface-light p-8">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-3xl font-bold text-primary mb-6">Transmute</h1>

        {/* File input */}
        <div className="mb-6">
          <label
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            className={`flex items-center justify-center w-full h-20 border-2 border-dashed rounded-lg cursor-pointer transition-colors duration-150 ${
              dragOver
                ? 'border-primary bg-primary/10'
                : 'border-surface-dark hover:border-primary/60 hover:bg-primary/5'
            } ${uploading || converting ? 'opacity-50 pointer-events-none' : ''}`}
          >
            <div className="flex items-center gap-3 text-text-muted">
              <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5 opacity-60" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
              </svg>
              <span className="text-sm">
                {uploading
                  ? `Uploading ${uploadCount} file${uploadCount > 1 ? 's' : ''}...`
                  : 'Drop files here or click to browse'}
              </span>
            </div>
            <input
              type="file"
              ref={filePickerRef2}
              multiple
              onChange={handleFileSelect}
              disabled={uploading || converting}
              className="hidden"
            />
          </label>
        </div>

        {error && (
          <div className="p-3 bg-primary/20 border border-primary rounded-lg text-primary-light text-sm mb-4">
            {error}
          </div>
        )}

        {/* Pending conversions section */}
        {hasPendingFiles && (
          <div className="mb-8">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-semibold text-text">
                Pending Conversions ({pendingFiles.length})
              </h2>
              <div className="flex items-center gap-3">
                <button
                  onClick={handleConvertAll}
                  disabled={converting || pendingFiles.length === 0}
                  className="bg-primary hover:bg-primary-dark text-text font-semibold py-2 px-6 rounded-lg transition duration-200 shadow-md hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {converting
                    ? `Converting ${pendingFiles.length} file${pendingFiles.length > 1 ? 's' : ''}...`
                    : `Convert ${pendingFiles.length} File${pendingFiles.length > 1 ? 's' : ''}`}
                </button>
                <button
                  onClick={() => setPendingFiles([])}
                  disabled={converting}
                  className="text-sm text-text-muted hover:text-text border border-surface-dark hover:border-text-muted py-2 px-4 rounded-lg transition duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Clear
                </button>
              </div>
            </div>
            <FileTable
                rows={pendingFiles.map(pf => ({
                  id: pf.file.id,
                  file: pf.file,
                  selectedFormat: pf.selectedFormat,
                  status: pf.status,
                  statusMessage: pf.errorMessage,
                  onFormatChange: (format: string) => handleFormatChange(pf.file.id, format),
                  onDelete: () => handleDelete(pf.file.id, true),
                  onPreview: isPreviewable(pf.file.media_type) ? () => setPreviewFile({ id: pf.file.id, filename: pf.file.original_filename, mediaType: pf.file.media_type }) : undefined,
                  isDeleting: deletingId === pf.file.id,
                }))}
                isPending={true}
                showDate={false}
                converting={converting}
              />
          </div>
        )}

        {/* Completed conversions section */}
        {hasCompletedConversions && (
          <div>
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-semibold text-text">
                Completed Conversions ({completedConversions.length})
              </h2>
              <div className="flex items-center gap-3">
                {completedConversions.length > 1 && (
                  <button
                    onClick={handleDownloadAll}
                    disabled={downloadingAll}
                    className="bg-success hover:bg-success-dark text-white font-semibold py-2 px-6 rounded-lg transition duration-200 shadow-md hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {downloadingAll ? 'Downloading...' : `Download All ${completedConversions.length} Files`}
                  </button>
                )}
                <button
                  onClick={() => setCompletedConversions([])}
                  className="text-sm text-text-muted hover:text-text border border-surface-dark hover:border-text-muted py-2 px-4 rounded-lg transition duration-200"
                >
                  Clear
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
                onPreview: isPreviewable(cc.conversion.media_type) ? () => { const name = cc.file.original_filename || 'download'; const dot = name.lastIndexOf('.'); const base = dot > 0 ? name.substring(0, dot) : name; setPreviewFile({ id: cc.conversion.id, filename: base + (cc.conversion.extension || ''), mediaType: cc.conversion.media_type }) } : undefined,
                isDeleting: deletingId === cc.file.id,
                isDownloading: downloadingId === cc.conversion.id,
              }))}
              showDate={false}
            />          </div>
        )}

        {previewFile && (
          <PreviewModal
            fileId={previewFile.id}
            filename={previewFile.filename}
            mediaType={previewFile.mediaType}
            onClose={() => setPreviewFile(null)}
          />
        )}
      </div>
    </div>
  )
}

export default Converter
