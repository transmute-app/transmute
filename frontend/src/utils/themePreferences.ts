import { FALLBACK_THEME, isKnownTheme, type CustomTheme } from './themeRegistry'

export type ThemeMode = 'manual' | 'system'

export interface ThemePreferences {
  theme: string
  themeMode: ThemeMode
  lightTheme: string
  darkTheme: string
}

export const THEME_MODE_STORAGE_KEY = 'transmute-theme-mode'
export const LIGHT_THEME_STORAGE_KEY = 'transmute-light-theme'
export const DARK_THEME_STORAGE_KEY = 'transmute-dark-theme'
export const DEFAULT_LIGHT_THEME = 'albedo'
export const DEFAULT_DARK_THEME = FALLBACK_THEME

export const DEFAULT_THEME_PREFERENCES: ThemePreferences = {
  theme: FALLBACK_THEME,
  themeMode: 'manual',
  lightTheme: DEFAULT_LIGHT_THEME,
  darkTheme: DEFAULT_DARK_THEME,
}

export function normalizeThemeMode(value: unknown): ThemeMode {
  return value === 'system' ? 'system' : 'manual'
}

export function resolveEffectiveTheme(
  preferences: ThemePreferences,
  prefersDark: boolean,
): string {
  if (preferences.themeMode === 'manual') return preferences.theme
  return prefersDark ? preferences.darkTheme : preferences.lightTheme
}

function readKnownTheme(
  storage: Storage,
  key: string,
  fallback: string,
  customThemes: CustomTheme[],
): string {
  const value = storage.getItem(key)
  return value && isKnownTheme(value, customThemes) ? value : fallback
}

export function readStoredThemePreferences(
  customThemes: CustomTheme[],
  storage: Storage = localStorage,
): ThemePreferences {
  try {
    return {
      theme: readKnownTheme(storage, 'transmute-theme', FALLBACK_THEME, customThemes),
      themeMode: normalizeThemeMode(storage.getItem(THEME_MODE_STORAGE_KEY)),
      lightTheme: readKnownTheme(storage, LIGHT_THEME_STORAGE_KEY, DEFAULT_LIGHT_THEME, customThemes),
      darkTheme: readKnownTheme(storage, DARK_THEME_STORAGE_KEY, DEFAULT_DARK_THEME, customThemes),
    }
  } catch {
    return { ...DEFAULT_THEME_PREFERENCES }
  }
}

export function storeThemePreferences(
  preferences: ThemePreferences,
  storage: Storage = localStorage,
): void {
  try {
    storage.setItem('transmute-theme', preferences.theme)
    storage.setItem(THEME_MODE_STORAGE_KEY, preferences.themeMode)
    storage.setItem(LIGHT_THEME_STORAGE_KEY, preferences.lightTheme)
    storage.setItem(DARK_THEME_STORAGE_KEY, preferences.darkTheme)
  } catch {
    /* storage unavailable */
  }
}
