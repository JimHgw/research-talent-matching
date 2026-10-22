import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';
import { languageCatalog, languageDefinition, supportsLanguage } from './locales/index.js';

export const languageStorageKey = 'banana.language';
export const languages = Object.fromEntries(
  Object.entries(languageCatalog).map(([key, value]) => [key, value.label])
);

export function translate(language, message, values = {}) {
  const translated = languageDefinition(language).messages[message];
  const template = typeof translated === 'string' ? translated : message;
  return template.replace(/\{(\w+)\}/g, (token, name) =>
    Object.hasOwn(values, name) ? String(values[name]) : token
  );
}

export function translateError(language, error) {
  const errors = languageDefinition(language).messages.errors || {};
  return (
    (Object.hasOwn(errors, error.code) && errors[error.code]) ||
    translate(language, error.message || String(error))
  );
}

const LanguageContext = createContext({
  language: 'en',
  direction: 'ltr',
  setLanguage: () => {},
  t: (message, values) => translate('en', message, values),
  errorMessage: (error) => translateError('en', error),
});

function savedLanguage() {
  try {
    const saved = window.localStorage.getItem(languageStorageKey);
    return supportsLanguage(saved) ? saved : 'en';
  } catch {
    return 'en';
  }
}

export function LanguageProvider({ children }) {
  const [language, updateLanguage] = useState(savedLanguage);
  useEffect(() => {
    document.documentElement.lang = language;
    document.documentElement.dir = languageDefinition(language).direction;
    try {
      window.localStorage.setItem(languageStorageKey, language);
    } catch {
      // Private browsing/storage restrictions must not prevent using the interface.
    }
  }, [language]);
  useEffect(() => {
    const sync = (event) => {
      if (event.key === null || event.key === languageStorageKey) {
        const value = event.newValue;
        if (value === null || supportsLanguage(value)) updateLanguage(value || 'en');
      }
    };
    window.addEventListener('storage', sync);
    return () => window.removeEventListener('storage', sync);
  }, []);
  const value = useMemo(
    () => ({
      language,
      direction: languageDefinition(language).direction,
      setLanguage: (next) => supportsLanguage(next) && updateLanguage(next),
      t: (message, values) => translate(language, message, values),
      errorMessage: (error) => translateError(language, error),
    }),
    [language]
  );
  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

export const useLanguage = () => useContext(LanguageContext);
