import { useState, useRef, useEffect, useCallback, useMemo } from 'react'
import { useTheme, type ThemeName } from '../ThemeContext'
import { useAuth } from '../AuthContext'
import { useTranslation } from 'react-i18next'
import {
  SUPPORTED_LANGUAGES,
  clearStoredLanguagePreference,
  getStoredLanguagePreference,
  setStoredLanguagePreference,
} from '../i18n'
import { ConfirmDialog } from '../components/ConfirmDialog'
import FormatDropdown from '../components/FormatDropdown'
import { authFetch as fetch } from '../utils/api'
import {
  DEFAULT_DATETIME_DISPLAY_FORMAT,
  formatDateTimeForDisplay,
  isValidDateTimeDisplayFormat,
} from '../utils/datetime'
import {
  BUILTIN_THEMES,
  FALLBACK_THEME,
  THEME_COLOR_TOKENS,
  type CustomTheme,
  type ThemeColorToken,
  type ThemeColors,
} from '../utils/themeRegistry'

interface Theme {
  value: string
  label: string
  colors: string[]
  custom: boolean
}

/** Default hex value used when seeding a new custom theme form. */
const DEFAULT_NEW_THEME_COLORS: ThemeColors = {
  primary:       '#ef4444',
  primary_light: '#f87171',
  primary_dark:  '#dc2626',
  accent:        '#f59e0b',
  success:       '#16a34a',
  success_light: '#22c55e',
  success_dark:  '#15803d',
  surface_dark:  '#0f172a',
  surface_light: '#1e293b',
  text:          '#f8fafc',
  text_muted:    '#94a3b8',
}

interface DefaultFormatMapping {
  input_format: string
  output_format: string
}

interface DefaultQualityMapping {
  output_format: string
  quality: string
}

interface DefaultCompressionLevelMapping {
  media_format: string
  compression_level: string
}

interface ConverterInfo {
  name: string
  supported_input_formats: string[]
  supported_output_formats: string[]
  formats_with_qualities: string[]
  qualities: string[]
}

interface CompressorInfo {
  name: string
  supported_formats: string[]
  formats_with_compression_levels: string[]
  compression_levels: string[]
}

/**
  Built-in themes are baked into index.css; we only need their swatch
  metadata here. Custom themes are appended from the runtime registry
  (`useTheme().customThemes`), with their swatch derived from the live
  color values.
*/
const BUILTIN_THEME_OPTIONS: Theme[] = BUILTIN_THEMES.map(b => ({
  value: b.key,
  label: b.label,
  colors: [b.swatch[0], b.swatch[1]],
  custom: false,
}))

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
  datetime_display_format: string
}

const DATETIME_FORMAT_PREVIEW_VALUE = new Date(2026, 4, 28, 14, 30, 38)

const LANGUAGE_LABELS: Record<(typeof SUPPORTED_LANGUAGES)[number], string> = {
  en: 'English',
  az: 'Azərbaycanca',
  de: 'Deutsch',
  es: 'Español',
  pl: 'Polski',
  pt: 'Português',
  it: 'Italiano',
  da: 'Dansk',
  fr: 'Français',
  hi: 'Hindi',
  cs: 'Čeština',
  tr: 'Türkçe',
  'zh-CN': '简体中文',
}

const BROWSER_DEFAULT_LANGUAGE = 'browser-default'
const BROWSER_DEFAULT_LABEL = 'Browser Default'

function normalizeLanguage(value: string) {
  if (SUPPORTED_LANGUAGES.includes(value as (typeof SUPPORTED_LANGUAGES)[number])) {
    return value as (typeof SUPPORTED_LANGUAGES)[number]
  }

  const partialMatch = SUPPORTED_LANGUAGES.find(language => value === language || value.startsWith(`${language}-`) || language.startsWith(`${value}-`))
  return partialMatch ?? 'en'
}

function Settings() {
  const {
    theme,
    setTheme,
    setKeepOriginals,
    dateTimeDisplayFormat,
    setDateTimeDisplayFormat,
    customThemes,
    refreshThemes,
  } = useTheme()
  const { isAdmin } = useAuth()
  const { t, i18n } = useTranslation()
  const [selectedLanguagePreference, setSelectedLanguagePreference] = useState<string | null>(() => getStoredLanguagePreference())
  const selectedLanguage = selectedLanguagePreference
    ? normalizeLanguage(selectedLanguagePreference)
    : BROWSER_DEFAULT_LANGUAGE

  // Merge built-ins with the runtime-registered custom themes. Memoised so
  // dropdown identity is stable across re-renders.
  const allThemes = useMemo<Theme[]>(() => {
    const customOptions: Theme[] = customThemes.map(ct => ({
      value: ct.key,
      label: ct.name,
      colors: [ct.colors.primary, ct.colors.surface_dark],
      custom: true,
    }))
    return [...BUILTIN_THEME_OPTIONS, ...customOptions]
  }, [customThemes])

  // ===== Custom theme CRUD state =====
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [editingKey, setEditingKey] = useState<string | null>(null)
  const [newThemeName, setNewThemeName] = useState('')
  const [newThemeColors, setNewThemeColors] = useState<ThemeColors>({ ...DEFAULT_NEW_THEME_COLORS })
  const [themeFormError, setThemeFormError] = useState<string | null>(null)
  const [themeFormSaving, setThemeFormSaving] = useState(false)
  const [autoDownload, setAutoDownload] = useState(false)
  const [saveOriginals, setSaveOriginals] = useState(true)
  const [dateTimeFormat, setDateTimeFormat] = useState(dateTimeDisplayFormat)
  const [cleanupEnabled, setCleanupEnabled] = useState(true)
  const [cleanupTtl, setCleanupTtl] = useState(60)
  const [themeOpen, setThemeOpen] = useState(false)
  const [languageOpen, setLanguageOpen] = useState(false)
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
  const languageRef = useRef<HTMLDivElement>(null)

  // Default format mappings
  const [defaultFormats, setDefaultFormats] = useState<DefaultFormatMapping[]>([])
  const [conversionMap, setConversionMap] = useState<Record<string, string[]>>({})
  const [newInputFormat, setNewInputFormat] = useState('')
  const [newOutputFormat, setNewOutputFormat] = useState('')

  // Default quality mappings
  const [defaultQualities, setDefaultQualities] = useState<DefaultQualityMapping[]>([])
  const [qualityFormatsMap, setQualityFormatsMap] = useState<Record<string, string[]>>({})
  const [newQualityFormat, setNewQualityFormat] = useState('')
  const [newQuality, setNewQuality] = useState('')

  // Default compression level mappings
  const [defaultCompressionLevels, setDefaultCompressionLevels] = useState<DefaultCompressionLevelMapping[]>([])
  const [compressionFormatsMap, setCompressionFormatsMap] = useState<Record<string, string[]>>({})
  const [newCompressionFormat, setNewCompressionFormat] = useState('')
  const [newCompressionLevel, setNewCompressionLevel] = useState('')

  // Build conversion map from converters API (input_format -> sorted output_formats)
  // and quality formats map (output_format -> sorted quality_options)
  const loadConversionMap = useCallback(() => {
    fetch('/api/converters')
      .then(r => r.ok ? r.json() : Promise.reject())
      .then((data: { converters: ConverterInfo[] }) => {
        const map: Record<string, Set<string>> = {}
        const qMap: Record<string, Set<string>> = {}
        for (const c of data.converters) {
          for (const inp of c.supported_input_formats) {
            for (const out of c.supported_output_formats) {
              if (inp !== out) {
                if (!map[inp]) map[inp] = new Set()
                map[inp].add(out)
              }
            }
          }
          for (const fmt of (c.formats_with_qualities || [])) {
            if (!qMap[fmt]) qMap[fmt] = new Set()
            for (const q of (c.qualities || [])) {
              qMap[fmt].add(q)
            }
          }
        }
        const sorted: Record<string, string[]> = {}
        for (const [k, v] of Object.entries(map)) {
          sorted[k] = [...v].sort()
        }
        setConversionMap(sorted)
        const qualityOrder: Record<string, number> = { low: 0, medium: 1, high: 2 }
        const sortedQ: Record<string, string[]> = {}
        for (const [k, v] of Object.entries(qMap)) {
          sortedQ[k] = [...v].sort((a, b) => (qualityOrder[a] ?? 99) - (qualityOrder[b] ?? 99))
        }
        setQualityFormatsMap(sortedQ)
      })
      .catch(() => {})
  }, [])

  const loadDefaultFormats = useCallback(() => {
    fetch('/api/default-formats')
      .then(r => r.ok ? r.json() : Promise.reject())
      .then((data: { defaults: DefaultFormatMapping[] }) => setDefaultFormats(data.defaults))
      .catch(() => {})
  }, [])

  const loadDefaultQualities = useCallback(() => {
    fetch('/api/default-qualities')
      .then(r => r.ok ? r.json() : Promise.reject())
      .then((data: { defaults: DefaultQualityMapping[] }) => setDefaultQualities(data.defaults))
      .catch(() => {})
  }, [])

  // Build compression formats map from compressors API (media_format -> sorted levels)
  const loadCompressionMap = useCallback(() => {
    fetch('/api/compressors')
      .then(r => r.ok ? r.json() : Promise.reject())
      .then((data: { compressors: CompressorInfo[] }) => {
        const map: Record<string, Set<string>> = {}
        for (const c of data.compressors) {
          for (const fmt of (c.formats_with_compression_levels || [])) {
            if (!map[fmt]) map[fmt] = new Set()
            for (const lvl of (c.compression_levels || [])) {
              map[fmt].add(lvl)
            }
          }
        }
        const levelOrder: Record<string, number> = { light: 0, balanced: 1, max: 2 }
        const sorted: Record<string, string[]> = {}
        for (const [k, v] of Object.entries(map)) {
          sorted[k] = [...v].sort((a, b) => (levelOrder[a] ?? 99) - (levelOrder[b] ?? 99))
        }
        setCompressionFormatsMap(sorted)
      })
      .catch(() => {})
  }, [])

  const loadDefaultCompressionLevels = useCallback(() => {
    fetch('/api/default-compression-levels')
      .then(r => r.ok ? r.json() : Promise.reject())
      .then((data: { defaults: DefaultCompressionLevelMapping[] }) => setDefaultCompressionLevels(data.defaults))
      .catch(() => {})
  }, [])

  // Load settings once on mount
  useEffect(() => {
    fetch('/api/settings')
      .then(r => r.ok ? r.json() : Promise.reject(t('settings.loadFailed')))
      .then((data: AppSettings) => {
        setTheme(data.theme as ThemeName)
        setAutoDownload(data.auto_download)
        setSaveOriginals(data.keep_originals)
        setDateTimeFormat(data.datetime_display_format || DEFAULT_DATETIME_DISPLAY_FORMAT)
        setCleanupEnabled(data.cleanup_enabled)
        setCleanupTtl(data.cleanup_ttl_minutes)
        setLoaded(true)
      })
      .catch(() => setLoaded(true)) // fall back to defaults silently
    loadConversionMap()
    loadDefaultFormats()
    loadDefaultQualities()
    loadCompressionMap()
    loadDefaultCompressionLevels()
  }, [setTheme, loadConversionMap, loadDefaultFormats, loadDefaultQualities, loadCompressionMap, loadDefaultCompressionLevels])

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (themeRef.current && !themeRef.current.contains(e.target as Node)) {
        setThemeOpen(false)
      }
      if (languageRef.current && !languageRef.current.contains(e.target as Node)) {
        setLanguageOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const handleSave = async () => {
    if (!isValidDateTimeDisplayFormat(dateTimeFormat)) {
      setError(t('settings.dateTimeDisplayFormatInvalid'))
      return
    }

    setSaving(true)
    setError(null)
    try {
      const payload: Record<string, unknown> = {
        theme,
        auto_download: autoDownload,
        keep_originals: saveOriginals,
        datetime_display_format: dateTimeFormat.trim(),
      }
      if (isAdmin) {
        payload.cleanup_enabled = cleanupEnabled
        payload.cleanup_ttl_minutes = cleanupTtl
      }
      const response = await fetch('/api/settings', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      if (!response.ok) throw new Error(t('settings.saveFailed'))
      setKeepOriginals(saveOriginals)
      setDateTimeDisplayFormat(dateTimeFormat)
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch (err) {
      setError(err instanceof Error ? err.message : t('settings.saveFailed'))
    } finally {
      setSaving(false)
    }
  }

  const stableDateTimeFormatPreview = formatDateTimeForDisplay(
    DATETIME_FORMAT_PREVIEW_VALUE,
    { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' },
    undefined,
    dateTimeFormat,
  )

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
      setError(t('settings.saveFailed'))
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
      setError(t('settings.saveFailed'))
    }
  }

  const handleDeleteDefaultFormat = async (input_format: string) => {
    try {
      const response = await fetch(`/api/default-formats/${encodeURIComponent(input_format)}`, { method: 'DELETE' })
      if (!response.ok) throw new Error()
      loadDefaultFormats()
    } catch {
      setError(t('settings.saveFailed'))
    }
  }

  const handleAddDefaultQuality = async () => {
    if (!newQualityFormat || !newQuality) return
    try {
      const response = await fetch('/api/default-qualities', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ output_format: newQualityFormat, quality: newQuality }),
      })
      if (!response.ok) throw new Error()
      loadDefaultQualities()
      setNewQualityFormat('')
      setNewQuality('')
    } catch {
      setError(t('settings.saveFailed'))
    }
  }

  const handleUpdateDefaultQuality = async (output_format: string, quality: string) => {
    try {
      const response = await fetch('/api/default-qualities', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ output_format, quality }),
      })
      if (!response.ok) throw new Error()
      loadDefaultQualities()
    } catch {
      setError(t('settings.saveFailed'))
    }
  }

  const handleDeleteDefaultQuality = async (output_format: string) => {
    try {
      const response = await fetch(`/api/default-qualities/${encodeURIComponent(output_format)}`, { method: 'DELETE' })
      if (!response.ok) throw new Error()
      loadDefaultQualities()
    } catch {
      setError(t('settings.saveFailed'))
    }
  }

  const handleAddDefaultCompressionLevel = async () => {
    if (!newCompressionFormat || !newCompressionLevel) return
    try {
      const response = await fetch('/api/default-compression-levels', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ media_format: newCompressionFormat, compression_level: newCompressionLevel }),
      })
      if (!response.ok) throw new Error()
      loadDefaultCompressionLevels()
      setNewCompressionFormat('')
      setNewCompressionLevel('')
    } catch {
      setError(t('settings.saveFailed'))
    }
  }

  const handleUpdateDefaultCompressionLevel = async (media_format: string, compression_level: string) => {
    try {
      const response = await fetch('/api/default-compression-levels', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ media_format, compression_level }),
      })
      if (!response.ok) throw new Error()
      loadDefaultCompressionLevels()
    } catch {
      setError(t('settings.saveFailed'))
    }
  }

  const handleDeleteDefaultCompressionLevel = async (media_format: string) => {
    try {
      const response = await fetch(`/api/default-compression-levels/${encodeURIComponent(media_format)}`, { method: 'DELETE' })
      if (!response.ok) throw new Error()
      loadDefaultCompressionLevels()
    } catch {
      setError(t('settings.saveFailed'))
    }
  }

  // ===== Custom theme handlers =====

  const resetThemeForm = useCallback(() => {
    setEditingKey(null)
    setNewThemeName('')
    setNewThemeColors({ ...DEFAULT_NEW_THEME_COLORS })
    setThemeFormError(null)
  }, [])

  const startEditTheme = useCallback((ct: CustomTheme) => {
    setEditingKey(ct.key)
    setNewThemeName(ct.name)
    setNewThemeColors({ ...ct.colors })
    setThemeFormError(null)
    setShowCreateForm(true)
  }, [])

  const handleSaveCustomTheme = async () => {
    if (!newThemeName.trim()) {
      setThemeFormError(t('settings.themeNameRequired'))
      return
    }
    setThemeFormSaving(true)
    setThemeFormError(null)
    try {
      const isEdit = editingKey !== null
      const url = isEdit
        ? `/api/settings/themes/${encodeURIComponent(editingKey!)}`
        : '/api/settings/themes'
      const response = await fetch(url, {
        method: isEdit ? 'PUT' : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: newThemeName.trim(), colors: newThemeColors }),
      })
      if (!response.ok) {
        const body = await response.json().catch(() => null)
        throw new Error(body?.detail || t('settings.saveFailed'))
      }
      await refreshThemes()
      resetThemeForm()
      setShowCreateForm(false)
    } catch (err) {
      setThemeFormError(err instanceof Error ? err.message : t('settings.saveFailed'))
    } finally {
      setThemeFormSaving(false)
    }
  }

  const handleDeleteCustomTheme = (ct: CustomTheme) => {
    setConfirmDialog({
      isOpen: true,
      title: t('settings.deleteCustomThemeTitle'),
      message: t('settings.deleteCustomThemeMessage', { name: ct.name }),
      confirmLabel: t('settings.deleteCustomThemeConfirm'),
      onConfirm: () => {
        setConfirmDialog(null)
        void (async () => {
          try {
            const response = await fetch(
              `/api/settings/themes/${encodeURIComponent(ct.key)}`,
              { method: 'DELETE' },
            )
            if (!response.ok && response.status !== 204) {
              throw new Error(t('settings.saveFailed'))
            }
            // If we just deleted the active theme, reset to the fallback.
            if (theme === ct.key) {
              setTheme(FALLBACK_THEME)
            }
            await refreshThemes()
          } catch (err) {
            setError(err instanceof Error ? err.message : t('settings.saveFailed'))
          }
        })()
      },
    })
  }

  // Available input formats that don't already have a default set
  const availableInputFormats = Object.keys(conversionMap)
    .filter(f => !defaultFormats.some(d => d.input_format === f))
    .sort()

  // When the new input format changes, auto-select the first available output
  const newOutputOptions = newInputFormat ? (conversionMap[newInputFormat] || []) : []

  // Available output formats with quality options that don't already have a default set
  const availableQualityFormats = Object.keys(qualityFormatsMap)
    .filter(f => !defaultQualities.some(d => d.output_format === f))
    .sort()

  // When the new quality format changes, auto-select the first available quality
  const newQualityOptions = newQualityFormat ? (qualityFormatsMap[newQualityFormat] || []) : []

  // Available media formats with compression levels that don't already have a default set
  const availableCompressionFormats = Object.keys(compressionFormatsMap)
    .filter(f => !defaultCompressionLevels.some(d => d.media_format === f))
    .sort()

  // When the new compression format changes, the available levels follow
  const newCompressionLevelOptions = newCompressionFormat ? (compressionFormatsMap[newCompressionFormat] || []) : []

  const handleClearConversions = () => {
    setConfirmDialog({
      isOpen: true,
      title: t('confirm.clearConversionsTitle'),
      message: t('confirm.clearConversionsMessage'),
      confirmLabel: t('confirm.clearConversionsConfirm'),
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
      title: t('confirm.clearUploadsTitle'),
      message: t('confirm.clearUploadsMessage'),
      confirmLabel: t('confirm.clearUploadsConfirm'),
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
          <p className="text-text-muted text-sm">{t('settings.loadingSettings')}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-surface-dark to-surface-light p-8">
      <div className="max-w-4xl mx-auto">
        <div className="flex justify-between items-center mb-6 min-h-[4rem]">
          <h1 className="text-3xl font-bold text-primary">{t('settings.title')}</h1>
        </div>

        {error && (
          <div className="p-3 bg-primary/20 border border-primary rounded-lg text-primary-light text-sm mb-4">
            {error}
          </div>
        )}

        <div className="space-y-6">

          {/* Appearance */}
          <section className="bg-surface-light rounded-xl p-6">
            <h2 className="text-lg font-semibold text-text mb-4">{t('settings.appearance')}</h2>
            <div className="flex flex-col gap-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-text font-medium">{t('settings.theme')}</p>
                  <p className="text-text-muted text-sm">{t('settings.themeDescription')}</p>
                </div>
                <div className="relative" ref={themeRef}>
                  <button
                    onClick={() => setThemeOpen(o => !o)}
                    className="flex items-center gap-2 bg-surface-dark text-text border border-surface-light rounded-lg py-2 px-4 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 transition duration-200 min-w-[200px]"
                  >
                    <ThemeSwatch colors={allThemes.find(t => t.value === theme)?.colors ?? []} />
                    <span className="flex-1 text-left">{allThemes.find(t => t.value === theme)?.label ?? theme}</span>
                    <svg className={`w-4 h-4 transition-transform duration-200 ${themeOpen ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                    </svg>
                  </button>
                  {themeOpen && (
                    <div className="absolute right-0 mt-1 w-full bg-surface-dark border border-surface-light rounded-lg shadow-xl z-10 overflow-hidden max-h-80 overflow-y-auto">
                      {allThemes.map(opt => (
                        <button
                          key={opt.value}
                          onClick={() => { setTheme(opt.value as ThemeName); setThemeOpen(false) }}
                          className={`flex items-center gap-3 w-full px-4 py-2.5 text-sm text-left transition duration-150 ${
                            theme === opt.value
                              ? 'bg-primary/20 text-primary-light'
                              : 'text-text hover:bg-surface-light'
                          }`}
                        >
                          <ThemeSwatch colors={opt.colors} />
                          <span className="flex-1">{opt.label}</span>
                          {opt.custom && (
                            <span className="text-[10px] uppercase tracking-wider text-text-muted">
                              {t('settings.customThemeBadge')}
                            </span>
                          )}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              <div className="border-t border-surface-dark pt-4 mt-2">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <p className="text-text font-medium">{t('settings.language')}</p>
                    <p className="text-text-muted text-sm">{t('settings.languageDescription')}</p>
                  </div>
                  <div className="relative" ref={languageRef}>
                    <button
                      onClick={() => setLanguageOpen(open => !open)}
                      className="flex items-center gap-2 bg-surface-dark text-text border border-surface-light rounded-lg py-2 px-4 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 transition duration-200 min-w-[200px]"
                    >
                      <span className="flex-1 text-left">
                        {selectedLanguage === BROWSER_DEFAULT_LANGUAGE
                          ? BROWSER_DEFAULT_LABEL
                          : LANGUAGE_LABELS[selectedLanguage]}
                      </span>
                      <svg className={`w-4 h-4 transition-transform duration-200 ${languageOpen ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                      </svg>
                    </button>
                    {languageOpen && (
                      <div className="absolute right-0 mt-1 w-full bg-surface-dark border border-surface-light rounded-lg shadow-xl z-10 overflow-hidden max-h-80 overflow-y-auto">
                        <button
                          onClick={() => {
                            clearStoredLanguagePreference()
                            setSelectedLanguagePreference(null)
                            void i18n.changeLanguage()
                            setLanguageOpen(false)
                          }}
                          className={`flex items-center gap-3 w-full px-4 py-2.5 text-sm text-left transition duration-150 ${
                            selectedLanguage === BROWSER_DEFAULT_LANGUAGE
                              ? 'bg-primary/20 text-primary-light'
                              : 'text-text hover:bg-surface-light'
                          }`}
                        >
                          <span className="flex-1">{BROWSER_DEFAULT_LABEL}</span>
                        </button>
                        {SUPPORTED_LANGUAGES.map(language => (
                          <button
                            key={language}
                            onClick={() => {
                              setStoredLanguagePreference(language)
                              setSelectedLanguagePreference(language)
                              void i18n.changeLanguage(language)
                              setLanguageOpen(false)
                            }}
                            className={`flex items-center gap-3 w-full px-4 py-2.5 text-sm text-left transition duration-150 ${
                              selectedLanguage === language
                                ? 'bg-primary/20 text-primary-light'
                                : 'text-text hover:bg-surface-light'
                            }`}
                          >
                            <span className="flex-1">{LANGUAGE_LABELS[language]}</span>
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </div>

              <div className="border-t border-surface-dark pt-4 mt-2">
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                  <div className="max-w-2xl">
                    <p className="text-text font-medium">{t('settings.dateTimeDisplayFormat')}</p>
                    <p className="text-text-muted text-sm">{t('settings.dateTimeDisplayFormatDescription')}</p>
                    <p className="text-text-muted text-xs mt-2">{t('settings.dateTimeDisplayFormatHint')}</p>
                  </div>
                  <button
                    onClick={() => setDateTimeFormat(DEFAULT_DATETIME_DISPLAY_FORMAT)}
                    className="self-start rounded-lg border border-surface-dark px-3 py-2 text-xs font-semibold uppercase tracking-wide text-text-muted transition-colors duration-150 hover:border-surface-light hover:text-text"
                  >
                    {t('settings.useBrowserLocale')}
                  </button>
                </div>
                <div className="mt-3 flex flex-col gap-3 lg:flex-row lg:items-center">
                  <input
                    type="text"
                    value={dateTimeFormat}
                    onChange={e => setDateTimeFormat(e.target.value)}
                    placeholder={t('settings.dateTimeDisplayFormatPlaceholder')}
                    className="w-full rounded-lg border border-surface-dark bg-surface-dark px-4 py-2.5 text-sm text-text outline-none transition duration-200 focus:border-primary focus:ring-2 focus:ring-primary/30 lg:max-w-md"
                  />
                  <div className="text-sm text-text-muted">
                    <span className="font-medium text-text">{t('settings.dateTimeDisplayFormatPreview')}:</span>{' '}
                    <span className="font-mono">{stableDateTimeFormatPreview}</span>
                  </div>
                </div>
              </div>

              {isAdmin && (
                <div className="border-t border-surface-dark pt-4 mt-2">
                  <div className="flex items-center justify-between mb-3">
                    <div>
                      <p className="text-text font-medium">{t('settings.customThemes')}</p>
                      <p className="text-text-muted text-sm">{t('settings.customThemesDescription')}</p>
                    </div>
                    <button
                      onClick={() => {
                        if (showCreateForm) {
                          resetThemeForm()
                          setShowCreateForm(false)
                        } else {
                          resetThemeForm()
                          setShowCreateForm(true)
                        }
                      }}
                      className="bg-primary text-white text-sm py-2 px-3 rounded-lg hover:bg-primary-dark transition-colors duration-150"
                    >
                      {showCreateForm
                        ? t('settings.cancelCustomTheme')
                        : t('settings.createCustomTheme')}
                    </button>
                  </div>

                  {customThemes.length === 0 && !showCreateForm && (
                    <p className="text-text-muted text-sm italic">{t('settings.customThemesEmpty')}</p>
                  )}

                  {customThemes.length > 0 && (
                    <ul className="flex flex-col gap-2 mb-3">
                      {customThemes.map(ct => (
                        <li
                          key={ct.key}
                          className="flex items-center gap-3 bg-surface-dark border border-surface-light rounded-lg py-2 px-3"
                        >
                          <ThemeSwatch colors={[ct.colors.primary, ct.colors.surface_dark]} />
                          <div className="flex-1 min-w-0">
                            <p className="text-text text-sm truncate">{ct.name}</p>
                            <p className="text-text-muted text-xs truncate font-mono">{ct.key}</p>
                          </div>
                          <button
                            onClick={() => startEditTheme(ct)}
                            className="text-text-muted hover:text-text text-xs uppercase tracking-wider px-2 py-1"
                          >
                            {t('settings.editCustomTheme')}
                          </button>
                          <button
                            onClick={() => handleDeleteCustomTheme(ct)}
                            className="text-primary-light hover:text-primary text-xs uppercase tracking-wider px-2 py-1"
                          >
                            {t('settings.deleteCustomTheme')}
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}

                  {showCreateForm && (
                    <div className="bg-surface-dark border border-surface-light rounded-lg p-4 flex flex-col gap-3">
                      <div>
                        <label className="text-text text-sm font-medium block mb-1" htmlFor="custom-theme-name">
                          {t('settings.themeName')}
                        </label>
                        <input
                          id="custom-theme-name"
                          type="text"
                          value={newThemeName}
                          onChange={e => setNewThemeName(e.target.value)}
                          placeholder={t('settings.themeNamePlaceholder')}
                          maxLength={64}
                          className="w-full bg-surface-light text-text border border-surface-light rounded-lg py-2 px-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
                        />
                      </div>

                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        {THEME_COLOR_TOKENS.map(token => (
                          <div key={token} className="flex items-center justify-between gap-3 bg-surface-light rounded-lg py-2 px-3">
                            <label
                              htmlFor={`custom-theme-${token}`}
                              className="text-text-muted text-xs uppercase tracking-wider"
                            >
                              {t(`settings.themeToken.${token}`)}
                            </label>
                            <div className="flex items-center gap-2">
                              <input
                                id={`custom-theme-${token}`}
                                type="color"
                                value={newThemeColors[token as ThemeColorToken]}
                                onChange={e => setNewThemeColors(prev => ({
                                  ...prev,
                                  [token]: e.target.value,
                                }))}
                                className="w-8 h-8 rounded cursor-pointer bg-transparent border border-surface-dark"
                              />
                              <span className="text-text text-xs font-mono uppercase">
                                {newThemeColors[token as ThemeColorToken]}
                              </span>
                            </div>
                          </div>
                        ))}
                      </div>

                      {themeFormError && (
                        <p className="text-primary-light text-sm">{themeFormError}</p>
                      )}

                      <div className="flex justify-end gap-2">
                        <button
                          onClick={() => { resetThemeForm(); setShowCreateForm(false) }}
                          className="bg-surface-light text-text text-sm py-2 px-3 rounded-lg hover:bg-surface-dark border border-surface-light transition-colors duration-150"
                        >
                          {t('settings.cancelCustomTheme')}
                        </button>
                        <button
                          onClick={handleSaveCustomTheme}
                          disabled={themeFormSaving}
                          className="bg-primary text-white text-sm py-2 px-3 rounded-lg hover:bg-primary-dark transition-colors duration-150 disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                          {themeFormSaving
                            ? t('settings.saving')
                            : editingKey
                              ? t('settings.updateCustomTheme')
                              : t('settings.saveCustomTheme')}
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </section>

          {/* Conversion */}
          <section className="bg-surface-light rounded-xl p-6">
            <h2 className="text-lg font-semibold text-text mb-4">{t('settings.conversion')}</h2>
            <div className="flex flex-col gap-5">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-text font-medium">{t('settings.autoDownload')}</p>
                  <p className="text-text-muted text-sm">{t('settings.autoDownloadDescription')}</p>
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
                  <p className="text-text font-medium">{t('settings.keepOriginals')}</p>
                  <p className="text-text-muted text-sm">{t('settings.keepOriginalsDescription')}</p>
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
                  <p className="text-text font-medium">{t('settings.cleanupTtl')}</p>
                  <p className="text-text-muted text-sm">{t('settings.cleanupTtlDescription')}</p>
                  {!isAdmin && <p className="text-text-muted text-xs italic mt-1">{t('settings.cleanupAdminOnly')}</p>}
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
                  <p className="text-text font-medium">{t('settings.cleanupInterval')}</p>
                  <p className="text-text-muted text-sm">{t('settings.cleanupIntervalDescription')}</p>
                </div>
                <div className="flex items-center gap-2">
                  <div className={`flex items-center bg-surface-dark border border-surface-light rounded-lg overflow-hidden ${!isAdmin ? 'opacity-50 pointer-events-none' : ''}`}>
                    <button
                      onClick={() => setCleanupTtl(v => Math.max(1, v - 1))}
                      disabled={!isAdmin}
                      className="px-3 py-2 text-text-muted hover:text-text hover:bg-surface-light transition-colors duration-150 text-base leading-none select-none"
                      aria-label={t('settings.decrease')}
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
                      aria-label={t('settings.increase')}
                    >+</button>
                  </div>
                  <span className="text-text-muted text-sm">{t('settings.min')}</span>
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
              {saving ? t('account.saving') : saved ? t('settings.saved') : t('settings.saveChanges')}
            </button>
          </div>

          {/* Data Management */}
          <section className="bg-surface-light rounded-xl p-6">
            <h2 className="text-lg font-semibold text-text mb-4">{t('settings.dataManagement')}</h2>
            <div className="flex flex-col gap-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-text font-medium">{t('settings.clearConversions')}</p>
                  <p className="text-text-muted text-sm">{t('settings.clearConversionsDescription')}</p>
                </div>
                <button
                  onClick={handleClearConversions}
                  disabled={clearConversionsStatus === 'clearing'}
                  className="bg-primary/20 hover:bg-primary/40 text-primary-light font-semibold py-2 px-5 rounded-lg transition duration-200 shadow-md hover:shadow-lg text-sm disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {clearConversionsStatus === 'clearing' ? t('settings.clearing') : clearConversionsStatus === 'success' ? t('settings.cleared') : clearConversionsStatus === 'error' ? t('settings.clearFailed') : t('settings.clearHistory')}
                </button>
              </div>

              <div className="border-t border-surface-dark" />

              <div className="flex items-center justify-between">
                <div>
                  <p className="text-text font-medium">{t('settings.clearUploads')}</p>
                  <p className="text-text-muted text-sm">{t('settings.clearUploadsDescription')}</p>
                </div>
                <button
                  onClick={handleClearUploads}
                  disabled={clearUploadsStatus === 'clearing'}
                  className="bg-primary/20 hover:bg-primary/40 text-primary-light font-semibold py-2 px-5 rounded-lg transition duration-200 shadow-md hover:shadow-lg text-sm disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {clearUploadsStatus === 'clearing' ? t('settings.clearing') : clearUploadsStatus === 'success' ? t('settings.cleared') : clearUploadsStatus === 'error' ? t('settings.clearFailed') : t('settings.clearFiles')}
                </button>
              </div>
            </div>
          </section>

          {/* Default Formats */}
          <section className="bg-surface-light rounded-xl p-6">
            <h2 className="text-lg font-semibold text-text mb-1">{t('settings.defaultFormats')}</h2>
            <p className="text-text-muted text-sm mb-4">{t('settings.defaultFormatsDescription')}</p>

            {defaultFormats.length > 0 && (
              <div className="mb-4 overflow-hidden rounded-lg border border-surface-dark">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-surface-dark">
                      <th className="text-left text-text-muted font-medium px-4 py-2.5">{t('settings.inputFormat')}</th>
                      <th className="text-left text-text-muted font-medium px-4 py-2.5">{t('settings.defaultOutput')}</th>
                      <th className="w-10" />
                    </tr>
                  </thead>
                  <tbody>
                    {defaultFormats.map(d => (
                      <tr key={d.input_format} className="border-t border-surface-dark">
                        <td className="px-4 py-2.5 text-text font-mono">{d.input_format}</td>
                        <td className="px-4 py-2.5">
                          <FormatDropdown
                            value={d.output_format}
                            formats={conversionMap[d.input_format] || [d.output_format]}
                            onChange={(format) => handleUpdateDefaultFormat(d.input_format, format)}
                            title={`${d.input_format} -> ${d.output_format}`}
                            triggerClassName="w-full max-w-[12rem] border border-surface-light bg-surface-dark px-3 py-1.5 text-text"
                          />
                        </td>
                        <td className="px-2 py-2.5 text-center">
                          <button
                            onClick={() => handleDeleteDefaultFormat(d.input_format)}
                            className="text-text-muted hover:text-primary transition-colors duration-150 p-1"
                            title={t('settings.removeDefault')}
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
              <div className="flex flex-wrap items-center gap-3">
                <FormatDropdown
                  value={newInputFormat}
                  formats={availableInputFormats}
                  onChange={(format) => { setNewInputFormat(format); setNewOutputFormat('') }}
                  placeholder={t('settings.inputFormatPlaceholder')}
                  title={newInputFormat || 'Select input format'}
                  triggerClassName="min-w-[10rem] border border-surface-light bg-surface-dark px-3 py-2 text-text"
                />
                <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4 text-text-muted flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M14 5l7 7m0 0l-7 7m7-7H3" />
                </svg>
                <FormatDropdown
                  value={newOutputFormat}
                  formats={newOutputOptions}
                  onChange={setNewOutputFormat}
                  placeholder={t('settings.outputFormatPlaceholder')}
                  title={newOutputFormat || 'Select output format'}
                  disabled={!newInputFormat}
                  triggerClassName="min-w-[10rem] border border-surface-light bg-surface-dark px-3 py-2 text-text"
                />
                <button
                  onClick={handleAddDefaultFormat}
                  disabled={!newInputFormat || !newOutputFormat}
                  className="bg-primary/20 hover:bg-primary/40 text-primary-light font-semibold py-2 px-4 rounded-lg transition duration-200 text-sm disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {t('settings.add')}
                </button>
              </div>
            ) : defaultFormats.length > 0 ? (
              <p className="text-text-muted text-sm">{t('settings.allFormatsConfigured')}</p>
            ) : (
              <p className="text-text-muted text-sm">{t('settings.loadingFormats')}</p>
            )}
          </section>

          {/* Default Qualities */}
          <section className="bg-surface-light rounded-xl p-6">
            <h2 className="text-lg font-semibold text-text mb-1">{t('settings.defaultQualities')}</h2>
            <p className="text-text-muted text-sm mb-4">{t('settings.defaultQualitiesDescription')}</p>

            {defaultQualities.length > 0 && (
              <div className="mb-4 overflow-hidden rounded-lg border border-surface-dark">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-surface-dark">
                      <th className="text-left text-text-muted font-medium px-4 py-2.5">{t('settings.outputFormat')}</th>
                      <th className="text-left text-text-muted font-medium px-4 py-2.5">{t('settings.defaultQuality')}</th>
                      <th className="w-10" />
                    </tr>
                  </thead>
                  <tbody>
                    {defaultQualities.map(d => (
                      <tr key={d.output_format} className="border-t border-surface-dark">
                        <td className="px-4 py-2.5 text-text font-mono">{d.output_format}</td>
                        <td className="px-4 py-2.5">
                          <FormatDropdown
                            value={d.quality}
                            formats={qualityFormatsMap[d.output_format] || [d.quality]}
                            onChange={(quality) => handleUpdateDefaultQuality(d.output_format, quality)}
                            title={`${d.output_format} quality: ${d.quality}`}
                            triggerClassName="w-full max-w-[12rem] border border-surface-light bg-surface-dark px-3 py-1.5 text-text"
                            presorted
                          />
                        </td>
                        <td className="px-2 py-2.5 text-center">
                          <button
                            onClick={() => handleDeleteDefaultQuality(d.output_format)}
                            className="text-text-muted hover:text-primary transition-colors duration-150 p-1"
                            title={t('settings.removeDefault')}
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

            {availableQualityFormats.length > 0 ? (
              <div className="flex flex-wrap items-center gap-3">
                <FormatDropdown
                  value={newQualityFormat}
                  formats={availableQualityFormats}
                  onChange={(format) => { setNewQualityFormat(format); setNewQuality('') }}
                  placeholder={t('settings.outputFormatPlaceholder')}
                  title={newQualityFormat || 'Select output format'}
                  triggerClassName="min-w-[10rem] border border-surface-light bg-surface-dark px-3 py-2 text-text"
                />
                <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4 text-text-muted flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M14 5l7 7m0 0l-7 7m7-7H3" />
                </svg>
                <FormatDropdown
                  value={newQuality}
                  formats={newQualityOptions}
                  onChange={setNewQuality}
                  placeholder={t('settings.qualityPlaceholder')}
                  title={newQuality || 'Select quality'}
                  disabled={!newQualityFormat}
                  triggerClassName="min-w-[10rem] border border-surface-light bg-surface-dark px-3 py-2 text-text"
                  presorted
                />
                <button
                  onClick={handleAddDefaultQuality}
                  disabled={!newQualityFormat || !newQuality}
                  className="bg-primary/20 hover:bg-primary/40 text-primary-light font-semibold py-2 px-4 rounded-lg transition duration-200 text-sm disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {t('settings.add')}
                </button>
              </div>
            ) : defaultQualities.length > 0 ? (
              <p className="text-text-muted text-sm">{t('settings.allQualitiesConfigured')}</p>
            ) : Object.keys(qualityFormatsMap).length === 0 ? (
              <p className="text-text-muted text-sm">{t('settings.loadingFormats')}</p>
            ) : null}
          </section>

          {/* Default Compression Levels */}
          <section className="bg-surface-light rounded-xl p-6">
            <h2 className="text-lg font-semibold text-text mb-1">{t('settings.defaultCompressionLevels')}</h2>
            <p className="text-text-muted text-sm mb-4">{t('settings.defaultCompressionLevelsDescription')}</p>

            {defaultCompressionLevels.length > 0 && (
              <div className="mb-4 overflow-hidden rounded-lg border border-surface-dark">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-surface-dark">
                      <th className="text-left text-text-muted font-medium px-4 py-2.5">{t('settings.mediaFormat')}</th>
                      <th className="text-left text-text-muted font-medium px-4 py-2.5">{t('settings.defaultCompressionLevel')}</th>
                      <th className="w-10" />
                    </tr>
                  </thead>
                  <tbody>
                    {defaultCompressionLevels.map(d => (
                      <tr key={d.media_format} className="border-t border-surface-dark">
                        <td className="px-4 py-2.5 text-text font-mono">{d.media_format}</td>
                        <td className="px-4 py-2.5">
                          <FormatDropdown
                            value={d.compression_level}
                            formats={compressionFormatsMap[d.media_format] || [d.compression_level]}
                            onChange={(level) => handleUpdateDefaultCompressionLevel(d.media_format, level)}
                            title={`${d.media_format}: ${d.compression_level}`}
                            triggerClassName="w-full max-w-[12rem] border border-surface-light bg-surface-dark px-3 py-1.5 text-text"
                            presorted
                          />
                        </td>
                        <td className="px-2 py-2.5 text-center">
                          <button
                            onClick={() => handleDeleteDefaultCompressionLevel(d.media_format)}
                            className="text-text-muted hover:text-primary transition-colors duration-150 p-1"
                            title={t('settings.removeDefault')}
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

            {availableCompressionFormats.length > 0 ? (
              <div className="flex flex-wrap items-center gap-3">
                <FormatDropdown
                  value={newCompressionFormat}
                  formats={availableCompressionFormats}
                  onChange={(format) => { setNewCompressionFormat(format); setNewCompressionLevel('') }}
                  placeholder={t('settings.mediaFormatPlaceholder')}
                  title={newCompressionFormat || 'Select media format'}
                  triggerClassName="min-w-[10rem] border border-surface-light bg-surface-dark px-3 py-2 text-text"
                />
                <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4 text-text-muted flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M14 5l7 7m0 0l-7 7m7-7H3" />
                </svg>
                <FormatDropdown
                  value={newCompressionLevel}
                  formats={newCompressionLevelOptions}
                  onChange={setNewCompressionLevel}
                  placeholder={t('settings.compressionLevelPlaceholder')}
                  title={newCompressionLevel || 'Select compression level'}
                  disabled={!newCompressionFormat}
                  triggerClassName="min-w-[10rem] border border-surface-light bg-surface-dark px-3 py-2 text-text"
                  presorted
                />
                <button
                  onClick={handleAddDefaultCompressionLevel}
                  disabled={!newCompressionFormat || !newCompressionLevel}
                  className="bg-primary/20 hover:bg-primary/40 text-primary-light font-semibold py-2 px-4 rounded-lg transition duration-200 text-sm disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {t('settings.add')}
                </button>
              </div>
            ) : defaultCompressionLevels.length > 0 ? (
              <p className="text-text-muted text-sm">{t('settings.allCompressionLevelsConfigured')}</p>
            ) : Object.keys(compressionFormatsMap).length === 0 ? (
              <p className="text-text-muted text-sm">{t('settings.loadingFormats')}</p>
            ) : null}
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
