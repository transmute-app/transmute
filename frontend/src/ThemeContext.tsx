import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react'
import { useAuth } from './AuthContext'
import { authFetch as fetch } from './utils/api'
import {
  DEFAULT_DATETIME_DISPLAY_FORMAT,
  readStoredDateTimeDisplayFormat,
  setStoredDateTimeDisplayFormat,
} from './utils/datetime'
import {
  FALLBACK_THEME,
  cacheRegistry,
  injectCustomThemesCSS,
  loadCustomThemes,
  readCachedRegistry,
  type CustomTheme,
} from './utils/themeRegistry'
import {
  DEFAULT_DARK_THEME,
  DEFAULT_LIGHT_THEME,
  normalizeThemeMode,
  readStoredThemePreferences,
  resolveEffectiveTheme,
  storeThemePreferences,
  type ThemeMode,
  type ThemePreferences,
} from './utils/themePreferences'

/**
 * Theme name is now an arbitrary string — built-in keys plus any custom
 * theme registered in the database. The runtime registry decides what is
 * valid; this used to be a discriminated union pinned to a fixed list.
 */
export type ThemeName = string

interface ThemeContextValue {
  theme: ThemeName
  setTheme: (theme: ThemeName) => void
  themeMode: ThemeMode
  setThemeMode: (mode: ThemeMode) => void
  lightTheme: ThemeName
  setLightTheme: (theme: ThemeName) => void
  darkTheme: ThemeName
  setDarkTheme: (theme: ThemeName) => void
  keepOriginals: boolean
  setKeepOriginals: (value: boolean) => void
  dateTimeDisplayFormat: string
  setDateTimeDisplayFormat: (value: string) => void
  customThemes: CustomTheme[]
  /** Re-fetch the registry from the backend and re-inject the CSS rules. */
  refreshThemes: () => Promise<void>
}

const ThemeContext = createContext<ThemeContextValue>({
  theme: FALLBACK_THEME,
  setTheme: () => {},
  themeMode: 'manual',
  setThemeMode: () => {},
  lightTheme: DEFAULT_LIGHT_THEME,
  setLightTheme: () => {},
  darkTheme: DEFAULT_DARK_THEME,
  setDarkTheme: () => {},
  keepOriginals: true,
  setKeepOriginals: () => {},
  dateTimeDisplayFormat: DEFAULT_DATETIME_DISPLAY_FORMAT,
  setDateTimeDisplayFormat: () => {},
  customThemes: [],
  refreshThemes: async () => {},
})

const KEEP_ORIGINALS_KEY = 'transmute-keep-originals'

function getSystemPrefersDark(): boolean {
  return typeof window.matchMedia === 'function'
    && window.matchMedia('(prefers-color-scheme: dark)').matches
}

function readStoredKeepOriginals(): boolean {
  try {
    const v = localStorage.getItem(KEEP_ORIGINALS_KEY)
    if (v !== null) return v === 'true'
  } catch { /* storage unavailable */ }
  return true
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const { status } = useAuth()
  const cachedThemes = readCachedRegistry()
  // Initialise from localStorage so React state matches what the blocking
  // script already applied to the DOM — avoids a flash during hydration.
  const [themePreferences, setThemePreferences] = useState<ThemePreferences>(
    () => readStoredThemePreferences(cachedThemes),
  )
  const [prefersDark, setPrefersDark] = useState(getSystemPrefersDark)
  const [keepOriginals, setKeepOriginalsState] = useState(readStoredKeepOriginals)
  const [dateTimeDisplayFormat, setDateTimeDisplayFormatState] = useState(readStoredDateTimeDisplayFormat)
  // Seed from cache so the Settings page can render custom themes immediately
  // even before the network round-trip completes.
  const [customThemes, setCustomThemes] = useState<CustomTheme[]>(cachedThemes)

  const setTheme = useCallback((name: ThemeName) => {
    setThemePreferences(previous => ({ ...previous, theme: name }))
  }, [])

  const setThemeMode = useCallback((mode: ThemeMode) => {
    setThemePreferences(previous => ({ ...previous, themeMode: mode }))
  }, [])

  const setLightTheme = useCallback((name: ThemeName) => {
    setThemePreferences(previous => ({ ...previous, lightTheme: name }))
  }, [])

  const setDarkTheme = useCallback((name: ThemeName) => {
    setThemePreferences(previous => ({ ...previous, darkTheme: name }))
  }, [])

  const setKeepOriginals = useCallback((value: boolean) => {
    setKeepOriginalsState(value)
    try { localStorage.setItem(KEEP_ORIGINALS_KEY, String(value)) } catch { /* storage unavailable */ }
  }, [])

  const setDateTimeDisplayFormat = useCallback((value: string) => {
    const normalized = setStoredDateTimeDisplayFormat(value)
    setDateTimeDisplayFormatState(normalized)
  }, [])

  const refreshThemes = useCallback(async () => {
    try {
      const data = await loadCustomThemes(fetch as typeof window.fetch)
      setCustomThemes(data.themes)
      injectCustomThemesCSS(data.themes)
      cacheRegistry(data.themes)
    } catch {
      /* keep whatever we already have */
    }
  }, [])

  // Apply cached custom themes to the DOM immediately so the React tree
  // renders against the same rules the pre-paint script used.
  useEffect(() => {
    injectCustomThemesCSS(customThemes)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    const media = typeof window.matchMedia === 'function'
      ? window.matchMedia('(prefers-color-scheme: dark)')
      : null
    if (!media) return

    const handleChange = (event: MediaQueryListEvent) => setPrefersDark(event.matches)
    media.addEventListener('change', handleChange)
    return () => media.removeEventListener('change', handleChange)
  }, [])

  useEffect(() => {
    storeThemePreferences(themePreferences)
    document.documentElement.setAttribute(
      'data-theme',
      resolveEffectiveTheme(themePreferences, prefersDark),
    )
  }, [themePreferences, prefersDark])

  // Once authenticated, validate against the backend (authoritative source).
  useEffect(() => {
    if (status !== 'authenticated') return

    let cancelled = false

    void Promise.all([
      fetch('/api/settings').then(r => (r.ok ? r.json() : null)).catch(() => null),
      loadCustomThemes(fetch as typeof window.fetch).catch(() => null),
    ]).then(([settingsData, registryData]) => {
      if (cancelled) return
      if (registryData) {
        setCustomThemes(registryData.themes)
        injectCustomThemesCSS(registryData.themes)
        cacheRegistry(registryData.themes)
      }
      if (settingsData) {
        setThemePreferences({
          theme: (settingsData.theme ?? FALLBACK_THEME) as ThemeName,
          themeMode: normalizeThemeMode(settingsData.theme_mode),
          lightTheme: (settingsData.light_theme ?? DEFAULT_LIGHT_THEME) as ThemeName,
          darkTheme: (settingsData.dark_theme ?? DEFAULT_DARK_THEME) as ThemeName,
        })
        setKeepOriginalsState(prev => {
          const next = settingsData.keep_originals ?? true
          if (prev !== next) {
            try { localStorage.setItem(KEEP_ORIGINALS_KEY, String(next)) } catch { /* storage unavailable */ }
            return next
          }
          return prev
        })
        setDateTimeDisplayFormatState(prev => {
          const next = setStoredDateTimeDisplayFormat(settingsData.datetime_display_format ?? DEFAULT_DATETIME_DISPLAY_FORMAT)
          return prev === next ? prev : next
        })
      }
    })

    return () => { cancelled = true }
  }, [status])

  return (
    <ThemeContext.Provider value={{
      theme: themePreferences.theme,
      setTheme,
      themeMode: themePreferences.themeMode,
      setThemeMode,
      lightTheme: themePreferences.lightTheme,
      setLightTheme,
      darkTheme: themePreferences.darkTheme,
      setDarkTheme,
      keepOriginals,
      setKeepOriginals,
      dateTimeDisplayFormat,
      setDateTimeDisplayFormat,
      customThemes,
      refreshThemes,
    }}>
      {children}
    </ThemeContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function useTheme() {
  return useContext(ThemeContext)
}
