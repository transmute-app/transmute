import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react'
import { useAuth } from './AuthContext'
import { authFetch as fetch } from './utils/api'

export type ThemeName = 'rubedo' | 'citrinitas' | 'viriditas' | 'nigredo' | 'albedo' | 'aurora' | 'caelum'

interface ThemeContextValue {
  theme: ThemeName
  setTheme: (theme: ThemeName) => void
  keepOriginals: boolean
  setKeepOriginals: (value: boolean) => void
}

const ThemeContext = createContext<ThemeContextValue>({
  theme: 'rubedo',
  setTheme: () => {},
  keepOriginals: true,
  setKeepOriginals: () => {},
})

const STORAGE_KEY = 'transmute-theme'
const KEEP_ORIGINALS_KEY = 'transmute-keep-originals'

function applyThemeToDom(name: ThemeName) {
  document.documentElement.setAttribute('data-theme', name)
  try { localStorage.setItem(STORAGE_KEY, name) } catch { /* storage unavailable */ }
}

const VALID_THEMES = new Set<ThemeName>(['rubedo', 'citrinitas', 'viriditas', 'nigredo', 'albedo', 'aurora', 'caelum'])

function readStoredTheme(): ThemeName {
  try {
    const t = localStorage.getItem(STORAGE_KEY) as ThemeName | null
    if (t && VALID_THEMES.has(t)) return t
  } catch { /* storage unavailable */ }
  return 'rubedo'
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

  const setTheme = useCallback((name: ThemeName) => {
    setThemeState(name)
    applyThemeToDom(name)
  }, [])

  const setKeepOriginals = useCallback((value: boolean) => {
    setKeepOriginalsState(value)
    try { localStorage.setItem(KEEP_ORIGINALS_KEY, String(value)) } catch { /* storage unavailable */ }
  }, [])

  // On mount, validate against the backend (authoritative source of truth).
  // If another browser changed the theme, this corrects localStorage too.
  useEffect(() => {
    if (status !== 'authenticated') return
    fetch('/api/settings')
      .then(r => (r.ok ? r.json() : null))
      .then(data => {
        if (!data) return
        const name = (data.theme ?? 'rubedo') as ThemeName
        // Only update state if the value actually changed to avoid re-render cascades
        setThemeState(prev => {
          if (prev !== name) {
            applyThemeToDom(name)
            return name
          }
          return prev
        })
        setKeepOriginalsState(prev => {
          const next = data.keep_originals ?? true
          if (prev !== next) {
            try { localStorage.setItem(KEEP_ORIGINALS_KEY, String(next)) } catch { /* storage unavailable */ }
            return next
          }
          return prev
        })
      })
      .catch(() => {/* keep whatever localStorage had */})
  }, [status])

  return (
    <ThemeContext.Provider value={{ theme, setTheme, keepOriginals, setKeepOriginals }}>
      {children}
    </ThemeContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function useTheme() {
  return useContext(ThemeContext)
}
