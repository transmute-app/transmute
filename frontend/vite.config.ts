/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  // Relative asset URLs so the app can be served under a runtime sub-path
  // (resolved via the <base> tag injected by the backend). See index.html.
  base: './',
  plugins: [react()],
  build: {
    outDir: 'dist',
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('react-syntax-highlighter')) {
            return 'syntax-highlighter'
          }

          if (!id.includes('node_modules')) {
            return undefined
          }

          if (id.includes('react-router-dom') || id.includes('/react-router/')) {
            return 'router'
          }

          if (id.includes('react-icons')) {
            return 'icons'
          }

          if (id.includes('react-i18next') || id.includes('i18next-browser-languagedetector') || id.includes('/i18next/')) {
            return 'i18n'
          }

          if (id.includes('/react/') || id.includes('/react-dom/') || id.includes('/scheduler/')) {
            return 'react-vendor'
          }

          return 'vendor'
        },
      },
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
  },
})
