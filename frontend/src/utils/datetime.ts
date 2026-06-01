const UTC_TIMESTAMP_WITHOUT_ZONE = /^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d+)?$/
const SUPPORTED_DATETIME_DISPLAY_FORMAT_TOKENS = ['YYYY', 'MMM', 'MM', 'DD', 'HH', 'hh', 'mm', 'ss', 'A'] as const

export const DEFAULT_DATETIME_DISPLAY_FORMAT = 'locale'
export const DATETIME_DISPLAY_FORMAT_STORAGE_KEY = 'transmute-datetime-display-format'

type SupportedDateTimeToken = typeof SUPPORTED_DATETIME_DISPLAY_FORMAT_TOKENS[number]

function getBrowserLocalStorage(): Storage | null {
  if (typeof window === 'undefined') return null

  try {
    return window.localStorage
  } catch {
    return null
  }
}

function pad(value: number): string {
  return String(value).padStart(2, '0')
}

function formatWithPattern(date: Date, pattern: string, locales?: Intl.LocalesArgument): string {
  const monthShort = new Intl.DateTimeFormat(locales, { month: 'short' }).format(date)
  const hours24 = date.getHours()
  const hours12 = hours24 % 12 || 12
  const replacements: Record<SupportedDateTimeToken, string> = {
    YYYY: String(date.getFullYear()),
    MMM: monthShort,
    MM: pad(date.getMonth() + 1),
    DD: pad(date.getDate()),
    HH: pad(hours24),
    hh: pad(hours12),
    mm: pad(date.getMinutes()),
    ss: pad(date.getSeconds()),
    A: hours24 < 12 ? 'AM' : 'PM',
  }

  return pattern.replace(/YYYY|MMM|MM|DD|HH|hh|mm|ss|A/g, token => replacements[token as SupportedDateTimeToken])
}

export function formatDateTimeForDisplay(
  value: Date,
  options?: Intl.DateTimeFormatOptions,
  locales?: Intl.LocalesArgument,
  displayFormatOverride?: string,
): string {
  const displayFormat = normalizeDateTimeDisplayFormat(displayFormatOverride ?? readStoredDateTimeDisplayFormat())
  if (displayFormat === DEFAULT_DATETIME_DISPLAY_FORMAT) {
    return value.toLocaleString(locales, options)
  }

  return formatWithPattern(value, displayFormat, locales)
}

export function normalizeDateTimeDisplayFormat(value?: string | null): string {
  if (typeof value !== 'string') return DEFAULT_DATETIME_DISPLAY_FORMAT

  const normalized = value.trim()
  if (!normalized) return DEFAULT_DATETIME_DISPLAY_FORMAT
  if (normalized.toLowerCase() === DEFAULT_DATETIME_DISPLAY_FORMAT) {
    return DEFAULT_DATETIME_DISPLAY_FORMAT
  }

  let remaining = normalized
  for (const token of [...SUPPORTED_DATETIME_DISPLAY_FORMAT_TOKENS].sort((a, b) => b.length - a.length)) {
    remaining = remaining.split(token).join('')
  }

  if ([...remaining].some(ch => /[A-Za-z0-9]/.test(ch))) {
    return DEFAULT_DATETIME_DISPLAY_FORMAT
  }

  return normalized.slice(0, 64)
}

export function isValidDateTimeDisplayFormat(value?: string | null): boolean {
  if (typeof value !== 'string') return false
  const trimmed = value.trim()
  if (!trimmed || trimmed.length > 64) return false
  return normalizeDateTimeDisplayFormat(trimmed) === trimmed || trimmed.toLowerCase() === DEFAULT_DATETIME_DISPLAY_FORMAT
}

export function readStoredDateTimeDisplayFormat(): string {
  const storage = getBrowserLocalStorage()
  try {
    return normalizeDateTimeDisplayFormat(storage?.getItem(DATETIME_DISPLAY_FORMAT_STORAGE_KEY))
  } catch {
    return DEFAULT_DATETIME_DISPLAY_FORMAT
  }
}

export function setStoredDateTimeDisplayFormat(value: string): string {
  const normalized = normalizeDateTimeDisplayFormat(value)
  const storage = getBrowserLocalStorage()
  try {
    storage?.setItem(DATETIME_DISPLAY_FORMAT_STORAGE_KEY, normalized)
  } catch {
    // ignore storage failures and still return the normalized value
  }
  return normalized
}

function normalizeUtcTimestamp(value: string): string {
  const trimmed = value.trim()
  if (!trimmed) return trimmed
  if (UTC_TIMESTAMP_WITHOUT_ZONE.test(trimmed)) {
    return `${trimmed.replace(' ', 'T')}Z`
  }
  return trimmed
}

export function parseUtcTimestamp(value?: string | null): Date | null {
  if (!value) return null

  const parsed = new Date(normalizeUtcTimestamp(value))
  return Number.isNaN(parsed.getTime()) ? null : parsed
}

export function formatUtcTimestamp(
  value: string | null | undefined,
  options?: Intl.DateTimeFormatOptions,
  locales?: Intl.LocalesArgument,
  displayFormatOverride?: string,
): string {
  const parsed = parseUtcTimestamp(value)
  if (!parsed) return ''

  return formatDateTimeForDisplay(parsed, options, locales, displayFormatOverride)
}

export function formatUtcDate(
  value: string | null | undefined,
  options?: Intl.DateTimeFormatOptions,
  locales?: Intl.LocalesArgument,
  displayFormatOverride?: string,
): string {
  const parsed = parseUtcTimestamp(value)
  if (!parsed) return ''

  const displayFormat = normalizeDateTimeDisplayFormat(displayFormatOverride ?? readStoredDateTimeDisplayFormat())
  if (displayFormat === DEFAULT_DATETIME_DISPLAY_FORMAT) {
    return parsed.toLocaleDateString(locales, options)
  }

  return formatWithPattern(parsed, displayFormat, locales)
}