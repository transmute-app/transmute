import { useState, useRef, useEffect } from 'react'
import { useTheme, type ThemeName } from '../ThemeContext'

interface Theme {
  value: string
  label: string
  colors: string[]
}

const THEMES: Theme[] = [
  { value: 'rubedo',     label: 'Rubedo',     colors: ['#ef4444', '#171e2f'] },  // Red / Dark Blue
  { value: 'citrinitas', label: 'Citrinitas', colors: ['#ffd700', '#3c00a4'] },  // Gold / Violet
  { value: 'viriditas',  label: 'Viriditas',  colors: ['#16a34a', '#000000'] },  // Green / Black
  { value: 'nigredo',    label: 'Nigredo',    colors: ['#3c00a4', '#000000'] },  // Purple / Black
  { value: 'albedo',     label: 'Albedo',     colors: ['#f8fafc', '#cbd5e1'] },  // Light / Silver
]

function ThemeSwatch({ colors }: { colors: string[] }) {
  if (colors.length >= 2) {
    return (
      <span className="relative w-4 h-4 rounded-full flex-shrink-0 overflow-hidden border border-white/20 block">
        <span className="absolute inset-y-0 left-0 w-1/2" style={{ background: colors[0] }} />
        <span className="absolute inset-y-0 right-0 w-1/2" style={{ background: colors[1] }} />
      </span>
    )
  }
  return (
    <span
      className="block w-4 h-4 rounded-full border border-white/20 flex-shrink-0"
      style={{ background: colors[0] ?? '#888' }}
    />
  )
}

interface AppSettings {
  theme: string
  auto_download: boolean
  keep_originals: boolean
  cleanup_ttl_minutes: number
}

function Settings() {
  const { theme, setTheme } = useTheme()
  const [autoDownload, setAutoDownload] = useState(false)
  const [saveOriginals, setSaveOriginals] = useState(true)
  const [cleanupTtl, setCleanupTtl] = useState(60)
  const [themeOpen, setThemeOpen] = useState(false)
  const [loaded, setLoaded] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [clearConversionsStatus, setClearConversionsStatus] = useState<'idle' | 'clearing' | 'success' | 'error'>('idle')
  const [clearUploadsStatus, setClearUploadsStatus] = useState<'idle' | 'clearing' | 'success' | 'error'>('idle')
  const themeRef = useRef<HTMLDivElement>(null)

  // Load settings once on mount
  useEffect(() => {
    fetch('/api/settings')
      .then(r => r.ok ? r.json() : Promise.reject('Failed to load settings'))
      .then((data: AppSettings) => {
        setTheme(data.theme as ThemeName)
        setAutoDownload(data.auto_download)
        setSaveOriginals(data.keep_originals)
        setCleanupTtl(data.cleanup_ttl_minutes)
        setLoaded(true)
      })
      .catch(() => setLoaded(true)) // fall back to defaults silently
  }, [])

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (themeRef.current && !themeRef.current.contains(e.target as Node)) {
        setThemeOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const handleSave = async () => {
    setSaving(true)
    setError(null)
    try {
      const response = await fetch('/api/settings', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ theme, auto_download: autoDownload, keep_originals: saveOriginals, cleanup_ttl_minutes: cleanupTtl }),
      })
      if (!response.ok) throw new Error('Failed to save settings')
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save settings')
    } finally {
      setSaving(false)
    }
  }

  const handleClearConversions = () => {
    setClearConversionsStatus('clearing')
    fetch('/api/conversions/all', { method: 'DELETE' })
      .then(r => {
        if (!r.ok) throw new Error()
        setClearConversionsStatus('success')
        setTimeout(() => setClearConversionsStatus('idle'), 2000)
      })
      .catch(() => {
        setClearConversionsStatus('error')
        setTimeout(() => setClearConversionsStatus('idle'), 2000)
      })
  }

  const handleClearUploads = () => {
    setClearUploadsStatus('clearing')
    fetch('/api/files/all', { method: 'DELETE' })
      .then(r => {
        if (!r.ok) throw new Error()
        setClearUploadsStatus('success')
        setTimeout(() => setClearUploadsStatus('idle'), 2000)
      })
      .catch(() => {
        setClearUploadsStatus('error')
        setTimeout(() => setClearUploadsStatus('idle'), 2000)
      })
  }

  if (!loaded) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-surface-dark to-surface-light p-8 flex items-start justify-start">
        <div className="max-w-4xl mx-auto w-full pt-8">
          <p className="text-text-muted text-sm">Loading settings...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-surface-dark to-surface-light p-8">
      <div className="max-w-4xl mx-auto">
        <div className="flex justify-between items-center mb-6 min-h-[4rem]">
          <h1 className="text-3xl font-bold text-primary">Settings</h1>
        </div>

        {error && (
          <div className="p-3 bg-primary/20 border border-primary rounded-lg text-primary-light text-sm mb-4">
            {error}
          </div>
        )}

        <div className="space-y-6">

          {/* Appearance */}
          <section className="bg-surface-light rounded-xl p-6">
            <h2 className="text-lg font-semibold text-text mb-4">Appearance</h2>
            <div className="flex flex-col gap-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-text font-medium">Theme</p>
                  <p className="text-text-muted text-sm">Choose the application color theme</p>
                </div>
                <div className="relative" ref={themeRef}>
                  <button
                    onClick={() => setThemeOpen(o => !o)}
                    className="flex items-center gap-2 bg-surface-dark text-text border border-surface-light rounded-lg py-2 px-4 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 transition duration-200 min-w-[200px]"
                  >
                    <ThemeSwatch colors={THEMES.find(t => t.value === theme)?.colors ?? []} />
                    <span className="flex-1 text-left">{THEMES.find(t => t.value === theme)?.label}</span>
                    <svg className={`w-4 h-4 transition-transform duration-200 ${themeOpen ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                    </svg>
                  </button>
                  {themeOpen && (
                    <div className="absolute right-0 mt-1 w-full bg-surface-dark border border-surface-light rounded-lg shadow-xl z-10 overflow-hidden">
                      {THEMES.map(t => (
                        <button
                          key={t.value}
                          onClick={() => { setTheme(t.value as ThemeName); setThemeOpen(false) }}
                          className={`flex items-center gap-3 w-full px-4 py-2.5 text-sm text-left transition duration-150 ${
                            theme === t.value
                              ? 'bg-primary/20 text-primary-light'
                              : 'text-text hover:bg-surface-light'
                          }`}
                        >
                          <ThemeSwatch colors={t.colors} />
                          {t.label}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          </section>

          {/* Conversion */}
          <section className="bg-surface-light rounded-xl p-6">
            <h2 className="text-lg font-semibold text-text mb-4">Conversion</h2>
            <div className="flex flex-col gap-5">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-text font-medium">Auto-download on Completion</p>
                  <p className="text-text-muted text-sm">Automatically download files when conversion finishes</p>
                </div>
                <button
                  onClick={() => setAutoDownload(v => !v)}
                  className={`relative w-12 h-6 rounded-full transition-colors duration-200 focus:outline-none ${autoDownload ? 'bg-success' : 'bg-surface-dark border border-surface-light'}`}
                >
                  <span
                    className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform duration-200 ${autoDownload ? 'translate-x-6' : 'translate-x-0'}`}
                  />
                </button>
              </div>

              <div className="flex items-center justify-between">
                <div>
                  <p className="text-text font-medium">Keep Original Files</p>
                  <p className="text-text-muted text-sm">Retain uploaded source files after conversion</p>
                  <p className="text-yellow-400/80 text-xs mt-1 flex items-center gap-1">
                    <svg className="w-3 h-3 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495zM10 5a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 5zm0 9a1 1 0 100-2 1 1 0 000 2z" clipRule="evenodd" />
                    </svg>
                    Not yet implemented — this setting has no effect
                  </p>
                </div>
                <button
                  onClick={() => setSaveOriginals(v => !v)}
                  className={`relative w-12 h-6 rounded-full transition-colors duration-200 focus:outline-none ${saveOriginals ? 'bg-success' : 'bg-surface-dark border border-surface-light'}`}
                >
                  <span
                    className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform duration-200 ${saveOriginals ? 'translate-x-6' : 'translate-x-0'}`}
                  />
                </button>
              </div>

              <div className="flex items-center justify-between">
                <div>
                  <p className="text-text font-medium">Cleanup TTL</p>
                  <p className="text-text-muted text-sm">Minutes before uploads & conversions are cleaned up</p>
                </div>
                <div className="flex items-center gap-2">
                  <div className="flex items-center bg-surface-dark border border-surface-light rounded-lg overflow-hidden">
                    <button
                      onClick={() => setCleanupTtl(v => Math.max(1, v - 1))}
                      className="px-3 py-2 text-text-muted hover:text-text hover:bg-surface-light transition-colors duration-150 text-base leading-none select-none"
                      aria-label="Decrease"
                    >−</button>
                    <input
                      type="number"
                      min={1}
                      max={10080}
                      value={cleanupTtl}
                      onChange={e => setCleanupTtl(Math.max(1, parseInt(e.target.value) || 1))}
                      className="w-16 bg-transparent text-text text-sm text-center py-2 focus:outline-none [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
                    />
                    <button
                      onClick={() => setCleanupTtl(v => Math.min(10080, v + 1))}
                      className="px-3 py-2 text-text-muted hover:text-text hover:bg-surface-light transition-colors duration-150 text-base leading-none select-none"
                      aria-label="Increase"
                    >+</button>
                  </div>
                  <span className="text-text-muted text-sm">min</span>
                </div>
              </div>
            </div>
          </section>

          {/* Data Management */}
          <section className="bg-surface-light rounded-xl p-6">
            <h2 className="text-lg font-semibold text-text mb-4">Data Management</h2>
            <div className="flex flex-col gap-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-text font-medium">Clear Conversions</p>
                  <p className="text-text-muted text-sm">Delete all converted files and conversion history records</p>
                </div>
                <button
                  onClick={handleClearConversions}
                  disabled={clearConversionsStatus === 'clearing'}
                  className="bg-primary/20 hover:bg-primary/40 text-primary-light font-semibold py-2 px-5 rounded-lg transition duration-200 shadow-md hover:shadow-lg text-sm disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {clearConversionsStatus === 'clearing' ? 'Clearing...' : clearConversionsStatus === 'success' ? 'Cleared!' : clearConversionsStatus === 'error' ? 'Failed' : 'Clear History'}
                </button>
              </div>

              <div className="border-t border-surface-dark" />

              <div className="flex items-center justify-between">
                <div>
                  <p className="text-text font-medium">Clear Uploads</p>
                  <p className="text-text-muted text-sm">Delete all uploaded files</p>
                </div>
                <button
                  onClick={handleClearUploads}
                  disabled={clearUploadsStatus === 'clearing'}
                  className="bg-primary/20 hover:bg-primary/40 text-primary-light font-semibold py-2 px-5 rounded-lg transition duration-200 shadow-md hover:shadow-lg text-sm disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {clearUploadsStatus === 'clearing' ? 'Clearing...' : clearUploadsStatus === 'success' ? 'Cleared!' : clearUploadsStatus === 'error' ? 'Failed' : 'Clear Files'}
                </button>
              </div>
            </div>
          </section>

        </div>

        {/* Save */}
        <div className="mt-8 flex justify-end">
          <button
            onClick={handleSave}
            disabled={saving}
            className="bg-success hover:bg-success-dark text-white font-semibold py-2 px-8 rounded-lg transition duration-200 shadow-md hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {saving ? 'Saving...' : saved ? 'Saved!' : 'Save Changes'}
          </button>
        </div>

      </div>
    </div>
  )
}

export default Settings
