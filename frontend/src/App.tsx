import { lazy, Suspense, type ReactNode, useEffect } from 'react'
import { BrowserRouter as Router, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { AuthProvider, useAuth } from './AuthContext'
import { ThemeProvider, useTheme } from './ThemeContext'
import Header from './components/Header'
import Footer from './components/Footer'

const Account = lazy(() => import('./pages/Account'))
const Auth = lazy(() => import('./pages/Auth'))
const Converter = lazy(() => import('./pages/Converter'))
const History = lazy(() => import('./pages/History'))
const Files = lazy(() => import('./pages/Files'))
const Settings = lazy(() => import('./pages/Settings'))
const Users = lazy(() => import('./pages/Users'))
const Stats = lazy(() => import('./pages/Stats'))
const NotFound = lazy(() => import('./pages/NotFound'))

function RouteTitle() {
  const location = useLocation()
  const { t } = useTranslation()

  useEffect(() => {
    const titles: Record<string, string> = {
      '/auth': t('titles.signIn'),
      '/': t('titles.converter'),
      '/files': t('titles.files'),
      '/history': t('titles.history'),
      '/settings': t('titles.settings'),
      '/account': t('titles.account'),
      '/admin/users': t('titles.userManagement'),
      '/admin/stats': t('titles.stats'),
    }

    document.title = titles[location.pathname] || t('app.name')
  }, [location, t])

  return null
}

function LoadingScreen() {
  const { t } = useTranslation()

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-surface-dark to-surface-light px-6 text-text">
      <div className="rounded-3xl border border-white/10 bg-surface-light/70 px-8 py-6 shadow-xl backdrop-blur">
        <p className="text-sm uppercase tracking-[0.2em] text-text-muted">{t('loading.session')}</p>
        <p className="mt-3 text-xl font-semibold text-primary">{t('loading.restoring')}</p>
      </div>
    </div>
  )
}

function RequireAuth({ children }: { children: ReactNode }) {
  const { status } = useAuth()
  const location = useLocation()

  if (status === 'loading') {
    return <LoadingScreen />
  }

  if (status !== 'authenticated') {
    return <Navigate to="/auth" replace state={{ from: location.pathname }} />
  }

  return <>{children}</>
}

function RequireAdmin({ children }: { children: ReactNode }) {
  const { status, isAdmin } = useAuth()

  if (status === 'loading') {
    return <LoadingScreen />
  }

  if (!isAdmin) {
    return <Navigate to="/account" replace />
  }

  return <>{children}</>
}

function RejectGuest({ children }: { children: ReactNode }) {
  const { user } = useAuth()

  if (user?.is_guest) {
    return <Navigate to="/" replace />
  }

  return <>{children}</>
}

function AppRoutes() {
  const { keepOriginals } = useTheme()
  const { status } = useAuth()

  return (
    <Suspense fallback={<LoadingScreen />}>
      <Routes>
        <Route path="/auth" element={status === 'authenticated' ? <Navigate to="/" replace /> : <Auth />} />
        <Route path="/" element={<RequireAuth><Converter /></RequireAuth>} />
        <Route
          path="/files"
          element={
            <RequireAuth>
              {keepOriginals ? <Files /> : <Navigate to="/" replace />}
            </RequireAuth>
          }
        />
        <Route path="/queue" element={<Navigate to="/history" replace />} />
        <Route path="/history" element={<RequireAuth><History /></RequireAuth>} />
        <Route path="/settings" element={<RequireAuth><RejectGuest><Settings /></RejectGuest></RequireAuth>} />
        <Route path="/account" element={<RequireAuth><RejectGuest><Account /></RejectGuest></RequireAuth>} />
        <Route path="/admin/users" element={<RequireAuth><RequireAdmin><Users /></RequireAdmin></RequireAuth>} />
        <Route path="/admin/stats" element={<RequireAuth><RequireAdmin><Stats /></RequireAdmin></RequireAuth>} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </Suspense>
  )
}

function AppShell() {
  const location = useLocation()
  const { status } = useAuth()
  const showChrome = status === 'authenticated' && location.pathname !== '/auth'

  return (
    <div className="flex h-screen flex-col overflow-hidden">
      {showChrome && <Header />}
      <main className="flex-grow overflow-auto">
        <AppRoutes />
      </main>
      {showChrome && <Footer />}
    </div>
  )
}

function App() {
  return (
    <AuthProvider>
      <ThemeProvider>
        <Router>
          <RouteTitle />
          <AppShell />
        </Router>
      </ThemeProvider>
    </AuthProvider>
  )
}

export default App

