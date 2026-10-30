import { FaChevronLeft, FaChevronRight } from 'react-icons/fa'
import { useTranslation } from 'react-i18next'

interface PaginationProps {
  /** Current page, starting at 1. */
  page: number
  totalPages: number
  onPageChange: (page: number) => void
  /** Disables both buttons, for example while a page is loading. */
  disabled?: boolean
}

const buttonClass =
  'flex items-center gap-2 bg-primary/20 hover:bg-primary/40 text-primary-light font-semibold py-2 px-4 rounded-lg transition duration-200 disabled:opacity-50 disabled:cursor-not-allowed'

/** Previous / next controls with a "Page X of Y" label. Renders nothing for a single page. */
function Pagination({ page, totalPages, onPageChange, disabled = false }: PaginationProps) {
  const { t } = useTranslation()

  if (totalPages <= 1) return null

  return (
    <nav aria-label={t('pagination.label')} className="flex items-center justify-center gap-4 mt-6">
      <button
        type="button"
        onClick={() => onPageChange(page - 1)}
        disabled={disabled || page <= 1}
        className={buttonClass}
      >
        <FaChevronLeft aria-hidden="true" />
        {t('pagination.previous')}
      </button>
      <span className="text-text-muted text-sm" aria-live="polite">
        {t('pagination.pageOf', { page, total: totalPages })}
      </span>
      <button
        type="button"
        onClick={() => onPageChange(page + 1)}
        disabled={disabled || page >= totalPages}
        className={buttonClass}
      >
        {t('pagination.next')}
        <FaChevronRight aria-hidden="true" />
      </button>
    </nav>
  )
}

export default Pagination
