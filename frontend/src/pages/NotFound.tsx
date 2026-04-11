import { Link } from 'react-router-dom'
import { FaHouse } from 'react-icons/fa6'
import { useTranslation } from 'react-i18next'

export default function NotFound() {
  const { t } = useTranslation()

  return (
    <div className="flex flex-col items-center justify-center h-full space-y-6 text-center">
      <h1 className="text-8xl font-bold text-primary">{t('notFound.title')}</h1>
      <h2 className="text-3xl font-semibold text-text">{t('notFound.heading')}</h2>
      <p className="text-text-muted max-w-md">
        {t('notFound.message')}
      </p>
      <Link
        to="/"
        className="flex items-center px-6 py-3 bg-primary text-surface font-medium rounded-lg hover:bg-primary-hover transition-colors"
      >
        <FaHouse className="mr-2" />
        {t('notFound.backHome')}
      </Link>
    </div>
  )
}
