import { useState, useEffect } from 'react'
import FileListItem, { FileInfo, ConversionInfo } from '../components/FileListItem'

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
  original_file?: OriginalFileInfo
}

function History() {
  const [conversions, setConversions] = useState<ConversionRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [downloadingId, setDownloadingId] = useState<string | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)

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

  const handleDownload = async (conversion: ConversionRecord) => {
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

  const handleDelete = async (conversionId: string) => {
    setDeletingId(conversionId)
    try {
      const response = await fetch(`/api/conversions/${conversionId}`, { method: 'DELETE' })
      if (!response.ok) throw new Error('Delete failed')
      setConversions(prev => prev.filter(c => c.id !== conversionId))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Delete failed')
    } finally {
      setDeletingId(null)
    }
  }

  const sortedConversions = conversions
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())

  return (
    <div className="min-h-screen bg-gradient-to-br from-surface-dark to-surface-light p-8">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-3xl font-bold text-primary mb-6">History</h1>

        {error && (
          <div className="p-3 bg-primary/20 border border-primary rounded-lg text-primary-light text-sm mb-4">
            {error}
          </div>
        )}

        {loading && (
          <p className="text-text-muted text-sm">Loading conversions...</p>
        )}

        {!loading && sortedConversions.length === 0 && (
          <p className="text-text-muted text-sm">No converted files yet.</p>
        )}

        {!loading && sortedConversions.length > 0 && (
          <div className="space-y-3">
            {sortedConversions.map(conversion => {
              // Use original file metadata if available, otherwise use conversion metadata
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
              }
              return (
                <FileListItem
                  key={conversion.id}
                  file={fileInfo}
                  conversion={conversionInfo}
                  onDownload={() => handleDownload(conversion)}
                  onDelete={() => handleDelete(conversion.id)}
                  isDeleting={deletingId === conversion.id}
                  isDownloading={downloadingId === conversion.id}
                  isPending={false}
                />
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}

export default History
