import { Link } from 'react-router-dom'
import { FaHouse } from 'react-icons/fa6'

export default function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center h-full space-y-6 text-center">
      <h1 className="text-8xl font-bold text-primary">404</h1>
      <h2 className="text-3xl font-semibold text-text">Page Not Found</h2>
      <p className="text-text-muted max-w-md">
        The page you are looking for doesn't exist or has been moved.
      </p>
      <Link
        to="/"
        className="flex items-center px-6 py-3 bg-primary text-surface font-medium rounded-lg hover:bg-primary-hover transition-colors"
      >
        <FaHouse className="mr-2" />
        Back to Home
      </Link>
    </div>
  )
}
