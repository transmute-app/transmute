import { useState, useEffect } from 'react'

interface ConversionInfo {
  id: string
  original_filename: string
  media_type: string
  extension: string
  size_bytes: number
  created_at: string
}

interface FileRecord {
  id: string
  original_filename: string
  media_type: string
  extension: string
  size_bytes: number
  created_at: string
  conversion?: ConversionInfo
}

function Files() {
  const [conversions, setConversions] = useState<FileRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [downloadingId, setDownloadingId] = useState<string | null>(null)

  useEffect(() => {
    const fetchConversions = async () => {
      try {
        const response = await fetch('/api/conversions/complete')
        if (!response.ok) throw new Error('Failed to fetch conversions')
        const data = await response.json()
        setConversions(data.conversions)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load conversions')
      } finally {
        setLoading(false)
      }
    }
    fetchConversions()
  }, [])

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

  const convertedFiles = conversions
    .filter(f => f.conversion)
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())

  return (
    <div className="min-h-screen bg-gradient-to-br from-surface-dark to-surface-light p-8">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-3xl font-bold text-primary mb-6">Files</h1>

        {error && (
          <div className="p-3 bg-primary/20 border border-primary rounded-lg text-primary-light text-sm mb-4">
            {error}
          </div>
        )}

        {loading && (
          <p className="text-text-muted text-sm">Loading conversions...</p>
        )}

        {!loading && convertedFiles.length === 0 && (
          <p className="text-text-muted text-sm">No converted files yet.</p>
        )}

        {!loading && convertedFiles.length > 0 && (
          <div className="space-y-3">
            {convertedFiles.map(file => (
              <div
                key={file.id}
                className="bg-surface-light border border-surface-dark rounded-lg p-4 flex items-center gap-4"
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs font-mono uppercase bg-surface-dark px-2 py-0.5 rounded text-text-muted">
                      {file.media_type}
                    </span>
                    <span className="text-text-muted text-xs">→</span>
                    <span className="text-xs font-mono uppercase bg-primary/20 px-2 py-0.5 rounded text-primary">
                      {file.conversion!.media_type}
                    </span>
                  </div>
                  <p className="text-sm font-medium text-text truncate">
                    {(() => {
                      const name = file.original_filename || 'download'
                      const dot = name.lastIndexOf('.')
                      const base = dot > 0 ? name.substring(0, dot) : name
                      return base + (file.conversion!.extension || '')
                    })()}
                  </p>
                  <p className="text-xs text-text-muted/70 mt-0.5">
                    {new Date(file.created_at).toLocaleString()} &middot;{' '}
                    {(file.size_bytes / 1024).toFixed(1)} KB → {(file.conversion!.size_bytes / 1024).toFixed(1)} KB
                  </p>
                </div>
                <button
                  onClick={() => handleDownload(file.conversion!)}
                  disabled={downloadingId === file.conversion!.id}
                  className="flex-shrink-0 bg-success hover:bg-success-dark text-white text-sm font-semibold py-2 px-4 rounded-lg transition duration-200 shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {downloadingId === file.conversion!.id ? 'Downloading...' : 'Download'}
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export default Files
