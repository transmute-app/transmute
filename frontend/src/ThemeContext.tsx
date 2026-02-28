import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react'

export type ThemeName = 'rubedo' | 'citrinitas' | 'viriditas' | 'nigredo' | 'albedo'

interface ThemeContextValue {
  theme: ThemeName
  setTheme: (theme: ThemeName) => void
}

const ThemeContext = createContext<ThemeContextValue>({
  theme: 'rubedo',
  setTheme: () => {},
})

const STORAGE_KEY = 'transmute-theme'

function applyThemeToDom(name: ThemeName) {
  document.documentElement.setAttribute('data-theme', name)
  try { localStorage.setItem(STORAGE_KEY, name) } catch (_) {}
}

const VALID_THEMES = new Set<ThemeName>(['rubedo', 'citrinitas', 'viriditas', 'nigredo', 'albedo'])

function readStoredTheme(): ThemeName {
  try {
    const t = localStorage.getItem(STORAGE_KEY) as ThemeName | null
    if (t && VALID_THEMES.has(t)) return t
  } catch (_) {}
  return 'rubedo'
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  // Initialise from localStorage so React state matches what the blocking
  // script already applied to the DOM — avoids a redundant re-render.
  const [theme, setThemeState] = useState<ThemeName>(readStoredTheme)

  const setTheme = useCallback((name: ThemeName) => {
    setThemeState(name)
    applyThemeToDom(name)
  }, [])

  // On mount, validate against the backend (authoritative source of truth).
  // If another browser changed the theme, this corrects localStorage too.
  useEffect(() => {
    fetch('/api/settings')
      .then(r => (r.ok ? r.json() : null))
      .then(data => {
        const name = (data?.theme ?? 'rubedo') as ThemeName
        setTheme(name)
      })
      .catch(() => {/* keep whatever localStorage had */})
  }, [setTheme])

  return (
    <ThemeContext.Provider value={{ theme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  )
}

export function useTheme() {
  return useContext(ThemeContext)
}
