import { useState } from 'react'
import { FaCheckSquare, FaSquare, FaSort, FaSortUp, FaSortDown, FaDownload, FaTrash, FaEye } from 'react-icons/fa'
import { stripExtension } from '../utils/filename'
import FormatDropdown from './FormatDropdown'

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

export interface FileTableRow {
  id: string
  file: FileInfo
  conversion?: ConversionInfo
  selectedFormat?: string
  status?: 'pending' | 'failed'
  statusMessage?: string
  onFormatChange?: (format: string) => void
  onDelete?: () => void
  onDownload?: () => void
  onPreview?: () => void
  isDeleting?: boolean
  isDownloading?: boolean
}

interface FileTableProps {
  rows: FileTableRow[]
  isPending?: boolean
  showCheckbox?: boolean
  showDate?: boolean
  selectedIds?: Set<string>
  onToggleSelect?: (id: string) => void
  onToggleSelectAll?: () => void
  converting?: boolean
}

type SortColumn = 'filename' | 'type' | 'size' | 'date'
type SortDirection = 'asc' | 'desc'

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  const kb = bytes / 1024
  if (kb < 1024) return `${kb.toFixed(1)} KB`
  const mb = kb / 1024
  if (mb < 1024) return `${mb.toFixed(1)} MB`
  const gb = mb / 1024
  if (gb < 1024) return `${gb.toFixed(1)} GB`
  return `${(gb / 1024).toFixed(1)} TB`
}

function FileTable({
  rows,
  isPending = false,
  showCheckbox = false,
  showDate = true,
  selectedIds,
  onToggleSelect,
  onToggleSelectAll,
  converting = false,
}: FileTableProps) {
  const [sortColumn, setSortColumn] = useState<SortColumn>('date')
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc')

  const handleSort = (column: SortColumn) => {
    if (sortColumn === column) {
      setSortDirection(prev => (prev === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortColumn(column)
      setSortDirection(column === 'date' ? 'desc' : 'asc')
    }
  }

  const sortedRows = [...rows].sort((a, b) => {
    let cmp = 0
    switch (sortColumn) {
      case 'filename':
        cmp = (a.file.original_filename || '').localeCompare(b.file.original_filename || '')
        break
      case 'type': {
        const typeA = a.selectedFormat || a.conversion?.media_type || a.file.media_type || ''
        const typeB = b.selectedFormat || b.conversion?.media_type || b.file.media_type || ''
        cmp = typeA.localeCompare(typeB)
        break
      }
      case 'size':
        cmp = a.file.size_bytes - b.file.size_bytes
        break
      case 'date': {
        const dateA = a.conversion?.created_at || a.file.created_at || ''
        const dateB = b.conversion?.created_at || b.file.created_at || ''
        cmp = new Date(dateA).getTime() - new Date(dateB).getTime()
        break
      }
    }
    return sortDirection === 'asc' ? cmp : -cmp
  })

  const SortIcon = ({ column }: { column: SortColumn }) => {
    if (sortColumn !== column) return <FaSort className="inline ml-1 opacity-30 text-[0.6rem]" />
    return sortDirection === 'asc'
      ? <FaSortUp className="inline ml-1 text-[0.6rem]" />
      : <FaSortDown className="inline ml-1 text-[0.6rem]" />
  }

  const allSelected = rows.length > 0 && selectedIds?.size === rows.length

  const getDisplayFilename = (row: FileTableRow) => {
    const name = row.file.original_filename || 'download'
    if (isPending || !row.conversion) return name
    const base = stripExtension(name)
    return base + (row.conversion.extension || '')
  }

  const hasActions = rows.some(r => r.onDownload || r.onDelete || r.onPreview)

  if (rows.length === 0) return null

  return (
    <div className="overflow-x-auto rounded-lg border border-surface-dark">
      <table className="w-full text-sm text-left">
        <thead className="text-xs uppercase bg-surface-dark text-text-muted">
          <tr>
            {showCheckbox && (
              <th className="px-3 py-3 w-10">
                {onToggleSelectAll && (
                  <button
                    onClick={onToggleSelectAll}
                    className="text-primary hover:text-primary-light text-lg transition duration-200"
                    aria-label={allSelected ? 'Deselect all' : 'Select all'}
                  >
                    {allSelected ? <FaCheckSquare /> : <FaSquare />}
                  </button>
                )}
              </th>
            )}
            <th 
              className="px-4 py-3"
              aria-sort={sortColumn === 'filename' ? (sortDirection === 'asc' ? 'ascending' : 'descending') : 'none'}
            >
              <button
                onClick={() => handleSort('filename')}
                className="flex items-center gap-1 hover:text-text transition uppercase"
              >
                Filename <SortIcon column="filename" />
              </button>
            </th>
            <th
              className="px-4 py-3"
              aria-sort={sortColumn=== 'type' ? (sortDirection === 'asc' ? 'ascending' : 'descending') : 'none'}
            >
              <button
                onClick={() => handleSort('type')}
                className="flex items-center gap-1 hover:text-text transition uppercase"
              >
                Format <SortIcon column="type" />
              </button>
            </th>
            <th
              className="px-4 py-3"
              aria-sort={sortColumn=== 'size' ? (sortDirection === 'asc' ? 'ascending' : 'descending') : 'none'}
            >
              <button
                onClick={() => handleSort('size')}
                className="flex items-center gap-1 hover:text-text transition uppercase"
              >
                Size <SortIcon column="size" />
              </button>
            </th>
            {showDate && (
              <th
                className="px-4 py-3"
                aria-sort={sortColumn=== 'date' ? (sortDirection === 'asc' ? 'ascending' : 'descending') : 'none'}
              >
                <button
                  onClick={() => handleSort('date')}
                  className="flex items-center gap-1 hover:text-text transition uppercase"
                >
                  Date <SortIcon column="date" />
                </button>
              </th>
            )}
            {hasActions && (
              <th className="px-4 py-3 text-right">Actions</th>
            )}
          </tr>
        </thead>
        <tbody>
          {sortedRows.map(row => (
            <tr
              key={row.id}
              className={`border-t border-surface-dark ${row.status === 'failed' ? 'bg-primary/10 hover:bg-primary/15' : 'bg-surface-light hover:bg-surface-dark/50'} transition duration-100${
                converting ? ' opacity-50 pointer-events-none' : ''
              }`}
            >
              {showCheckbox && (
                <td className="px-3 py-3">
                  {onToggleSelect && (
                    <button
                      onClick={() => onToggleSelect(row.id)}
                      className="text-primary hover:text-primary-light text-lg transition duration-200"
                      aria-label={selectedIds?.has(row.id) ? 'Deselect' : 'Select'}
                    >
                      {selectedIds?.has(row.id) ? <FaCheckSquare /> : <FaSquare />}
                    </button>
                  )}
                </td>
              )}
              <td className="px-4 py-3">
                <div className="max-w-[16rem]">
                  <span
                    className="font-medium text-text truncate block"
                    title={getDisplayFilename(row)}
                  >
                    {getDisplayFilename(row)}
                  </span>
                  {row.status === 'failed' && (
                    <div className="mt-1">
                      <span className="inline-block text-[0.65rem] font-semibold uppercase tracking-wide bg-primary/20 px-2 py-0.5 rounded text-primary-light">
                        Failed
                      </span>
                      {row.statusMessage && (
                        <p className="mt-1 text-xs text-primary-light/90 break-words" title={row.statusMessage}>
                          {row.statusMessage}
                        </p>
                      )}
                    </div>
                  )}
                </div>
              </td>
              <td className="px-4 py-3 whitespace-nowrap">
                  {(row.conversion || row.selectedFormat) ? (
                    isPending && row.file.compatible_formats && row.file.compatible_formats.length > 0 && row.onFormatChange ? (
                      <FormatDropdown
                        value={row.selectedFormat || ''}
                        formats={row.file.compatible_formats!}
                        onChange={(format) => row.onFormatChange!(format)}
                        title={`${row.file.media_type} → ${row.selectedFormat || ''}`}
                      />
                    ) : (
                      <span
                        className="text-xs font-mono uppercase bg-primary/20 px-2 py-0.5 rounded text-primary"
                        title={`${row.file.media_type} → ${row.conversion?.media_type || row.selectedFormat}`}
                      >
                        {row.conversion?.media_type || row.selectedFormat}
                      </span>
                    )
                  ) : (
                    <span className="text-xs font-mono uppercase bg-surface-dark px-2 py-0.5 rounded text-text-muted">
                      {row.file.media_type}
                    </span>
                  )}
              </td>
              <td
                className="px-4 py-3 text-text-muted whitespace-nowrap"
                title={row.conversion ? `${formatFileSize(row.file.size_bytes)} → ${formatFileSize(row.conversion.size_bytes)}` : undefined}
              >
                {formatFileSize(row.conversion?.size_bytes ?? row.file.size_bytes)}
              </td>
              {showDate && (
                <td className="px-4 py-3 text-text-muted whitespace-nowrap">
                  {(row.file.created_at || row.conversion?.created_at) &&
                    new Date(row.conversion?.created_at || row.file.created_at!).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })
                  }
                </td>
              )}
              {hasActions && (
                <td className="px-4 py-3">
                  <div className="flex gap-1.5 justify-end">
                    {row.onPreview && (
                      <button
                        onClick={row.onPreview}
                        className="p-2 rounded-lg text-text-muted hover:text-text hover:bg-surface-dark transition duration-200"
                        title="Preview"
                      >
                        <FaEye className="text-sm" />
                      </button>
                    )}
                    {row.onDownload && row.conversion && (
                      <button
                        onClick={row.onDownload}
                        disabled={row.isDownloading}
                        className="p-2 rounded-lg text-success hover:bg-success/20 transition duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
                        title="Download"
                      >
                        <FaDownload className="text-sm" />
                      </button>
                    )}
                    {row.onDelete && (
                      <button
                        onClick={row.onDelete}
                        disabled={row.isDeleting}
                        className="p-2 rounded-lg text-primary-light hover:bg-primary/20 transition duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
                        title="Delete"
                      >
                        <FaTrash className="text-sm" />
                      </button>
                    )}
                  </div>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default FileTable
