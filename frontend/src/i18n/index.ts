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

const isTest = typeof process !== 'undefined' && process.env.NODE_ENV === 'test'

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    supportedLngs: ['en', 'az', 'de', 'es', 'pl', 'pt', 'it', 'da', 'fr', 'hi', 'cs', 'tr', 'zh-CN'],
    nonExplicitSupportedLngs: true,
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
