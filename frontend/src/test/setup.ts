import '@testing-library/jest-dom/vitest'
import '../i18n'
import { afterEach } from 'vitest'
import { cleanup } from '@testing-library/react'

afterEach(() => {
  cleanup()
})
