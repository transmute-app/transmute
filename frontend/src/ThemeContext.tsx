import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react'
import { useAuth } from './AuthContext'
import { authFetch as fetch } from './utils/api'
import {
  BUILTIN_THEMES,
  FALLBACK_THEME,
  THEME_STORAGE_KEY,
  cacheRegistry,
  injectCustomThemesCSS,
  isKnownTheme,
  loadCustomThemes,
  readCachedRegistry,
  type CustomTheme,
} from './utils/themeRegistry'

/**
 * Theme name is now an arbitrary string — built-in keys plus any custom
 * theme registered in the database. The runtime registry decides what is
 * valid; this used to be a discriminated union pinned to a fixed list.
 */
export type ThemeName = string

interface ThemeContextValue {
  theme: ThemeName
  setTheme: (theme: ThemeName) => void
  keepOriginals: boolean
  setKeepOriginals: (value: boolean) => void
  customThemes: CustomTheme[]
  /** Re-fetch the registry from the backend and re-inject the CSS rules. */
  refreshThemes: () => Promise<void>
}

const ThemeContext = createContext<ThemeContextValue>({
  theme: FALLBACK_THEME,
  setTheme: () => {},
  keepOriginals: true,
  setKeepOriginals: () => {},
  customThemes: [],
  refreshThemes: async () => {},
})

const KEEP_ORIGINALS_KEY = 'transmute-keep-originals'

function applyThemeToDom(name: ThemeName) {
  document.documentElement.setAttribute('data-theme', name)
  try { localStorage.setItem(THEME_STORAGE_KEY, name) } catch { /* storage unavailable */ }
}

function readStoredTheme(): ThemeName {
  try {
    const t = localStorage.getItem(THEME_STORAGE_KEY)
    if (!t) return FALLBACK_THEME
    // Accept any known built-in or anything that the cached registry knows
    // about. If the registry hasn't been hydrated yet, the pre-paint
    // script already injected the matching <style> rules so it's safe to
    // trust the stored value here.
    const cached = readCachedRegistry()
    if (isKnownTheme(t, cached) || BUILTIN_THEMES.some(b => b.key === t)) return t
    return FALLBACK_THEME
  } catch { /* storage unavailable */ }
  return FALLBACK_THEME
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
  // Initialise from localStorage so React state matches what the blocking
  // script already applied to the DOM — avoids a redundant re-render.
  const [theme, setThemeState] = useState<ThemeName>(readStoredTheme)
  const [keepOriginals, setKeepOriginalsState] = useState(readStoredKeepOriginals)
  // Seed from cache so the Settings page can render custom themes immediately
  // even before the network round-trip completes.
  const [customThemes, setCustomThemes] = useState<CustomTheme[]>(readCachedRegistry)

  const setTheme = useCallback((name: ThemeName) => {
    setThemeState(name)
    applyThemeToDom(name)
  }, [])

  const setKeepOriginals = useCallback((value: boolean) => {
    setKeepOriginalsState(value)
    try { localStorage.setItem(KEEP_ORIGINALS_KEY, String(value)) } catch { /* storage unavailable */ }
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
        const name = (settingsData.theme ?? FALLBACK_THEME) as ThemeName
        setThemeState(prev => {
          if (prev !== name) {
            applyThemeToDom(name)
            return name
          }
          return prev
        })
        setKeepOriginalsState(prev => {
          const next = settingsData.keep_originals ?? true
          if (prev !== next) {
            try { localStorage.setItem(KEEP_ORIGINALS_KEY, String(next)) } catch { /* storage unavailable */ }
            return next
          }
          return prev
        })
      }
    })

    return () => { cancelled = true }
  }, [status])

  return (
    <ThemeContext.Provider value={{ theme, setTheme, keepOriginals, setKeepOriginals, customThemes, refreshThemes }}>
      {children}
    </ThemeContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function useTheme() {
  return useContext(ThemeContext)
}
