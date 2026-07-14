import { useTranslation } from 'react-i18next'
import type { PaginationMetadata } from '../utils/pagination'

interface PaginationProps {
  pagination: PaginationMetadata
  onPageChange: (page: number) => void
  disabled?: boolean
}

function Pagination({ pagination, onPageChange, disabled = false }: PaginationProps) {
  const { t } = useTranslation()

  if (pagination.total_pages <= 1) return null

  return (
    <nav className="mt-6 flex items-center justify-center gap-4" aria-label={t('pagination.label')}>
      <button
        type="button"
        onClick={() => onPageChange(pagination.current_page - 1)}
        disabled={disabled || !pagination.has_prev}
        className="rounded-lg border border-primary/40 px-4 py-2 text-sm font-semibold text-primary-light transition hover:bg-primary/20 disabled:cursor-not-allowed disabled:opacity-40"
      >
        {t('pagination.previous')}
      </button>
      <span className="text-sm text-text-muted">
        {t('pagination.pageOf', {
          current: pagination.current_page,
          total: pagination.total_pages,
        })}
      </span>
      <button
        type="button"
        onClick={() => onPageChange(pagination.current_page + 1)}
        disabled={disabled || !pagination.has_next}
        className="rounded-lg border border-primary/40 px-4 py-2 text-sm font-semibold text-primary-light transition hover:bg-primary/20 disabled:cursor-not-allowed disabled:opacity-40"
      >
        {t('pagination.next')}
      </button>
    </nav>
  )
}

export default Pagination
