import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import LanguageDetector from 'i18next-browser-languagedetector'

import en from './en.json'
import de from './de.json'
import es from './es.json'
import pl from './pl.json'
import it from './it.json'

const isTest = typeof process !== 'undefined' && process.env.NODE_ENV === 'test'

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      en: { translation: en },
      de: { translation: de },
      es: { translation: es },
      pl: { translation: pl },
      it: { translation: it },
    },
    fallbackLng: 'en',
    interpolation: {
      escapeValue: false, // React already escapes
    },
    detection: {
      order: isTest ? ['navigator'] : ['navigator', 'localStorage'],
      caches: isTest ? [] : ['localStorage'],
      lookupLocalStorage: 'transmute-language',
    },
  })

export default i18n
