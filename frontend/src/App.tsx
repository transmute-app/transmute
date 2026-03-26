import { type ReactNode, useEffect } from 'react'
import { BrowserRouter as Router, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { AuthProvider, useAuth } from './AuthContext'
import { ThemeProvider, useTheme } from './ThemeContext'
import Header from './components/Header'
import Footer from './components/Footer'
import Account from './pages/Account'
import Auth from './pages/Auth'
import Converter from './pages/Converter'
import History from './pages/History'
import Files from './pages/Files'
import Settings from './pages/Settings'
import Users from './pages/Users'
import Stats from './pages/Stats'
import NotFound from './pages/NotFound'

function RouteTitle() {
  const location = useLocation()

  useEffect(() => {
    const titles: Record<string, string> = {
      '/auth': 'Transmute - Sign In',
      '/': 'Transmute - Converter',
      '/files': 'Transmute - Files',
      '/history': 'Transmute - History',
      '/settings': 'Transmute - Settings',
      '/account': 'Transmute - My Account',
      '/admin/users': 'Transmute - User Management',
      '/admin/stats': 'Transmute - Stats',
    }

    document.title = titles[location.pathname] || 'Transmute'
  }, [location])

  return null
}

function LoadingScreen() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-surface-dark to-surface-light px-6 text-text">
      <div className="rounded-3xl border border-white/10 bg-surface-light/70 px-8 py-6 shadow-xl backdrop-blur">
        <p className="text-sm uppercase tracking-[0.2em] text-text-muted">Loading Session</p>
        <p className="mt-3 text-xl font-semibold text-primary">Restoring your workspace...</p>
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
      <Route path="/history" element={<RequireAuth><History /></RequireAuth>} />
      <Route path="/settings" element={<RequireAuth><RejectGuest><Settings /></RejectGuest></RequireAuth>} />
      <Route path="/account" element={<RequireAuth><RejectGuest><Account /></RejectGuest></RequireAuth>} />
      <Route path="/admin/users" element={<RequireAuth><RequireAdmin><Users /></RequireAdmin></RequireAuth>} />
      <Route path="/admin/stats" element={<RequireAuth><RequireAdmin><Stats /></RequireAdmin></RequireAuth>} />
      <Route path="*" element={<NotFound />} />
    </Routes>
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

