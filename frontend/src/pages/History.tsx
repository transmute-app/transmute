import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import FileTable, { FileInfo, ConversionInfo } from '../components/FileTable'
import PreviewModal, { isPreviewable } from '../components/PreviewModal'
import { authFetch as fetch } from '../utils/api'
import { downloadBlob } from '../utils/download'
import { stripExtension } from '../utils/filename'

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

function History() {
  const [conversions, setConversions] = useState<ConversionRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [downloadingId, setDownloadingId] = useState<string | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [deletingSelected, setDeletingSelected] = useState(false)
  const [downloadingSelected, setDownloadingSelected] = useState(false)
  const [previewConversion, setPreviewConversion] = useState<ConversionRecord | null>(null)
  const { t } = useTranslation()

  useEffect(() => {
    const fetchConversions = async () => {
      try {
        const response = await fetch('/api/conversions/complete')
        if (!response.ok) throw new Error(t('history.fetchFailed'))
        const data = await response.json()
        setConversions(data.conversions)
      } catch (err) {
        setError(err instanceof Error ? err.message : t('history.loadFailed'))
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

  return (
    <div className="min-h-full bg-gradient-to-br from-surface-dark to-surface-light p-8 pb-12">
      <div className="max-w-4xl mx-auto">
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

        {!loading && conversions.length === 0 && (
          <p className="text-text-muted text-sm">{t('history.noConversions')}</p>
        )}

        {!loading && conversions.length > 0 && (
          <FileTable
            rows={conversions.map(conversion => {
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
                onDownload: () => handleDownload(conversion),
                onDelete: () => handleDelete(conversion.id),
                onPreview: isPreviewable(conversion.media_type) ? () => { const name = conversion.original_filename || 'download'; const base = stripExtension(name); setPreviewConversion({ ...conversion, original_filename: base + (conversion.extension || '') }) } : undefined,
                isDeleting: deletingId === conversion.id,
                isDownloading: downloadingId === conversion.id,
              }
            })}
            showCheckbox={true}
            selectedIds={selectedIds}
            onToggleSelect={toggleSelection}
            onToggleSelectAll={toggleSelectAll}
          />
        )}

        {previewConversion && (
          <PreviewModal
            fileId={previewConversion.id}
            filename={previewConversion.original_filename}
            mediaType={previewConversion.media_type}
            onClose={() => setPreviewConversion(null)}
          />
        )}
      </div>
    </div>
  )
}

export default History
