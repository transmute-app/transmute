import { Link } from 'react-router-dom'
import { FaArrowRightArrowLeft, FaClockRotateLeft, FaBook, FaFile, FaGear } from 'react-icons/fa6'

function Header() {
  return (
    <header className="bg-surface-dark">
      <nav className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          <Link to="/" className="flex items-center">
            <svg
              viewBox="284 186 632 828"
              className="h-8 w-8 mr-2 text-primary"
              fill="currentColor"
              aria-label="Transmute Logo"
            >
              <path
                fillRule="evenodd"
                d="m730.08 186c9.9844 0 18 8.0625 18 18v72c0 9.9375-8.0156 18-18 18h-18v193.92l172.87 363.05c36.047 75.656-19.125 163.03-102.89 163.03h-367.92c-83.766 0-138.94-87.375-102.94-163.03l172.87-363.05v-193.92h-18c-9.9375 0-18-8.0625-18-18v-72c0-9.9375 8.0625-18 18-18zm-225.32 426-128.53 269.95c-13.266 27.844 7.0312 60.047 37.922 60.047h367.92c30.844 0 51.188-32.203 37.922-60.047l-128.53-269.95z"
              />
            </svg>
            <span className="text-2xl font-bold text-primary">Transmute</span>
          </Link>
          <div className="flex space-x-8">
            <Link
              to="/"
              className="text-text hover:text-primary px-3 py-2 rounded-md text-xl font-medium transition duration-200"
              title="Converter"
              aria-label="Converter"
            >
              <FaArrowRightArrowLeft />
            </Link>
            <Link
              to="/files"
              className="text-text hover:text-primary px-3 py-2 rounded-md text-xl font-medium transition duration-200"
              title="Files"
              aria-label="Files"
            >
              <FaFile />
            </Link>
            <Link
              to="/history"
              className="text-text hover:text-primary px-3 py-2 rounded-md text-xl font-medium transition duration-200"
              title="History"
              aria-label="History"
            >
              <FaClockRotateLeft />
            </Link>
            <a
              href="/api/docs"
              className="text-text hover:text-primary px-3 py-2 rounded-md text-xl font-medium transition duration-200"
              title="API Docs"
              aria-label="API Docs"
            >
              <FaBook />
            </a>
            <Link
              to="/settings"
              className="text-text hover:text-primary px-3 py-2 rounded-md text-xl font-medium transition duration-200"
              title="Settings"
              aria-label="Settings"
            >
              <FaGear />
            </Link>
          </div>
        </div>
      </nav>
    </header>
  )
}

export default Header
