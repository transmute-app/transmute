import { lazy, Suspense, useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import FileTable, { FileInfo, type SortColumn, type SortDirection } from '../components/FileTable'
import Pagination from '../components/Pagination'
import { isPreviewable } from '../components/previewUtils'
import { authFetch as fetch } from '../utils/api'

const PreviewModal = lazy(() => import('../components/PreviewModal'))

const PAGE_SIZE = 20

interface PaginationInfo {
  total_items: number
  total_pages: number
  current_page: number
  limit: number | null
  has_next: boolean
  has_prev: boolean
}

function Files() {
  const [files, setFiles] = useState<FileInfo[]>([])
  const [pagination, setPagination] = useState<PaginationInfo | null>(null)
  const [page, setPage] = useState(1)
  const [sortColumn, setSortColumn] = useState<SortColumn>('date')
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc')
  // Bumped after deletes so the current page is fetched again and refilled.
  const [reloadCount, setReloadCount] = useState(0)
  const [loading, setLoading] = useState(true)
  const [fetching, setFetching] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [deletingSelected, setDeletingSelected] = useState(false)
  const [previewFile, setPreviewFile] = useState<FileInfo | null>(null)
  const navigate = useNavigate()
  const { t } = useTranslation()

  useEffect(() => {
    // Ignore the response if a newer request has started (quick clicks on Next).
    let cancelled = false
    const fetchFiles = async () => {
      setFetching(true)
      try {
        const params = new URLSearchParams({
          page: String(page),
          limit: String(PAGE_SIZE),
          sort: sortColumn,
          order: sortDirection,
        })
        const response = await fetch(`/api/files?${params}`)
        if (!response.ok) throw new Error(t('files.fetchFailed'))
        const data = await response.json()
        if (cancelled) return
        const info: PaginationInfo = data.pagination
        // This page no longer exists (its files were deleted): step back to the last page.
        if (data.files.length === 0 && page > 1) {
          setPage(Math.max(1, info.total_pages))
          return
        }
        setFiles(data.files)
        setPagination(info)
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : t('files.loadFailed'))
      } finally {
        if (!cancelled) {
          setLoading(false)
          setFetching(false)
        }
      }
    }
    fetchFiles()
    return () => {
      cancelled = true
    }
  }, [page, sortColumn, sortDirection, reloadCount, t])

  const reload = () => setReloadCount(count => count + 1)

  // Selection only ever refers to the rows on screen, so it is cleared whenever
  // the visible page changes.
  const goToPage = (nextPage: number) => {
    setError(null)
    setSelectedIds(new Set())
    setPage(nextPage)
  }

  const handleSortChange = (column: SortColumn, direction: SortDirection) => {
    setError(null)
    setSelectedIds(new Set())
    setSortColumn(column)
    setSortDirection(direction)
    setPage(1)
  }

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
      reload()
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
    reload()
  }

  const handleBringToConverter = () => {
    const selectedFiles = files.filter(f => selectedIds.has(f.id))
    navigate('/', { state: { files: selectedFiles } })
  }

  return (
    <div className="min-h-full bg-gradient-to-br from-surface-dark to-surface-light p-8 pb-12">
      <div className="max-w-6xl mx-auto">
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
            sortColumn={sortColumn}
            sortDirection={sortDirection}
            onSortChange={handleSortChange}
            className={fetching ? 'opacity-60' : undefined}
          />
        )}

        {!loading && files.length > 0 && (
          <Pagination
            page={page}
            totalPages={pagination?.total_pages ?? 1}
            onPageChange={goToPage}
            disabled={fetching}
          />
        )}

        {previewFile && (
          <Suspense fallback={null}>
            <PreviewModal
              fileId={previewFile.id}
              filename={previewFile.original_filename}
              mediaType={previewFile.media_type}
              onClose={() => setPreviewFile(null)}
            />
          </Suspense>
        )}
      </div>
    </div>
  )
}

export default Files
