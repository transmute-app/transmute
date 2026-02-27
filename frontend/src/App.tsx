import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import Header from './components/Header'
import Footer from './components/Footer'
import Converter from './pages/Converter'
import History from './pages/History'
import Files from './pages/Files'
import Settings from './pages/Settings'

function App() {
  return (
    <Router>
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
  )
}

export default App
