import { useState, useEffect } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import FileListItem, { FileInfo, ConversionInfo } from '../components/FileListItem'

interface PendingFile {
  file: FileInfo
  selectedFormat: string
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
  const [convertingIndex, setConvertingIndex] = useState<number | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [downloadingId, setDownloadingId] = useState<string | null>(null)
  const [downloadingAll, setDownloadingAll] = useState(false)
  const [autoDownload, setAutoDownload] = useState(false)

  // Load auto-download setting
  useEffect(() => {
    fetch('/api/settings')
      .then(r => r.ok ? r.json() : Promise.reject())
      .then(data => setAutoDownload(!!data.auto_download))
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
        return {
          file,
          selectedFormat: sortedFormats[0] || '',
        }
      })
      setPendingFiles(prev => [...newPendingFiles, ...prev])
      // Clear the location state to prevent re-adding on refresh
      navigate(location.pathname, { replace: true })
    }
  }, [location.state])

  const handleFileSelect = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files
    if (!files || files.length === 0) return

    setUploading(true)
    setError(null)
    setUploadCount(files.length)

    const newPendingFiles: PendingFile[] = []

    for (const file of Array.from(files)) {
      const formData = new FormData()
      formData.append('file', file)

      try {
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

        // Set default format (alphabetically first)
        const sortedFormats = fileInfo.compatible_formats
          ? [...fileInfo.compatible_formats].sort()
          : []
        const defaultFormat = sortedFormats[0] || ''

        newPendingFiles.push({
          file: fileInfo,
          selectedFormat: defaultFormat,
        })
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Upload failed')
      }
    }

    setPendingFiles((prev) => [...prev, ...newPendingFiles])
    event.target.value = ''
    setUploading(false)
    setUploadCount(0)
  }

  const handleFormatChange = (fileId: string, format: string) => {
    setPendingFiles((prev) =>
      prev.map((pf) =>
        pf.file.id === fileId ? { ...pf, selectedFormat: format } : pf
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

    const filesToConvert = [...pendingFiles]
    const newCompletedConversions: CompletedConversion[] = []

    for (let i = 0; i < filesToConvert.length; i++) {
      const { file, selectedFormat } = filesToConvert[i]
      setConvertingIndex(i)

      if (!selectedFormat) continue

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
          throw new Error(`Conversion failed for ${file.original_filename}: ${response.statusText}`)
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

        newCompletedConversions.push({
          file,
          conversion: conversionInfo,
        })
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Conversion failed')
      }
    }

    setCompletedConversions((prev) => [...newCompletedConversions, ...prev])
    setPendingFiles([])
    setConverting(false)
    setConvertingIndex(null)

    if (autoDownload && newCompletedConversions.length > 0) {
      await triggerDownloads(newCompletedConversions)
    }
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

  // Initial landing page - shown before any files are selected
  if (!hasStarted && !uploading) {
    return (
      <div className="h-full bg-gradient-to-br from-surface-dark to-surface-light flex items-center justify-center p-4">
        <div className="bg-surface-light rounded-lg shadow-xl p-8 max-w-xl w-full border border-surface-dark">
          <h1 className="text-4xl font-bold text-center text-primary mb-6">
            Transmute
          </h1>
          
          <div className="space-y-4">
            <div>
              <input
                type="file"
                multiple
                onChange={handleFileSelect}
                disabled={uploading}
                className="block w-full text-sm text-text-muted
                  file:mr-4 file:py-2 file:px-4
                  file:rounded-lg file:border-0
                  file:text-sm file:font-semibold
                  file:bg-primary/20 file:text-primary
                  hover:file:bg-primary/30
                  cursor-pointer
                  disabled:opacity-50 disabled:cursor-not-allowed"
              />
            </div>

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
          <input
            type="file"
            multiple
            onChange={handleFileSelect}
            disabled={uploading || converting}
            className="block w-full text-sm text-text-muted
              file:mr-4 file:py-2 file:px-4
              file:rounded-lg file:border-0
              file:text-sm file:font-semibold
              file:bg-primary/20 file:text-primary
              hover:file:bg-primary/30
              cursor-pointer
              disabled:opacity-50 disabled:cursor-not-allowed"
          />
          {uploading && (
            <p className="text-sm text-primary font-medium mt-2">
              Uploading {uploadCount} file{uploadCount > 1 ? 's' : ''}...
            </p>
          )}
        </div>

        {error && (
          <div className="p-3 bg-primary/20 border border-primary rounded-lg text-primary-light text-sm mb-4">
            {error}
          </div>
        )}

        {/* Pending conversions section */}
        {hasPendingFiles && (
          <div className="mb-8">
            <h2 className="text-xl font-semibold text-text mb-4">
              Pending Conversions ({pendingFiles.length})
            </h2>
            <div className="space-y-3 mb-4">
              {pendingFiles.map((pf, index) => (
                <div key={pf.file.id} className="relative">
                  {converting && convertingIndex === index && (
                    <div className="absolute inset-0 bg-surface-dark/50 rounded-lg flex items-center justify-center z-10">
                      <span className="text-sm text-primary font-medium">Converting...</span>
                    </div>
                  )}
                  <FileListItem
                    file={pf.file}
                    selectedFormat={pf.selectedFormat}
                    onFormatChange={(format) => handleFormatChange(pf.file.id, format)}
                    onDelete={() => handleDelete(pf.file.id, true)}
                    isDeleting={deletingId === pf.file.id}
                    isPending={true}
                  />
                </div>
              ))}
            </div>
            <button
              onClick={handleConvertAll}
              disabled={converting || pendingFiles.length === 0}
              className="w-full bg-primary hover:bg-primary-dark text-text font-semibold py-3 px-6 rounded-lg transition duration-200 shadow-md hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {converting
                ? `Converting ${(convertingIndex ?? 0) + 1} of ${pendingFiles.length}...`
                : `Convert ${pendingFiles.length} File${pendingFiles.length > 1 ? 's' : ''}`}
            </button>
          </div>
        )}

        {/* Completed conversions section */}
        {hasCompletedConversions && (
          <div>
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-semibold text-text">
                Completed Conversions ({completedConversions.length})
              </h2>
              {completedConversions.length > 1 && (
                <button
                  onClick={handleDownloadAll}
                  disabled={downloadingAll}
                  className="bg-success hover:bg-success-dark text-white font-semibold py-2 px-6 rounded-lg transition duration-200 shadow-md hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {downloadingAll ? 'Downloading...' : `Download All ${completedConversions.length} Files`}
                </button>
              )}
            </div>
            <div className="space-y-3">
              {completedConversions.map((cc) => (
                <FileListItem
                  key={cc.conversion.id}
                  file={cc.file}
                  conversion={cc.conversion}
                  onDownload={() => handleDownload(cc.conversion)}
                  onDelete={() => handleDelete(cc.file.id, false)}
                  isDeleting={deletingId === cc.file.id}
                  isDownloading={downloadingId === cc.conversion.id}
                  isPending={false}
                />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default Converter
