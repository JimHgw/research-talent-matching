import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';
import { languageCatalog, languageDefinition, supportsLanguage } from './locales/index.js';

export const languageStorageKey = 'banana.language';
export const languages = Object.fromEntries(
  Object.entries(languageCatalog).map(([key, value]) => [key, value.label])
);

const templateCache = new WeakMap();

function templates(messages) {
  if (templateCache.has(messages)) return templateCache.get(messages);
  const compiled = Object.entries(messages)
    .filter(([key, value]) => key.includes('{') && typeof value === 'string')
    .map(([key, value]) => {
      const names = [];
      const pattern = key
        .split(/(\{\w+\})/)
        .map((part) => {
          if (/^\{\w+\}$/.test(part)) {
            names.push(part.slice(1, -1));
            return '([\\s\\S]*?)';
          }
          return part.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        })
        .join('');
      return { pattern: new RegExp(`^${pattern}$`), names, value };
    });
  templateCache.set(messages, compiled);
  return compiled;
}

export function translate(language, message, values = {}) {
  if (typeof message !== 'string') return message;
  const messages = languageDefinition(language).messages;
  const translated = Object.hasOwn(messages, message) ? messages[message] : undefined;
  let template = typeof translated === 'string' ? translated : message;
  // Server diagnostics and saved notifications still use the English API contract.
  // Only known system templates are localized; captured source text stays verbatim.
  if (translated === undefined && language !== 'en' && !Object.keys(values).length) {
    for (const entry of templates(messages)) {
      const match = entry.pattern.exec(message);
      if (!match) continue;
      template = entry.value;
      values = Object.fromEntries(entry.names.map((name, index) => [name, match[index + 1]]));
      break;
    }
  }
  return template.replace(/\{(\w+)\}/g, (token, name) =>
    Object.hasOwn(values, name) ? String(values[name]) : token
  );
}

export function translateError(language, error) {
  const messages = languageDefinition(language).messages;
  const errors = messages.errors || {};
  const message = error.message || String(error);
  const translated = translate(language, message, error.values);
  if (translated !== message) return translated;
  return (Object.hasOwn(errors, error.code) && errors[error.code]) || translated;
}

export function translateDiagnostic(language, message) {
  // Extraction combines several diagnostics using semicolons. Split only at
  // known diagnostic starts so punctuation inside quoted source remains intact.
  return message
    .split(
      /; (?=(?:More |No |Missing |Additional |Could |Unrecognised |Learning |Negative |Conflicting |Review |Programme |A course |A programme |Supporting |Interest |Resume |Output ))/
    )
    .map((part) => translate(language, part))
    .join(' · ');
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
    document.title = translate(language, 'Banana · Research, connected.');
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
