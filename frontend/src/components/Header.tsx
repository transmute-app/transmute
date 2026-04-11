import { useEffect, useRef, useState } from 'react'
import { Link, NavLink } from 'react-router-dom'
import { FaArrowRightArrowLeft, FaChartBar, FaChevronDown, FaClockRotateLeft, FaFile, FaGear, FaRightFromBracket, FaUser, FaUsers } from 'react-icons/fa6'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../AuthContext'
import { useTheme } from '../ThemeContext'

function Header() {
  const { keepOriginals } = useTheme()
  const { user, isAdmin, logout } = useAuth()
  const { t } = useTranslation()
  const [menuOpen, setMenuOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handlePointerDown = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setMenuOpen(false)
      }
    }

    document.addEventListener('mousedown', handlePointerDown)
    return () => document.removeEventListener('mousedown', handlePointerDown)
  }, [])

  return (
    <header className="bg-surface-dark">
      <nav className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex h-16 items-center justify-between gap-4">
          <Link to="/" className="flex items-center">
            <svg
              viewBox="284 186 632 828"
              className="h-8 w-8 mr-2 text-primary"
              fill="currentColor"
              aria-label={t('nav.logo')}
            >
              <path
                fillRule="evenodd"
                d="m730.08 186c9.9844 0 18 8.0625 18 18v72c0 9.9375-8.0156 18-18 18h-18v193.92l172.87 363.05c36.047 75.656-19.125 163.03-102.89 163.03h-367.92c-83.766 0-138.94-87.375-102.94-163.03l172.87-363.05v-193.92h-18c-9.9375 0-18-8.0625-18-18v-72c0-9.9375 8.0625-18 18-18zm-225.32 426-128.53 269.95c-13.266 27.844 7.0312 60.047 37.922 60.047h367.92c30.844 0 51.188-32.203 37.922-60.047l-128.53-269.95z"
              />
            </svg>
            <span className="text-2xl font-bold text-primary">{t('app.name')}</span>
          </Link>
          <div className="flex items-center gap-3 md:gap-5">
            <div className="flex items-center gap-2 md:gap-3">
              <NavLink
                to="/"
                end
                className={({ isActive }) =>
                  `flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-semibold transition duration-200 ${isActive ? 'bg-primary/10 text-primary-light' : 'text-text hover:bg-surface-light hover:text-primary'}`
                }
                title={t('nav.converter')}
                aria-label={t('nav.converter')}
              >
                <FaArrowRightArrowLeft className="text-base" />
                <span className="hidden sm:inline">{t('nav.convert')}</span>
              </NavLink>
              {keepOriginals && (
                <NavLink
                  to="/files"
                  className={({ isActive }) =>
                    `flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-semibold transition duration-200 ${isActive ? 'bg-primary/10 text-primary-light' : 'text-text hover:bg-surface-light hover:text-primary'}`
                  }
                  title={t('nav.files')}
                  aria-label={t('nav.files')}
                >
                  <FaFile className="text-base" />
                  <span className="hidden sm:inline">{t('nav.files')}</span>
                </NavLink>
              )}
              <NavLink
                to="/history"
                className={({ isActive }) =>
                  `flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-semibold transition duration-200 ${isActive ? 'bg-primary/10 text-primary-light' : 'text-text hover:bg-surface-light hover:text-primary'}`
                }
                title={t('nav.history')}
                aria-label={t('nav.history')}
              >
                <FaClockRotateLeft className="text-base" />
                <span className="hidden sm:inline">{t('nav.history')}</span>
              </NavLink>
            </div>

            <div className="relative" ref={menuRef}>
              <button
                type="button"
                onClick={() => setMenuOpen(open => !open)}
                className="flex items-center gap-2 rounded-lg border border-primary/20 bg-primary/10 px-3 py-2 text-sm font-medium text-primary-light transition duration-200 hover:bg-primary/15"
                aria-haspopup="menu"
                aria-expanded={menuOpen}
                aria-label={t('menu.openAccountMenu')}
              >
                <FaUser className="text-sm" />
                <span className="hidden sm:inline max-w-28 truncate">{user?.username}</span>
                <FaChevronDown className={`text-xs transition-transform duration-200 ${menuOpen ? 'rotate-180' : ''}`} />
              </button>

              {menuOpen && (
                <div className="absolute right-0 z-20 mt-2 w-56 overflow-hidden rounded-xl border border-surface-light bg-surface-dark shadow-xl">
                  <div className="border-b border-surface-light px-4 py-3">
                    <p className="truncate text-sm font-semibold text-text">{user?.username}</p>
                    <p className="mt-1 text-xs uppercase tracking-[0.18em] text-text-muted">{user?.role}</p>
                  </div>
                  <div className="p-2">
                    {!user?.is_guest && (
                      <>
                        <NavLink
                          to="/account"
                          onClick={() => setMenuOpen(false)}
                          className={({ isActive }) =>
                            `flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition duration-200 ${isActive ? 'bg-primary/10 text-primary-light' : 'text-text hover:bg-surface-light hover:text-primary'}`
                          }
                        >
                          <FaUser className="text-sm" />
                          {t('menu.myAccount')}
                        </NavLink>
                        <NavLink
                          to="/settings"
                          onClick={() => setMenuOpen(false)}
                          className={({ isActive }) =>
                            `mt-1 flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition duration-200 ${isActive ? 'bg-primary/10 text-primary-light' : 'text-text hover:bg-surface-light hover:text-primary'}`
                          }
                        >
                          <FaGear className="text-sm" />
                          {t('menu.settings')}
                        </NavLink>
                        {isAdmin && (
                          <>
                            <NavLink
                              to="/admin/users"
                              onClick={() => setMenuOpen(false)}
                              className={({ isActive }) =>
                                `mt-1 flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition duration-200 ${isActive ? 'bg-primary/10 text-primary-light' : 'text-text hover:bg-surface-light hover:text-primary'}`
                              }
                            >
                              <FaUsers className="text-sm" />
                              {t('menu.userManagement')}
                            </NavLink>
                            <NavLink
                              to="/admin/stats"
                              onClick={() => setMenuOpen(false)}
                              className={({ isActive }) =>
                                `mt-1 flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition duration-200 ${isActive ? 'bg-primary/10 text-primary-light' : 'text-text hover:bg-surface-light hover:text-primary'}`
                              }
                            >
                              <FaChartBar className="text-sm" />
                              {t('menu.stats')}
                            </NavLink>
                          </>
                        )}
                      </>
                    )}
                    <button
                      type="button"
                      onClick={() => {
                        setMenuOpen(false)
                        logout()
                      }}
                      className="mt-1 flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-sm font-medium text-text transition duration-200 hover:bg-surface-light hover:text-primary"
                    >
                      <FaRightFromBracket className="text-sm" />
                      {t('menu.signOut')}
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </nav>
    </header>
  )
}

export default Header
