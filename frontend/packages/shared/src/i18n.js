import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import HttpBackend from 'i18next-http-backend';
import LanguageDetector from 'i18next-browser-languagedetector';

export function initI18n() {
  i18n
    .use(HttpBackend)
    .use(LanguageDetector)
    .use(initReactI18next)
    .init({
      lng: 'ko',
      fallbackLng: 'ko',
      interpolation: {
        escapeValue: false,
      },
      backend: {
        loadPath: '/locales/{{lng}}/{{ns}}.json',
      },
    });

  return i18n;
}
