import { useState, useEffect } from 'react'
import FileListItem, { FileInfo, ConversionInfo } from '../components/FileListItem'
import { FaCheckSquare, FaSquare } from 'react-icons/fa'

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
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [deletingSelected, setDeletingSelected] = useState(false)
  const [downloadingSelected, setDownloadingSelected] = useState(false)

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
    if (selectedIds.size === sortedConversions.length) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(sortedConversions.map(c => c.id)))
    }
  }

  const handleDeleteSelected = async () => {
    if (selectedIds.size === 0) return
    setDeletingSelected(true)
    setError(null)

    const idsToDelete = Array.from(selectedIds)
    for (const conversionId of idsToDelete) {
      try {
        const response = await fetch(`/api/conversions/${conversionId}`, { method: 'DELETE' })
        if (!response.ok) throw new Error('Delete failed')
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Delete failed')
      }
    }

    setConversions(prev => prev.filter(c => !selectedIds.has(c.id)))
    setSelectedIds(new Set())
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
      setDownloadingSelected(false)
    }
  }

  const sortedConversions = conversions
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())

  return (
    <div className="min-h-screen bg-gradient-to-br from-surface-dark to-surface-light p-8">
      <div className="max-w-4xl mx-auto">
        <div className="flex justify-between items-center mb-6 min-h-[4rem]">
          <h1 className="text-3xl font-bold text-primary">History</h1>
          <div className="flex gap-3">
            {selectedIds.size > 0 && (
              <>
                <button
                  onClick={handleDownloadSelected}
                  disabled={downloadingSelected}
                  className="bg-success hover:bg-success-dark text-white font-semibold py-2 px-6 rounded-lg transition duration-200 shadow-md hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {downloadingSelected ? 'Downloading...' : `Download ${selectedIds.size} File${selectedIds.size > 1 ? 's' : ''}`}
                </button>
                <button
                  onClick={handleDeleteSelected}
                  disabled={deletingSelected}
                  className="bg-primary/20 hover:bg-primary/40 text-primary-light font-semibold py-2 px-6 rounded-lg transition duration-200 shadow-md hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {deletingSelected ? 'Deleting...' : `Delete ${selectedIds.size} File${selectedIds.size > 1 ? 's' : ''}`}
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
          <p className="text-text-muted text-sm">Loading conversions...</p>
        )}

        {!loading && sortedConversions.length === 0 && (
          <p className="text-text-muted text-sm">No converted files yet.</p>
        )}

        {!loading && sortedConversions.length > 0 && (
          <>
            <div className="mb-4 flex justify-start">
              <button
                onClick={toggleSelectAll}
                className="bg-surface-light hover:bg-surface-dark text-text-muted hover:text-text text-sm font-medium py-1.5 px-4 rounded-lg transition duration-200"
              >
                {selectedIds.size === sortedConversions.length ? 'Deselect All' : 'Select All'}
              </button>
            </div>
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
                <div key={conversion.id} className="flex items-center gap-3">
                  <button
                    onClick={() => toggleSelection(conversion.id)}
                    className="text-primary hover:text-primary-light text-2xl transition duration-200 flex-shrink-0"
                    aria-label="Select conversion"
                  >
                    {selectedIds.has(conversion.id) ? <FaCheckSquare /> : <FaSquare />}
                  </button>
                  <div className="flex-1">
                    <FileListItem
                      file={fileInfo}
                      conversion={conversionInfo}
                      onDownload={() => handleDownload(conversion)}
                      onDelete={() => handleDelete(conversion.id)}
                      isDeleting={deletingId === conversion.id}
                      isDownloading={downloadingId === conversion.id}
                      isPending={false}
                    />
                  </div>
                </div>
              )
            })}
            </div>
          </>
        )}
      </div>
    </div>
  )
}

export default History
