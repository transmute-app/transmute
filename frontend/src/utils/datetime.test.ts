import { beforeEach, describe, expect, it } from 'vitest'
import {
  DATETIME_DISPLAY_FORMAT_STORAGE_KEY,
  DEFAULT_DATETIME_DISPLAY_FORMAT,
  formatUtcDate,
  formatUtcTimestamp,
  isValidDateTimeDisplayFormat,
  normalizeDateTimeDisplayFormat,
  parseUtcTimestamp,
} from './datetime'

beforeEach(() => {
  const store = new Map<string, string>()
  const localStorageMock = {
    getItem: (key: string) => store.get(key) ?? null,
    setItem: (key: string, value: string) => {
      store.set(key, value)
    },
    removeItem: (key: string) => {
      store.delete(key)
    },
    clear: () => {
      store.clear()
    },
  }

  Object.defineProperty(globalThis, 'localStorage', {
    configurable: true,
    value: localStorageMock,
  })
})

describe('parseUtcTimestamp', () => {
  it('treats backend timestamps without a timezone as UTC', () => {
    expect(parseUtcTimestamp('2026-03-20 12:00:00')?.toISOString()).toBe('2026-03-20T12:00:00.000Z')
    expect(parseUtcTimestamp('2026-03-20T12:00:00')?.toISOString()).toBe('2026-03-20T12:00:00.000Z')
  })

  it('preserves timestamps that already include a timezone', () => {
    expect(parseUtcTimestamp('2026-03-20T12:00:00Z')?.toISOString()).toBe('2026-03-20T12:00:00.000Z')
    expect(parseUtcTimestamp('2026-03-20T08:00:00-04:00')?.toISOString()).toBe('2026-03-20T12:00:00.000Z')
  })

  it('returns null for missing or invalid values', () => {
    expect(parseUtcTimestamp(undefined)).toBeNull()
    expect(parseUtcTimestamp('')).toBeNull()
    expect(parseUtcTimestamp('not-a-date')).toBeNull()
  })
})

describe('datetime formatting helpers', () => {
  it('formats timestamps using the parsed UTC value', () => {
    const value = '2026-03-20 12:00:00'
    const parsed = parseUtcTimestamp(value)

    expect(formatUtcTimestamp(value, { hour: '2-digit', minute: '2-digit' })).toBe(
      parsed?.toLocaleString(undefined, { hour: '2-digit', minute: '2-digit' }),
    )
    expect(formatUtcDate(value)).toBe(parsed?.toLocaleDateString())
  })

  it('formats timestamps with a custom stored pattern', () => {
    window.localStorage.setItem(DATETIME_DISPLAY_FORMAT_STORAGE_KEY, 'DD/MM/YYYY - HH:mm:ss')

    const parsed = parseUtcTimestamp('2026-03-20T12:34:56Z')!
    const expected = `${String(parsed.getDate()).padStart(2, '0')}/${String(parsed.getMonth() + 1).padStart(2, '0')}/${parsed.getFullYear()} - ${String(parsed.getHours()).padStart(2, '0')}:${String(parsed.getMinutes()).padStart(2, '0')}:${String(parsed.getSeconds()).padStart(2, '0')}`

    expect(formatUtcTimestamp('2026-03-20T12:34:56Z', undefined, 'en-US')).toBe(expected)
  })

  it('accepts locale or supported custom patterns', () => {
    expect(normalizeDateTimeDisplayFormat(' locale ')).toBe(DEFAULT_DATETIME_DISPLAY_FORMAT)
    expect(normalizeDateTimeDisplayFormat('DD/MM/YYYY - HH:mm:ss')).toBe('DD/MM/YYYY - HH:mm:ss')
    expect(isValidDateTimeDisplayFormat('DD MMM YYYY, hh:mm:ss A')).toBe(true)
    expect(isValidDateTimeDisplayFormat('DD/MM/YYYY test')).toBe(false)
  })
})