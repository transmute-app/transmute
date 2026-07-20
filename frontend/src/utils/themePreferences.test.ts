import { describe, expect, it } from 'vitest'
import {
  DEFAULT_THEME_PREFERENCES,
  normalizeThemeMode,
  readStoredThemePreferences,
  resolveEffectiveTheme,
  storeThemePreferences,
  type ThemePreferences,
} from './themePreferences'

describe('theme preferences', () => {
  it('keeps legacy users in manual mode', () => {
    localStorage.setItem('transmute-theme', 'viriditas')

    expect(readStoredThemePreferences([])).toEqual({
      ...DEFAULT_THEME_PREFERENCES,
      theme: 'viriditas',
    })
  })

  it('resolves the configured system light and dark themes', () => {
    const preferences: ThemePreferences = {
      theme: 'viriditas',
      themeMode: 'system',
      lightTheme: 'caelum',
      darkTheme: 'nigredo',
    }

    expect(resolveEffectiveTheme(preferences, false)).toBe('caelum')
    expect(resolveEffectiveTheme(preferences, true)).toBe('nigredo')
  })

  it('persists and restores all theme selections', () => {
    const preferences: ThemePreferences = {
      theme: 'citrinitas',
      themeMode: 'system',
      lightTheme: 'aurora',
      darkTheme: 'rubedo',
    }

    storeThemePreferences(preferences)

    expect(readStoredThemePreferences([])).toEqual(preferences)
  })

  it('normalizes unknown modes to manual', () => {
    expect(normalizeThemeMode('system')).toBe('system')
    expect(normalizeThemeMode('automatic')).toBe('manual')
    expect(normalizeThemeMode(null)).toBe('manual')
  })
})
