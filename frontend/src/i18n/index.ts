import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import LanguageDetector from 'i18next-browser-languagedetector'

import en from './en.json'
import az from './az.json'
import de from './de.json'
import es from './es.json'
import pl from './pl.json'
import pt from './pt.json'
import it from './it.json'
import da from './da.json'
import fr from './fr.json'
import hi from './hi.json'
import cs from './cs.json'
import tr from './tr.json'
import zhCN from './zh-CN.json'
import sl from './sl.json'

export const SUPPORTED_LANGUAGES = ['en', 'az', 'de', 'es', 'pl', 'pt', 'it', 'da', 'fr', 'hi', 'cs', 'tr', 'zh-CN', 'sl'] as const
export const LANGUAGE_STORAGE_KEY = 'transmute-language'
const USER_LANGUAGE_PREFERENCE_KEY = 'transmute-language-user-selected'

const isTest = typeof process !== 'undefined' && process.env.NODE_ENV === 'test'

export function getStoredLanguagePreference(): string | null {
  if (typeof window === 'undefined') {
    return null
  }

  return window.localStorage.getItem(USER_LANGUAGE_PREFERENCE_KEY)
}

export function setStoredLanguagePreference(language: string) {
  if (typeof window === 'undefined') {
    return
  }

  window.localStorage.setItem(USER_LANGUAGE_PREFERENCE_KEY, language)
}

export function clearStoredLanguagePreference() {
  if (typeof window === 'undefined') {
    return
  }

  window.localStorage.removeItem(USER_LANGUAGE_PREFERENCE_KEY)
  window.localStorage.removeItem(LANGUAGE_STORAGE_KEY)
}

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    supportedLngs: [...SUPPORTED_LANGUAGES],
    resources: {
      en: { translation: en },
      az: { translation: az },
      de: { translation: de },
      es: { translation: es },
      pl: { translation: pl },
      pt: { translation: pt },
      it: { translation: it },
      da: { translation: da },
      fr: { translation: fr },
      hi: { translation: hi },
      cs: { translation: cs },
      tr: { translation: tr },
      'zh-CN': { translation: zhCN },
      sl: { translation: sl },
    },
    fallbackLng: 'en',
    interpolation: {
      escapeValue: false, // React already escapes
    },
    detection: {
      order: isTest ? ['navigator'] : ['localStorage', 'navigator'],
      // Never auto-cache: only an explicit user selection is persisted (see
      // setStoredLanguagePreference). This keeps "Browser Locale" mode following
      // the live navigator locale on every reload instead of a stale cached value.
      caches: [],
      lookupLocalStorage: USER_LANGUAGE_PREFERENCE_KEY,
    },
  })

export default i18n
