import '@testing-library/jest-dom/vitest'
import { afterEach } from 'vitest'
import { cleanup } from '@testing-library/react'

function createStorageMock(): Storage {
  const store = new Map<string, string>()

  return {
    get length() {
      return store.size
    },
    clear() {
      store.clear()
    },
    getItem(key: string) {
      return store.get(key) ?? null
    },
    key(index: number) {
      return Array.from(store.keys())[index] ?? null
    },
    removeItem(key: string) {
      store.delete(key)
    },
    setItem(key: string, value: string) {
      store.set(key, String(value))
    },
  }
}

const localStorageMock = createStorageMock()
const sessionStorageMock = createStorageMock()

Object.defineProperty(window, 'localStorage', {
  configurable: true,
  value: localStorageMock,
})

Object.defineProperty(window, 'sessionStorage', {
  configurable: true,
  value: sessionStorageMock,
})

Object.defineProperty(globalThis, 'localStorage', {
  configurable: true,
  value: localStorageMock,
})

Object.defineProperty(globalThis, 'sessionStorage', {
  configurable: true,
  value: sessionStorageMock,
})

import '../i18n'

afterEach(() => {
  localStorageMock.clear()
  sessionStorageMock.clear()
  cleanup()
})
