import { useEffect, useState } from 'react'
import { FaGithub, FaExternalLinkAlt } from 'react-icons/fa'

function Footer() {
  const [appInfo, setAppInfo] = useState<{ name: string; version: string } | null>(null)

  useEffect(() => {
    fetch('/api/health/info')
      .then(res => res.json())
      .then(data => setAppInfo(data))
      .catch(() => {}) // Silently fail if API is unavailable
  }, [])

  return (
    <footer className="bg-surface-dark border-t border-surface-light mt-auto">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex items-center justify-center gap-2 text-text-muted text-sm">
            <a href="https://github.com/transmute-app/transmute" target="_blank" rel="noopener noreferrer" className="hover:text-text transition-colors">
              <FaGithub size={16} />
            </a>
            <span className="text-text-muted/30">|</span>
            <span>
              {appInfo?.name || 'Transmute'}
              {appInfo?.version && (
                <span className="ml-2 text-text-muted/60">v{appInfo.version}</span>
              )}
            </span>
            <span className="text-text-muted/30">|</span>
            <a href="https://transmute.sh" target="_blank" rel="noopener noreferrer" className="hover:text-text transition-colors">
              <FaExternalLinkAlt size={13} />
            </a>
          </div>
      </div>
    </footer>
  )
}

export default Footer
