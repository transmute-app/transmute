import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import FileTable, { FileInfo } from '../components/FileTable'
import PreviewModal, { isPreviewable } from '../components/PreviewModal'
import { authFetch as fetch } from '../utils/api'

function Files() {
  const [files, setFiles] = useState<FileInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [deletingSelected, setDeletingSelected] = useState(false)
  const [previewFile, setPreviewFile] = useState<FileInfo | null>(null)
  const navigate = useNavigate()
  const { t } = useTranslation()

  useEffect(() => {
    const fetchFiles = async () => {
      try {
        const response = await fetch('/api/files')
        if (!response.ok) throw new Error(t('files.fetchFailed'))
        const data = await response.json()
        setFiles(data.files)
      } catch (err) {
        setError(err instanceof Error ? err.message : t('files.loadFailed'))
      } finally {
        setLoading(false)
      }
    }
    fetchFiles()
  }, [])

  const handleDelete = async (fileId: string) => {
    setDeletingId(fileId)
    try {
      const response = await fetch(`/api/files/${fileId}`, { method: 'DELETE' })
      if (!response.ok) throw new Error(t('files.deleteFailed'))
      setFiles(prev => prev.filter(f => f.id !== fileId))
      setSelectedIds(prev => {
        const newSet = new Set(prev)
        newSet.delete(fileId)
        return newSet
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : t('files.deleteFailed'))
    } finally {
      setDeletingId(null)
    }
  }

  const toggleSelection = (fileId: string) => {
    setSelectedIds(prev => {
      const newSet = new Set(prev)
      if (newSet.has(fileId)) {
        newSet.delete(fileId)
      } else {
        newSet.add(fileId)
      }
      return newSet
    })
  }

  const toggleSelectAll = () => {
    if (selectedIds.size === files.length) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(files.map(f => f.id)))
    }
  }

  const handleDeleteSelected = async () => {
    if (selectedIds.size === 0) return
    
    setDeletingSelected(true)
    setError(null)
    const idsToDelete = Array.from(selectedIds)
    
    const results = await Promise.allSettled(
      idsToDelete.map(async (fileId) => {
        const response = await fetch(`/api/files/${fileId}`, { method: 'DELETE' })
        if (!response.ok) throw new Error(`Delete failed for ${fileId}`)
        setFiles(prev => prev.filter(f => f.id !== fileId))
        setSelectedIds(prev => {
          const newSet = new Set(prev)
          newSet.delete(fileId)
          return newSet
        })
      })
    )

    const errors = results
      .filter((r): r is PromiseRejectedResult => r.status === 'rejected')
      .map(r => (r.reason instanceof Error ? r.reason.message : t('files.deleteFailed')))

    if (errors.length > 0) {
      setError(errors.join('; '))
    }

    setDeletingSelected(false)
  }

  const handleBringToConverter = () => {
    const selectedFiles = files.filter(f => selectedIds.has(f.id))
    navigate('/', { state: { files: selectedFiles } })
  }

  return (
    <div className="min-h-full bg-gradient-to-br from-surface-dark to-surface-light p-8 pb-12">
      <div className="max-w-4xl mx-auto">
        <div className="flex justify-between items-center mb-6 min-h-[4rem]">
          <h1 className="text-3xl font-bold text-primary">{t('files.title')}</h1>
          <div className="flex gap-3">
            {selectedIds.size > 0 && (
              <>
                <button
                  onClick={handleBringToConverter}
                  className="bg-success hover:bg-success-dark text-white font-semibold py-2 px-6 rounded-lg transition duration-200 shadow-md hover:shadow-lg"
                >
                  {t('files.convertSelected', { count: selectedIds.size })}
                </button>
                <button
                  onClick={handleDeleteSelected}
                  disabled={deletingSelected}
                  className="bg-primary/20 hover:bg-primary/40 text-primary-light font-semibold py-2 px-6 rounded-lg transition duration-200 shadow-md hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {deletingSelected ? t('files.deleting') : t('files.deleteSelected', { count: selectedIds.size })}
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
          <p className="text-text-muted text-sm">{t('files.loading')}</p>
        )}

        {!loading && files.length === 0 && (
          <p className="text-text-muted text-sm">{t('files.noFiles')}</p>
        )}

        {!loading && files.length > 0 && (
          <FileTable
            rows={files.map(file => ({
              id: file.id,
              file,
              onDelete: () => handleDelete(file.id),
              onPreview: isPreviewable(file.media_type) ? () => setPreviewFile(file) : undefined,
              isDeleting: deletingId === file.id,
            }))}
            isPending={true}
            showCheckbox={true}
            selectedIds={selectedIds}
            onToggleSelect={toggleSelection}
            onToggleSelectAll={toggleSelectAll}
          />
        )}

        {previewFile && (
          <PreviewModal
            fileId={previewFile.id}
            filename={previewFile.original_filename}
            mediaType={previewFile.media_type}
            onClose={() => setPreviewFile(null)}
          />
        )}
      </div>
    </div>
  )
}

export default Files
