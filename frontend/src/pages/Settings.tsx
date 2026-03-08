import { useState, useRef, useEffect, useCallback } from 'react'
import { useTheme, type ThemeName } from '../ThemeContext'
import { useAuth } from '../AuthContext'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { authFetch as fetch } from '../utils/api'

interface Theme {
  value: string
  label: string
  colors: string[]
}

interface DefaultFormatMapping {
  input_format: string
  output_format: string
}

interface ConverterInfo {
  name: string
  supported_input_formats: string[]
  supported_output_formats: string[]
}

const THEMES: Theme[] = [
  { value: 'rubedo',     label: 'Rubedo',     colors: ['#ef4444', '#171e2f'] },  // Red / Dark Blue
  { value: 'citrinitas', label: 'Citrinitas', colors: ['#fbbf24', '#140d2d'] },  // Gold / Deep Violet
  { value: 'viriditas',  label: 'Viriditas',  colors: ['#16a34a', '#000000'] },  // Green / Black
  { value: 'nigredo',    label: 'Nigredo',    colors: ['#3c00a4', '#000000'] },  // Purple / Black
  { value: 'albedo',     label: 'Albedo',     colors: ['#f8fafc', '#cbd5e1'] },  // Light / Silver
  { value: 'aurora',     label: 'Aurora',     colors: ['#ea580c', '#fffbf0'] },  // Orange / Warm Cream
  { value: 'caelum',     label: 'Caelum',     colors: ['#0284c7', '#f0f9ff'] },  // Sky Blue / Cool White
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
  cleanup_enabled: boolean
  cleanup_ttl_minutes: number
}

function Settings() {
  const { theme, setTheme, setKeepOriginals } = useTheme()
  const { isAdmin } = useAuth()
  const [autoDownload, setAutoDownload] = useState(false)
  const [saveOriginals, setSaveOriginals] = useState(true)
  const [cleanupEnabled, setCleanupEnabled] = useState(true)
  const [cleanupTtl, setCleanupTtl] = useState(60)
  const [themeOpen, setThemeOpen] = useState(false)
  const [loaded, setLoaded] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [clearConversionsStatus, setClearConversionsStatus] = useState<'idle' | 'clearing' | 'success' | 'error'>('idle')
  const [clearUploadsStatus, setClearUploadsStatus] = useState<'idle' | 'clearing' | 'success' | 'error'>('idle')
  const [confirmDialog, setConfirmDialog] = useState<{
    isOpen: boolean
    title: string
    message: string
    confirmLabel: string
    onConfirm: () => void
  } | null>(null)
  const themeRef = useRef<HTMLDivElement>(null)

  // Default format mappings
  const [defaultFormats, setDefaultFormats] = useState<DefaultFormatMapping[]>([])
  const [conversionMap, setConversionMap] = useState<Record<string, string[]>>({})
  const [newInputFormat, setNewInputFormat] = useState('')
  const [newOutputFormat, setNewOutputFormat] = useState('')

  // Build conversion map from converters API (input_format -> sorted output_formats)
  const loadConversionMap = useCallback(() => {
    fetch('/api/converters')
      .then(r => r.ok ? r.json() : Promise.reject())
      .then((data: { converters: ConverterInfo[] }) => {
        const map: Record<string, Set<string>> = {}
        for (const c of data.converters) {
          for (const inp of c.supported_input_formats) {
            for (const out of c.supported_output_formats) {
              if (inp !== out) {
                if (!map[inp]) map[inp] = new Set()
                map[inp].add(out)
              }
            }
          }
        }
        const sorted: Record<string, string[]> = {}
        for (const [k, v] of Object.entries(map)) {
          sorted[k] = [...v].sort()
        }
        setConversionMap(sorted)
      })
      .catch(() => {})
  }, [])

  const loadDefaultFormats = useCallback(() => {
    fetch('/api/default-formats')
      .then(r => r.ok ? r.json() : Promise.reject())
      .then((data: { defaults: DefaultFormatMapping[] }) => setDefaultFormats(data.defaults))
      .catch(() => {})
  }, [])

  // Load settings once on mount
  useEffect(() => {
    fetch('/api/settings')
      .then(r => r.ok ? r.json() : Promise.reject('Failed to load settings'))
      .then((data: AppSettings) => {
        setTheme(data.theme as ThemeName)
        setAutoDownload(data.auto_download)
        setSaveOriginals(data.keep_originals)
        setCleanupEnabled(data.cleanup_enabled)
        setCleanupTtl(data.cleanup_ttl_minutes)
        setLoaded(true)
      })
      .catch(() => setLoaded(true)) // fall back to defaults silently
    loadConversionMap()
    loadDefaultFormats()
  }, [setTheme, loadConversionMap, loadDefaultFormats])

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
      const payload: Record<string, unknown> = { theme, auto_download: autoDownload, keep_originals: saveOriginals }
      if (isAdmin) {
        payload.cleanup_enabled = cleanupEnabled
        payload.cleanup_ttl_minutes = cleanupTtl
      }
      const response = await fetch('/api/settings', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      if (!response.ok) throw new Error('Failed to save settings')
      setKeepOriginals(saveOriginals)
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save settings')
    } finally {
      setSaving(false)
    }
  }

  const handleAddDefaultFormat = async () => {
    if (!newInputFormat || !newOutputFormat) return
    try {
      const response = await fetch('/api/default-formats', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ input_format: newInputFormat, output_format: newOutputFormat }),
      })
      if (!response.ok) throw new Error()
      loadDefaultFormats()
      setNewInputFormat('')
      setNewOutputFormat('')
    } catch {
      setError('Failed to save default format')
    }
  }

  const handleUpdateDefaultFormat = async (input_format: string, output_format: string) => {
    try {
      const response = await fetch('/api/default-formats', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ input_format, output_format }),
      })
      if (!response.ok) throw new Error()
      loadDefaultFormats()
    } catch {
      setError('Failed to update default format')
    }
  }

  const handleDeleteDefaultFormat = async (input_format: string) => {
    try {
      const response = await fetch(`/api/default-formats/${encodeURIComponent(input_format)}`, { method: 'DELETE' })
      if (!response.ok) throw new Error()
      loadDefaultFormats()
    } catch {
      setError('Failed to delete default format')
    }
  }

  // Available input formats that don't already have a default set
  const availableInputFormats = Object.keys(conversionMap)
    .filter(f => !defaultFormats.some(d => d.input_format === f))
    .sort()

  // When the new input format changes, auto-select the first available output
  const newOutputOptions = newInputFormat ? (conversionMap[newInputFormat] || []) : []

  const handleClearConversions = () => {
    setConfirmDialog({
      isOpen: true,
      title: 'Clear Conversion History?',
      message: 'You are about to clear conversion history and delete converted files. This action cannot be undone. Do you wish to proceed?',
      confirmLabel: 'Yes, Clear History',
      onConfirm: () => {
        setConfirmDialog(null)
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
      },
    })
  }

  const handleClearUploads = () => {
    setConfirmDialog({
      isOpen: true,
      title: 'Clear Uploaded Files?',
      message: 'You are about to delete all uploaded files. This action cannot be undone. Do you wish to proceed?',
      confirmLabel: 'Yes, Clear Files',
      onConfirm: () => {
        setConfirmDialog(null)
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
      },
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
                  <p className="text-text-muted text-sm">Automatically clean up uploads & conversions after a set time</p>
                  {!isAdmin && <p className="text-text-muted text-xs italic mt-1">Managed by an administrator</p>}
                </div>
                <button
                  onClick={() => setCleanupEnabled(v => !v)}
                  disabled={!isAdmin}
                  className={`relative w-12 h-6 rounded-full transition-colors duration-200 focus:outline-none ${cleanupEnabled ? 'bg-success' : 'bg-surface-dark border border-surface-light'} ${!isAdmin ? 'opacity-50 cursor-not-allowed' : ''}`}
                >
                  <span
                    className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform duration-200 ${cleanupEnabled ? 'translate-x-6' : 'translate-x-0'}`}
                  />
                </button>
              </div>

              {cleanupEnabled && (
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-text font-medium">Cleanup Interval</p>
                  <p className="text-text-muted text-sm">Minutes before uploads & conversions are cleaned up</p>
                </div>
                <div className="flex items-center gap-2">
                  <div className={`flex items-center bg-surface-dark border border-surface-light rounded-lg overflow-hidden ${!isAdmin ? 'opacity-50 pointer-events-none' : ''}`}>
                    <button
                      onClick={() => setCleanupTtl(v => Math.max(1, v - 1))}
                      disabled={!isAdmin}
                      className="px-3 py-2 text-text-muted hover:text-text hover:bg-surface-light transition-colors duration-150 text-base leading-none select-none"
                      aria-label="Decrease"
                    >−</button>
                    <input
                      type="number"
                      min={1}
                      max={10080}
                      value={cleanupTtl}
                      disabled={!isAdmin}
                      onChange={e => setCleanupTtl(Math.max(1, parseInt(e.target.value) || 1))}
                      className="w-16 bg-transparent text-text text-sm text-center py-2 focus:outline-none [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
                    />
                    <button
                      onClick={() => setCleanupTtl(v => Math.min(10080, v + 1))}
                      disabled={!isAdmin}
                      className="px-3 py-2 text-text-muted hover:text-text hover:bg-surface-light transition-colors duration-150 text-base leading-none select-none"
                      aria-label="Increase"
                    >+</button>
                  </div>
                  <span className="text-text-muted text-sm">min</span>
                </div>
              </div>
              )}
            </div>
          </section>

          {/* Save */}
          <div className="flex justify-end">
            <button
              onClick={handleSave}
              disabled={saving}
              className="bg-success hover:bg-success-dark text-white font-semibold py-2 px-8 rounded-lg transition duration-200 shadow-md hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {saving ? 'Saving...' : saved ? 'Saved!' : 'Save Changes'}
            </button>
          </div>

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

          {/* Default Formats */}
          <section className="bg-surface-light rounded-xl p-6">
            <h2 className="text-lg font-semibold text-text mb-1">Default Formats</h2>
            <p className="text-text-muted text-sm mb-4">Set default output formats for specific input file types. These can still be overridden per file.</p>

            {defaultFormats.length > 0 && (
              <div className="mb-4 overflow-hidden rounded-lg border border-surface-dark">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-surface-dark">
                      <th className="text-left text-text-muted font-medium px-4 py-2.5">Input Format</th>
                      <th className="text-left text-text-muted font-medium px-4 py-2.5">Default Output</th>
                      <th className="w-10" />
                    </tr>
                  </thead>
                  <tbody>
                    {defaultFormats.map(d => (
                      <tr key={d.input_format} className="border-t border-surface-dark">
                        <td className="px-4 py-2.5 text-text font-mono">{d.input_format}</td>
                        <td className="px-4 py-2.5">
                          <select
                            value={d.output_format}
                            onChange={e => handleUpdateDefaultFormat(d.input_format, e.target.value)}
                            className="bg-surface-dark text-text border border-surface-light rounded-lg py-1.5 px-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
                          >
                            {(conversionMap[d.input_format] || [d.output_format]).map(fmt => (
                              <option key={fmt} value={fmt}>{fmt}</option>
                            ))}
                          </select>
                        </td>
                        <td className="px-2 py-2.5 text-center">
                          <button
                            onClick={() => handleDeleteDefaultFormat(d.input_format)}
                            className="text-text-muted hover:text-primary transition-colors duration-150 p-1"
                            title="Remove default"
                          >
                            <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                            </svg>
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {availableInputFormats.length > 0 ? (
              <div className="flex items-center gap-3">
                <select
                  value={newInputFormat}
                  onChange={e => { setNewInputFormat(e.target.value); setNewOutputFormat('') }}
                  className="bg-surface-dark text-text border border-surface-light rounded-lg py-2 px-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 min-w-[140px]"
                >
                  <option value="">Input format...</option>
                  {availableInputFormats.map(f => (
                    <option key={f} value={f}>{f}</option>
                  ))}
                </select>
                <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4 text-text-muted flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M14 5l7 7m0 0l-7 7m7-7H3" />
                </svg>
                <select
                  value={newOutputFormat}
                  onChange={e => setNewOutputFormat(e.target.value)}
                  disabled={!newInputFormat}
                  className="bg-surface-dark text-text border border-surface-light rounded-lg py-2 px-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 min-w-[140px] disabled:opacity-50"
                >
                  <option value="">Output format...</option>
                  {newOutputOptions.map(f => (
                    <option key={f} value={f}>{f}</option>
                  ))}
                </select>
                <button
                  onClick={handleAddDefaultFormat}
                  disabled={!newInputFormat || !newOutputFormat}
                  className="bg-primary/20 hover:bg-primary/40 text-primary-light font-semibold py-2 px-4 rounded-lg transition duration-200 text-sm disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Add
                </button>
              </div>
            ) : defaultFormats.length > 0 ? (
              <p className="text-text-muted text-sm">All available input formats have defaults configured.</p>
            ) : (
              <p className="text-text-muted text-sm">Loading available formats...</p>
            )}
          </section>

        </div>

      </div>

      {/* Confirmation Dialog */}
      {confirmDialog && (
        <ConfirmDialog
          isOpen={confirmDialog.isOpen}
          title={confirmDialog.title}
          message={confirmDialog.message}
          confirmLabel={confirmDialog.confirmLabel}
          isDestructive={true}
          onConfirm={confirmDialog.onConfirm}
          onCancel={() => setConfirmDialog(null)}
        />
      )}
    </div>
  )
}

export default Settings
