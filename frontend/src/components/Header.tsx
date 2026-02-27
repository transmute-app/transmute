import { Link } from 'react-router-dom'
import { FaArrowRightArrowLeft, FaClockRotateLeft, FaBook, FaFile } from 'react-icons/fa6'

function Header() {
  return (
    <header className="bg-surface-dark">
      <nav className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          <Link to="/" className="flex items-center">
            <img src="/icons/beaker-red.svg" alt="Transmute Logo" className="h-8 w-8 mr-2" />
            <span className="text-2xl font-bold text-primary">Transmute</span>
          </Link>
          <div className="flex space-x-8">
            <Link
              to="/"
              className="text-text hover:text-primary px-3 py-2 rounded-md text-xl font-medium transition duration-200"
              title="Converter"
            >
              <FaArrowRightArrowLeft />
            </Link>
            <Link
              to="/files"
              className="text-text hover:text-primary px-3 py-2 rounded-md text-xl font-medium transition duration-200"
              title="Files"
            >
              <FaFile />
            </Link>
            <Link
              to="/history"
              className="text-text hover:text-primary px-3 py-2 rounded-md text-xl font-medium transition duration-200"
              title="History"
            >
              <FaClockRotateLeft />
            </Link>
            <a
              href="/api/docs"
              className="text-text hover:text-primary px-3 py-2 rounded-md text-xl font-medium transition duration-200"
              title="API Docs"
            >
              <FaBook />
            </a>
          </div>
        </div>
      </nav>
    </header>
  )
}

export default Header
