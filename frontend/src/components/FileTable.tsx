import { useState } from 'react'
import { FaCheckSquare, FaSquare, FaSort, FaSortUp, FaSortDown, FaDownload, FaTrash, FaEye, FaTimes, FaRedo, FaCheckCircle, FaSpinner, FaHourglassHalf, FaTimesCircle, FaBan } from 'react-icons/fa'
import { useTranslation } from 'react-i18next'
import { stripExtension } from '../utils/filename'
import FormatDropdown from './FormatDropdown'

export interface FileInfo {
  id: string
  original_filename: string
  media_type: string
  extension: string
  size_bytes: number
  created_at?: string
  compatible_formats?: Record<string, string[]>
}

export interface ConversionInfo {
  id: string
  original_filename: string
  media_type: string
  extension: string
  size_bytes: number
  created_at: string
  quality?: string
}

export type JobStatus = 'queued' | 'running' | 'completed' | 'failed' | 'cancelled'

export interface FileTableRow {
  id: string
  file: FileInfo
  conversion?: ConversionInfo
  selectedFormat?: string
  selectedQuality?: string
  status?: 'pending' | 'failed'
  statusMessage?: string
  jobStatus?: JobStatus
  selectable?: boolean
  onFormatChange?: (format: string) => void
  onQualityChange?: (quality: string) => void
  onDelete?: () => void
  onDownload?: () => void
  onPreview?: () => void
  onCancel?: () => void
  onRetry?: () => void
  isDeleting?: boolean
  isDownloading?: boolean
  isCancelling?: boolean
  isRetrying?: boolean
}

interface FileTableProps {
  rows: FileTableRow[]
  isPending?: boolean
  showCheckbox?: boolean
  showDate?: boolean
  showStatus?: boolean
  selectedIds?: Set<string>
  onToggleSelect?: (id: string) => void
  onToggleSelectAll?: () => void
  converting?: boolean
  className?: string
  bulkFormats?: string[]
  bulkQualities?: string[]
  onBulkFormatChange?: (format: string) => void
  onBulkQualityChange?: (quality: string) => void
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
  showStatus = false,
  selectedIds,
  onToggleSelect,
  onToggleSelectAll,
  converting = false,
  className,
  bulkFormats,
  bulkQualities,
  onBulkFormatChange,
  onBulkQualityChange,
}: FileTableProps) {
  const [sortColumn, setSortColumn] = useState<SortColumn>('date')
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc')
  const { t } = useTranslation()

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

  const renderSortIcon = (column: SortColumn) => {
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

  const hasActions = rows.some(r => r.onDownload || r.onDelete || r.onPreview || r.onCancel || r.onRetry)
  const hasQuality = isPending
    ? rows.some(r => r.selectedFormat && r.file.compatible_formats?.[r.selectedFormat]?.length)
    : rows.some(r => r.conversion?.quality)

  if (rows.length === 0) return null

  return (
    <div className={`overflow-x-auto rounded-lg border border-surface-dark ${className || ''}`}>
      <table className="w-full text-sm text-left">
        <thead className="text-xs uppercase bg-surface-dark text-text-muted">
          <tr>
            {showCheckbox && (
              <th className="px-2 sm:px-3 py-3 w-8 sm:w-10">
                {onToggleSelectAll && (
                  <button
                    onClick={onToggleSelectAll}
                    className="text-primary hover:text-primary-light text-lg transition duration-200"
                    aria-label={allSelected ? t('table.deselectAll') : t('table.selectAll')}
                  >
                    {allSelected ? <FaCheckSquare /> : <FaSquare />}
                  </button>
                )}
              </th>
            )}
            <th 
              className="px-3 sm:px-4 py-3"
              aria-sort={sortColumn === 'filename' ? (sortDirection === 'asc' ? 'ascending' : 'descending') : 'none'}
            >
              <button
                onClick={() => handleSort('filename')}
                className="flex items-center gap-1 hover:text-text transition uppercase"
              >
                {t('table.filename')} {renderSortIcon('filename')}
              </button>
            </th>
            <th
              className="px-2 sm:px-4 py-3"
              aria-sort={sortColumn=== 'type' ? (sortDirection === 'asc' ? 'ascending' : 'descending') : 'none'}
            >
              <div className="flex items-center gap-2">
                <button
                  onClick={() => handleSort('type')}
                  className="flex items-center gap-1 hover:text-text transition uppercase"
                >
                  {t('table.format')} {renderSortIcon('type')}
                </button>
                {bulkFormats && bulkFormats.length > 0 && onBulkFormatChange && (
                  <FormatDropdown
                    value=""
                    formats={bulkFormats}
                    onChange={onBulkFormatChange}
                    placeholder={t('table.all')}
                    title={t('table.setFormatAll')}
                    disabled={converting}
                  />
                )}
              </div>
            </th>
            {hasQuality && (
              <th className="hidden xl:table-cell px-4 py-3">
                <div className="flex items-center gap-2">
                  <span className="uppercase">{t('table.quality')}</span>
                  {bulkQualities && bulkQualities.length > 0 && onBulkQualityChange && (
                    <FormatDropdown
                      value=""
                      formats={bulkQualities}
                      onChange={onBulkQualityChange}
                    placeholder={t('table.all')}
                    title={t('table.setQualityAll')}
                      disabled={converting}
                      presorted
                    />
                  )}
                </div>
              </th>
            )}
            <th
              className="hidden md:table-cell px-4 py-3"
              aria-sort={sortColumn=== 'size' ? (sortDirection === 'asc' ? 'ascending' : 'descending') : 'none'}
            >
              <button
                onClick={() => handleSort('size')}
                className="flex items-center gap-1 hover:text-text transition uppercase"
              >
                {t('table.size')} {renderSortIcon('size')}
              </button>
            </th>
            {showDate && (
              <th
                className="hidden lg:table-cell px-4 py-3"
                aria-sort={sortColumn=== 'date' ? (sortDirection === 'asc' ? 'ascending' : 'descending') : 'none'}
              >
                <button
                  onClick={() => handleSort('date')}
                  className="flex items-center gap-1 hover:text-text transition uppercase"
                >
                  {t('table.date')} {renderSortIcon('date')}
                </button>
              </th>
            )}
            {showStatus && (
              <th className="px-2 sm:px-4 py-3 text-center uppercase">{t('table.status')}</th>
            )}
            {hasActions && (
              <th className="px-2 sm:px-4 py-3 text-right">{t('table.actions')}</th>
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
                <td className="px-2 sm:px-3 py-3">
                  {onToggleSelect && row.selectable !== false && (
                    <button
                      onClick={() => onToggleSelect(row.id)}
                      className="text-primary hover:text-primary-light text-lg transition duration-200"
                      aria-label={selectedIds?.has(row.id) ? t('table.deselect') : t('table.select')}
                    >
                      {selectedIds?.has(row.id) ? <FaCheckSquare /> : <FaSquare />}
                    </button>
                  )}
                </td>
              )}
              <td className="px-3 sm:px-4 py-3">
                <div className="max-w-[10rem] sm:max-w-[14rem] md:max-w-[16rem]">
                  <span
                    className="font-medium text-text truncate block"
                    title={getDisplayFilename(row)}
                  >
                    {getDisplayFilename(row)}
                  </span>
                  {(() => {
                    const size = formatFileSize(row.conversion?.size_bytes ?? row.file.size_bytes)
                    const dateStr = (row.file.created_at || row.conversion?.created_at)
                      ? new Date(row.conversion?.created_at || row.file.created_at!).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })
                      : null
                    const quality = !isPending && row.conversion?.quality ? row.conversion.quality : null
                    return (
                      <div className="lg:hidden text-xs text-text-muted mt-0.5 flex flex-wrap gap-x-2">
                        <span className="md:hidden">{size}</span>
                        {quality && <span className="xl:hidden uppercase">{quality}</span>}
                        {dateStr && <span>{dateStr}</span>}
                      </div>
                    )
                  })()}
                  {row.status === 'failed' && (
                    <div className="mt-1">
                      <span className="inline-block text-[0.65rem] font-semibold uppercase tracking-wide bg-primary/20 px-2 py-0.5 rounded text-primary-light">
                        {t('table.failed')}
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
              <td className="px-2 sm:px-4 py-3 whitespace-nowrap">
                  {(row.conversion || row.selectedFormat) ? (
                    isPending && row.file.compatible_formats && Object.keys(row.file.compatible_formats).length > 0 && row.onFormatChange ? (
                      <FormatDropdown
                        value={row.selectedFormat || ''}
                        formats={Object.keys(row.file.compatible_formats!)}
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
              {hasQuality && (
                <td className="hidden xl:table-cell px-4 py-3 whitespace-nowrap">
                  {(() => {
                    if (isPending) {
                      const qualities = row.selectedFormat ? row.file.compatible_formats?.[row.selectedFormat] : undefined
                      const qualityOrder: Record<string, number> = { low: 0, medium: 1, high: 2 }
                      const sortedQualities = qualities ? [...qualities].sort((a, b) => (qualityOrder[a] ?? 99) - (qualityOrder[b] ?? 99)) : undefined
                      return sortedQualities && sortedQualities.length > 0 && row.onQualityChange ? (
                        <FormatDropdown
                          value={row.selectedQuality || ''}
                          formats={sortedQualities}
                          onChange={(quality) => row.onQualityChange!(quality)}
                          placeholder={t('table.qualityPlaceholder')}
                          title={`Quality: ${row.selectedQuality || 'default'}`}
                          presorted
                        />
                      ) : (
                        <span className="text-xs text-text-muted">—</span>
                      )
                    }
                    return row.conversion?.quality ? (
                      <span className="text-xs font-mono uppercase bg-primary/20 px-2 py-0.5 rounded text-primary">
                        {row.conversion.quality}
                      </span>
                    ) : (
                      <span className="text-xs text-text-muted">—</span>
                    )
                  })()}
                </td>
              )}
              <td
                className="hidden md:table-cell px-4 py-3 text-text-muted whitespace-nowrap"
                title={row.conversion ? `${formatFileSize(row.file.size_bytes)} → ${formatFileSize(row.conversion.size_bytes)}` : undefined}
              >
                {formatFileSize(row.conversion?.size_bytes ?? row.file.size_bytes)}
              </td>
              {showDate && (
                <td className="hidden lg:table-cell px-4 py-3 text-text-muted whitespace-nowrap">
                  {(row.file.created_at || row.conversion?.created_at) &&
                    new Date(row.conversion?.created_at || row.file.created_at!).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })
                  }
                </td>
              )}
              {showStatus && (
                <td className="px-2 sm:px-4 py-3 whitespace-nowrap text-center">
                  {row.jobStatus ? (() => {
                    const label = t(`table.statusLabel.${row.jobStatus}`)
                    const tooltip = row.statusMessage ? `${label} — ${row.statusMessage}` : label
                    const icon =
                      row.jobStatus === 'completed' ? <FaCheckCircle className="text-success text-base" /> :
                      row.jobStatus === 'running' ? <FaSpinner className="text-primary-light text-base animate-spin" /> :
                      row.jobStatus === 'queued' ? <FaHourglassHalf className="text-text-muted text-base" /> :
                      row.jobStatus === 'cancelled' ? <FaBan className="text-text-muted text-base" /> :
                      <FaTimesCircle className="text-primary-light text-base" />
                    return (
                      <span className="inline-flex w-full justify-center" title={tooltip} aria-label={tooltip}>
                        {icon}
                      </span>
                    )
                  })() : (
                    <span className="text-xs text-text-muted">—</span>
                  )}
                </td>
              )}
              {hasActions && (
                <td className="px-2 sm:px-4 py-3">
                  <div className="flex gap-0.5 sm:gap-1.5 justify-end">
                    {row.onPreview && (
                      <button
                        onClick={row.onPreview}
                        className="p-1.5 sm:p-2 rounded-lg text-text-muted hover:text-text hover:bg-surface-dark transition duration-200"
                        title={t('table.preview')}
                      >
                        <FaEye className="text-sm" />
                      </button>
                    )}
                    {row.onDownload && row.conversion && (
                      <button
                        onClick={row.onDownload}
                        disabled={row.isDownloading}
                        className="p-1.5 sm:p-2 rounded-lg text-success hover:bg-success/20 transition duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
                        title={t('table.download')}
                      >
                        <FaDownload className="text-sm" />
                      </button>
                    )}
                    {row.onRetry && (
                      <button
                        onClick={row.onRetry}
                        disabled={row.isRetrying}
                        className="p-1.5 sm:p-2 rounded-lg text-primary-light hover:bg-primary/20 transition duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
                        title={t('table.retry')}
                      >
                        <FaRedo className="text-sm" />
                      </button>
                    )}
                    {row.onCancel && (
                      <button
                        onClick={row.onCancel}
                        disabled={row.isCancelling}
                        className="p-1.5 sm:p-2 rounded-lg text-text-muted hover:text-text hover:bg-surface-dark transition duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
                        title={t('table.cancel')}
                      >
                        <FaTimes className="text-sm" />
                      </button>
                    )}
                    {row.onDelete && (
                      <button
                        onClick={row.onDelete}
                        disabled={row.isDeleting}
                        className="p-1.5 sm:p-2 rounded-lg text-primary-light hover:bg-primary/20 transition duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
                        title={t('table.delete')}
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
