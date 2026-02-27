import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import FileListItem, { FileInfo } from '../components/FileListItem'

function Files() {
  const [files, setFiles] = useState<FileInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [deletingSelected, setDeletingSelected] = useState(false)
  const navigate = useNavigate()

  useEffect(() => {
    const fetchFiles = async () => {
      try {
        const response = await fetch('/api/files')
        if (!response.ok) throw new Error('Failed to fetch files')
        const data = await response.json()
        setFiles(data.files)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load files')
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
      if (!response.ok) throw new Error('Delete failed')
      setFiles(prev => prev.filter(f => f.id !== fileId))
      setSelectedIds(prev => {
        const newSet = new Set(prev)
        newSet.delete(fileId)
        return newSet
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Delete failed')
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
    const idsToDelete = Array.from(selectedIds)
    
    for (const fileId of idsToDelete) {
      try {
        const response = await fetch(`/api/files/${fileId}`, { method: 'DELETE' })
        if (!response.ok) throw new Error('Delete failed')
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Delete failed')
      }
    }
    
    setFiles(prev => prev.filter(f => !selectedIds.has(f.id)))
    setSelectedIds(new Set())
    setDeletingSelected(false)
  }

  const handleBringToConverter = () => {
    const selectedFiles = files.filter(f => selectedIds.has(f.id))
    navigate('/', { state: { files: selectedFiles } })
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-surface-dark to-surface-light p-8">
      <div className="max-w-4xl mx-auto">
        <div className="flex justify-between items-center mb-6 min-h-[4rem]">
          <h1 className="text-3xl font-bold text-primary">Files</h1>
          <div className="flex gap-3">
            {selectedIds.size > 0 && (
              <>
                <button
                  onClick={handleBringToConverter}
                  className="bg-success hover:bg-success-dark text-white font-semibold py-2 px-6 rounded-lg transition duration-200 shadow-md hover:shadow-lg"
                >
                  Convert {selectedIds.size} File{selectedIds.size > 1 ? 's' : ''}
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
          <p className="text-text-muted text-sm">Loading files...</p>
        )}

        {!loading && files.length === 0 && (
          <p className="text-text-muted text-sm">No uploaded files yet.</p>
        )}

        {!loading && files.length > 0 && (
          <>
            <div className="mb-4 flex justify-start">
              <button
                onClick={toggleSelectAll}
                className="bg-surface-light hover:bg-surface-dark text-text-muted hover:text-text text-sm font-medium py-1.5 px-4 rounded-lg transition duration-200"
              >
                {selectedIds.size === files.length ? 'Deselect All' : 'Select All'}
              </button>
            </div>
            <div className="space-y-3">
              {files.map(file => (
                <FileListItem
                  key={file.id}
                  file={file}
                  onDelete={() => handleDelete(file.id)}
                  isDeleting={deletingId === file.id}
                  isPending={true}
                  showCheckbox={true}
                  isSelected={selectedIds.has(file.id)}
                  onToggleSelect={() => toggleSelection(file.id)}
                />
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  )
}

export default Files
