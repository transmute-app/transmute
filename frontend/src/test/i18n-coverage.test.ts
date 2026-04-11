import { readdirSync, readFileSync } from 'fs'
import { join, relative, dirname } from 'path'
import { fileURLToPath } from 'url'
import { describe, expect, it } from 'vitest'

const SRC_DIR = join(dirname(fileURLToPath(import.meta.url)), '..')

/** Recursively collect .tsx files, excluding tests */
function collectTsxFiles(dir: string): string[] {
  const files: string[] = []
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name)
    if (entry.isDirectory()) {
      files.push(...collectTsxFiles(full))
    } else if (entry.name.endsWith('.tsx') && !entry.name.includes('.test.')) {
      files.push(full)
    }
  }
  return files
}

/** Files that only contain context/providers/logic — no user-facing strings */
const NON_UI_FILES = new Set(['ThemeContext.tsx', 'AuthContext.tsx', 'main.tsx'])

/** UI component directories to scan */
const UI_DIRS = [join(SRC_DIR, 'pages'), join(SRC_DIR, 'components')]

const uiFiles = UI_DIRS.flatMap(dir => collectTsxFiles(dir))

/**
 * Attributes that carry user-visible text and should use {t(…)} expressions
 * instead of static string literals.
 */
const USER_FACING_ATTRS = /\b(title|placeholder|aria-label)="([^"]*)"/g

/**
 * Allowlisted attribute values that are acceptable as hardcoded strings.
 * These are proper nouns, brand names, example/sample values, or
 * technical identifiers that don't need translation.
 */
const ALLOWED_ATTR_VALUES = new Set([
  // Brand / proper nouns
  'GitHub',
  // Example / sample placeholder values (not real UI text)
  'operator',
  'Alex Operator',
  'alex@example.com',
  // Visual dot pattern for password fields
  '••••••••',
])

describe('i18n coverage', () => {
  it('all UI component files import useTranslation', () => {
    const missing: string[] = []
    for (const file of uiFiles) {
      const name = file.split('/').pop()!
      if (NON_UI_FILES.has(name)) continue
      const content = readFileSync(file, 'utf-8')
      if (!content.includes("from 'react-i18next'")) {
        missing.push(relative(SRC_DIR, file))
      }
    }
    expect(missing, `Files missing useTranslation import:\n  ${missing.join('\n  ')}`).toEqual([])
  })

  it('no hardcoded strings in user-facing JSX attributes', () => {
    const violations: string[] = []
    for (const file of uiFiles) {
      const name = file.split('/').pop()!
      if (NON_UI_FILES.has(name)) continue
      const lines = readFileSync(file, 'utf-8').split('\n')
      for (let i = 0; i < lines.length; i++) {
        for (const match of lines[i].matchAll(USER_FACING_ATTRS)) {
          const value = match[2]
          if (ALLOWED_ATTR_VALUES.has(value)) continue
          violations.push(`${relative(SRC_DIR, file)}:${i + 1}  ${match[0]}`)
        }
      }
    }
    expect(
      violations,
      `Found hardcoded user-facing attributes (should use {t(…)}):\n  ${violations.join('\n  ')}`,
    ).toEqual([])
  })

  it('no hardcoded strings in setError / setMessage calls', () => {
    const violations: string[] = []
    // Matches setError('...') or setMessage('...') with a literal string starting with an uppercase letter
    const errorPattern = /\b(setError|setMessage)\('([A-Z][^']+)'\)/g
    for (const file of uiFiles) {
      const lines = readFileSync(file, 'utf-8').split('\n')
      for (let i = 0; i < lines.length; i++) {
        for (const match of lines[i].matchAll(errorPattern)) {
          violations.push(`${relative(SRC_DIR, file)}:${i + 1}  ${match[0]}`)
        }
      }
    }
    expect(
      violations,
      `Found hardcoded error/message strings (should use t()):\n  ${violations.join('\n  ')}`,
    ).toEqual([])
  })

  it('App.tsx uses i18n for route titles', () => {
    const content = readFileSync(join(SRC_DIR, 'App.tsx'), 'utf-8')
    expect(content).toContain("from 'react-i18next'")
    // Route titles should use t() not hardcoded strings
    expect(content).not.toMatch(/<RouteTitle\s+title="[^"]*"/)
  })

  it('all translation files have the same top-level keys', () => {
    const i18nDir = join(SRC_DIR, 'i18n')
    const files = readdirSync(i18nDir).filter(f => f.endsWith('.json'))
    expect(files.length).toBeGreaterThanOrEqual(2)

    const keysByFile = new Map<string, string[]>()
    for (const file of files) {
      const data = JSON.parse(readFileSync(join(i18nDir, file), 'utf-8'))
      keysByFile.set(file, Object.keys(data).sort())
    }

    const [reference, ...rest] = [...keysByFile.entries()]
    for (const [file, keys] of rest) {
      expect(keys, `${file} top-level keys should match ${reference[0]}`).toEqual(reference[1])
    }
  })
})
