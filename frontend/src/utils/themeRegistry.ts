/*
  themeRegistry.ts
  ----------------
  Single source of truth for theme metadata on the client.

  - The built-in themes (CSS lives in src/index.css) are described here so
    the Settings UI can render swatches without parsing the stylesheet.
  - Custom themes are fetched from `GET /api/settings/themes` and injected
    into the DOM at runtime by creating a `<style>` tag whose contents are
    `[data-theme="<key>"] { --color-...: r g b; ... }` rules. Tailwind
    utility classes already resolve those CSS variables, so no rebuild is
    needed for newly registered themes.
  - The registry is cached to localStorage so the pre-paint blocking
    script in index.html can apply a custom theme before React mounts,
    avoiding a flash of the default theme.
*/

export const THEME_COLOR_TOKENS = [
  'primary',
  'primary_light',
  'primary_dark',
  'accent',
  'success',
  'success_light',
  'success_dark',
  'surface_dark',
  'surface_light',
  'text',
  'text_muted',
] as const

export type ThemeColorToken = typeof THEME_COLOR_TOKENS[number]

export type ThemeColors = Record<ThemeColorToken, string>

export interface CustomTheme {
  key: string
  name: string
  colors: ThemeColors
  created_by?: string | null
  created_at?: string | null
  updated_at?: string | null
}

export interface ThemeRegistryResponse {
  themes: CustomTheme[]
  builtins: string[]
}

/** Built-in theme metadata used by the Settings UI to render swatches. */
export interface BuiltinThemeMeta {
  key: string
  label: string
  swatch: [string, string]
}

export const BUILTIN_THEMES: BuiltinThemeMeta[] = [
  { key: 'rubedo',     label: 'Rubedo',     swatch: ['#ef4444', '#171e2f'] },
  { key: 'citrinitas', label: 'Citrinitas', swatch: ['#fbbf24', '#140d2d'] },
  { key: 'viriditas',  label: 'Viriditas',  swatch: ['#16a34a', '#000000'] },
  { key: 'nigredo',    label: 'Nigredo',    swatch: ['#3c00a4', '#000000'] },
  { key: 'albedo',     label: 'Albedo',     swatch: ['#f8fafc', '#cbd5e1'] },
  { key: 'aurora',     label: 'Aurora',     swatch: ['#ea580c', '#fffbf0'] },
  { key: 'caelum',     label: 'Caelum',     swatch: ['#0284c7', '#f0f9ff'] },
  { key: 'argentum',   label: 'Argentum',   swatch: ['#8b7aa8', '#faf7ff'] },
]

export const BUILTIN_THEME_KEYS: ReadonlySet<string> = new Set(
  BUILTIN_THEMES.map(t => t.key),
)

export const STYLE_ELEMENT_ID = 'transmute-custom-themes'
export const REGISTRY_CACHE_KEY = 'transmute-theme-registry'
export const THEME_STORAGE_KEY = 'transmute-theme'
export const FALLBACK_THEME = 'rubedo'

/** Convert "#rrggbb" (or "#rgb") to "r g b" decimal channel string. */
export function hexToRgbChannels(hex: string): string {
  if (typeof hex !== 'string') return '0 0 0'
  let v = hex.trim().toLowerCase()
  if (v.startsWith('#')) v = v.slice(1)
  if (v.length === 3) v = v.split('').map(c => c + c).join('')
  if (!/^[0-9a-f]{6}$/.test(v)) return '0 0 0'
  const r = parseInt(v.slice(0, 2), 16)
  const g = parseInt(v.slice(2, 4), 16)
  const b = parseInt(v.slice(4, 6), 16)
  return `${r} ${g} ${b}`
}

/** Convert "primary_light" → "--color-primary-light". */
export function tokenToCssVar(token: string): string {
  return `--color-${token.replace(/_/g, '-')}`
}

/** Build a single `:root[data-theme="…"] { … }` CSS block for one theme.
 *
 * NOTE: we use `:root[data-theme="…"]` rather than just `[data-theme="…"]`
 * so that the rule has specificity (0,2,0) — high enough to win against
 * the built-in `[data-theme="rubedo"], :root` rule in index.css, which
 * applies `:root` (specificity 0,1,0) as the universal fallback. Without
 * the bump, source order decides and the bundled stylesheet (loaded
 * after this <style> element) wins, leaving custom themes overridden
 * by rubedo's `:root` values.
 */
function buildThemeRule(theme: CustomTheme): string {
  const declarations = THEME_COLOR_TOKENS.map(tok => {
    const hex = theme.colors[tok]
    return `  ${tokenToCssVar(tok)}: ${hexToRgbChannels(hex)};`
  }).join('\n')
  // Escape backslashes and double quotes in the key, though the backend slug regex
  // forbids them. This keeps the selector safe even for hand-edited cache.
  const safeKey = theme.key.replace(/\\/g, '\\\\').replace(/"/g, '\\"')
  return `:root[data-theme="${safeKey}"] {\n${declarations}\n}`
}

/**
 * Inject (or replace) a single <style> element containing the CSS rules
 * for every custom theme. Idempotent — calling repeatedly is safe.
 */
export function injectCustomThemesCSS(themes: CustomTheme[]): void {
  if (typeof document === 'undefined') return
  let style = document.getElementById(STYLE_ELEMENT_ID) as HTMLStyleElement | null
  if (!style) {
    style = document.createElement('style')
    style.id = STYLE_ELEMENT_ID
    document.head.appendChild(style)
  }
  style.textContent = themes.map(buildThemeRule).join('\n\n')
}

/** Persist the registry to localStorage so the pre-paint script can use it. */
export function cacheRegistry(themes: CustomTheme[]): void {
  try {
    localStorage.setItem(REGISTRY_CACHE_KEY, JSON.stringify({ themes }))
  } catch { /* storage unavailable */ }
}

/** Read the cached registry (used both by pre-paint and React init). */
export function readCachedRegistry(): CustomTheme[] {
  try {
    const raw = localStorage.getItem(REGISTRY_CACHE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    if (parsed && Array.isArray(parsed.themes)) return parsed.themes as CustomTheme[]
  } catch { /* malformed cache */ }
  return []
}

/**
 * Fetch the latest registry from the backend. The caller is responsible
 * for handling auth — this just performs a plain fetch and lets the
 * caller pass in the authenticated fetcher.
 */
export async function loadCustomThemes(
  fetcher: typeof fetch = fetch,
): Promise<ThemeRegistryResponse> {
  const res = await fetcher('/api/settings/themes')
  if (!res.ok) {
    throw new Error(`Failed to load themes: HTTP ${res.status}`)
  }
  return res.json() as Promise<ThemeRegistryResponse>
}

/**
 * Returns true when `key` is a recognised theme — either a built-in or
 * one of the supplied custom themes.
 */
export function isKnownTheme(key: string, customThemes: CustomTheme[]): boolean {
  if (BUILTIN_THEME_KEYS.has(key)) return true
  return customThemes.some(t => t.key === key)
}
