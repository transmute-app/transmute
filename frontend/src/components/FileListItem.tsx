import { FaCheckSquare, FaSquare } from 'react-icons/fa'

export interface FileInfo {
  id: string
  original_filename: string
  media_type: string
  extension: string
  size_bytes: number
  created_at?: string
  compatible_formats?: string[]
}

export interface ConversionInfo {
  id: string
  original_filename: string
  media_type: string
  extension: string
  size_bytes: number
  created_at: string
}

interface FileListItemProps {
  file: FileInfo
  conversion?: ConversionInfo
  selectedFormat?: string
  onFormatChange?: (format: string) => void
  onDelete?: () => void
  onDownload?: () => void
  isDeleting?: boolean
  isDownloading?: boolean
  isPending?: boolean // true for pending conversions, false for completed
  showCheckbox?: boolean
  isSelected?: boolean
  onToggleSelect?: () => void
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  const kb = bytes / 1024
  if (kb < 1024) return `${kb.toFixed(1)} KB`
  const mb = kb / 1024
  if (mb < 1024) return `${mb.toFixed(1)} MB`
  const gb = mb / 1024
  if (gb < 1024) return `${gb.toFixed(1)} GB`
  return `${(gb / 1024).toFixed(1)} TB`
}

function FileListItem({
  file,
  conversion,
  selectedFormat,
  onFormatChange,
  onDelete,
  onDownload,
  isDeleting = false,
  isDownloading = false,
  isPending = false,
  showCheckbox = false,
  isSelected = false,
  onToggleSelect,
}: FileListItemProps) {
  const sortedFormats = file.compatible_formats
    ? [...file.compatible_formats].sort()
    : []

  // Get filename - show original for pending, converted name for completed
  const getDisplayFilename = () => {
    const name = file.original_filename || 'download'
    // For pending files, show the original filename
    if (isPending || !conversion) {
      return name
    }
    // For completed conversions, show the new filename with converted extension
    const dot = name.lastIndexOf('.')
    const base = dot > 0 ? name.substring(0, dot) : name
    return base + (conversion.extension || '')
  }

  return (
    <div className="bg-surface-light border border-surface-dark rounded-lg p-4 flex items-center gap-4">
      {showCheckbox && onToggleSelect && (
        <button
          onClick={onToggleSelect}
          className="text-primary hover:text-primary-light text-2xl transition duration-200 flex-shrink-0"
          aria-label={isSelected ? 'Deselect file' : 'Select file'}
        >
          {isSelected ? <FaCheckSquare /> : <FaSquare />}
        </button>
      )}
      <div className="flex-1 min-w-0">
        {/* Format conversion indicator */}
        <div className="flex items-center gap-2 mb-1">
          <span className="text-xs font-mono uppercase bg-surface-dark px-2 py-0.5 rounded text-text-muted">
            {file.media_type}
          </span>
          {(conversion || selectedFormat) && (
            <>
              <span className="text-text-muted text-xs">→</span>
              {isPending && sortedFormats.length > 0 && onFormatChange ? (
                <select
                  value={selectedFormat || ''}
                  onChange={(e) => onFormatChange(e.target.value)}
                  className="text-xs font-mono uppercase bg-primary/20 px-2 py-0.5 rounded text-primary border-none focus:outline-none focus:ring-1 focus:ring-primary cursor-pointer"
                >
                  {sortedFormats.map((format) => (
                    <option key={format} value={format}>
                      {format}
                    </option>
                  ))}
                </select>
              ) : (
                <span className="text-xs font-mono uppercase bg-primary/20 px-2 py-0.5 rounded text-primary">
                  {conversion?.media_type || selectedFormat}
                </span>
              )}
            </>
          )}
        </div>

        {/* Filename */}
        <p className="text-sm font-medium text-text truncate">
          {getDisplayFilename()}
        </p>

        {/* File metadata */}
        <p className="text-xs text-text-muted/70 mt-0.5">
          {file.created_at && (
            <>
              {new Date(file.created_at).toLocaleString()} &middot;{' '}
            </>
          )}
          {formatFileSize(file.size_bytes)}
          {conversion && (
            <> → {formatFileSize(conversion.size_bytes)}</>
          )}
        </p>
      </div>

      {/* Action buttons */}
      <div className="flex gap-2 flex-shrink-0">
        {onDownload && conversion && (
          <button
            onClick={onDownload}
            disabled={isDownloading}
            className="bg-success hover:bg-success-dark text-white text-sm font-semibold py-2 px-4 rounded-lg transition duration-200 shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isDownloading ? 'Downloading...' : 'Download'}
          </button>
        )}
        {onDelete && (
          <button
            onClick={onDelete}
            disabled={isDeleting}
            className="bg-primary/20 hover:bg-primary/40 text-primary-light text-sm font-semibold py-2 px-4 rounded-lg transition duration-200 shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isDeleting ? 'Deleting...' : 'Delete'}
          </button>
        )}
      </div>
    </div>
  )
}

export default FileListItem
