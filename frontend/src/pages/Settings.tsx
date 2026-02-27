import { useState, useRef, useEffect } from 'react'

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

function Settings() {
  const [theme, setTheme] = useState('rubedo')
  const [themeOpen, setThemeOpen] = useState(false)
  const themeRef = useRef<HTMLDivElement>(null)
  const [autoDownload, setAutoDownload] = useState(false)

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (themeRef.current && !themeRef.current.contains(e.target as Node)) {
        setThemeOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])
  const [saveOriginals, setSaveOriginals] = useState(true)
  const [saved, setSaved] = useState(false)

  const handleSave = () => {
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  const handleClearConversions = () => {
    // No-op for now
  }

  const handleClearUploads = () => {
    // No-op for now
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-surface-dark to-surface-light p-8">
      <div className="max-w-4xl mx-auto">
        <div className="flex justify-between items-center mb-6 min-h-[4rem]">
          <h1 className="text-3xl font-bold text-primary">Settings</h1>
        </div>

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
                          onClick={() => { setTheme(t.value); setThemeOpen(false) }}
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
                  className="bg-primary/20 hover:bg-primary/40 text-primary-light font-semibold py-2 px-5 rounded-lg transition duration-200 shadow-md hover:shadow-lg text-sm"
                >
                  Clear History
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
                  className="bg-primary/20 hover:bg-primary/40 text-primary-light font-semibold py-2 px-5 rounded-lg transition duration-200 shadow-md hover:shadow-lg text-sm"
                >
                  Clear Files
                </button>
              </div>
            </div>
          </section>

        </div>

        {/* Save */}
        <div className="mt-8 flex justify-end">
          <button
            onClick={handleSave}
            className="bg-success hover:bg-success-dark text-white font-semibold py-2 px-8 rounded-lg transition duration-200 shadow-md hover:shadow-lg"
          >
            {saved ? 'Saved!' : 'Save Changes'}
          </button>
        </div>

      </div>
    </div>
  )
}

export default Settings
