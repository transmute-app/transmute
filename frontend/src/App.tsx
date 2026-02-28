import { BrowserRouter as Router, Routes, Route, useLocation } from 'react-router-dom'
import { useEffect } from 'react'
import { ThemeProvider } from './ThemeContext'
import Header from './components/Header'
import Footer from './components/Footer'
import Converter from './pages/Converter'
import History from './pages/History'
import Files from './pages/Files'
import Settings from './pages/Settings'

function RouteTitle() {
  const location = useLocation()

  useEffect(() => {
    const titles: Record<string, string> = {
      '/': 'Transmute - Converter',
      '/files': 'Transmute - Files',
      '/history': 'Transmute - History',
      '/settings': 'Transmute - Settings',
    }

    document.title = titles[location.pathname] || 'Transmute'
  }, [location])

  return null
}

function App() {
  return (
    <ThemeProvider>
      <Router>
        <RouteTitle />
        <div className="flex flex-col h-screen overflow-hidden">
          <Header />
          <main className="flex-grow overflow-auto">
            <Routes>
              <Route path="/" element={<Converter />} />
              <Route path="/files" element={<Files />} />
              <Route path="/history" element={<History />} />
              <Route path="/settings" element={<Settings />} />
            </Routes>
          </main>
          <Footer />
        </div>
      </Router>
    </ThemeProvider>
  )
}

export default App

