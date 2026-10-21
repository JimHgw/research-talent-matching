import React from 'react';
import { languages, useLanguage } from './i18n.jsx';
import { languageDefinition } from './locales/index.js';

export default function LanguageSelect() {
  const { language, setLanguage, t } = useLanguage();
  return (
    <label className="language-select">
      <span>{t('Language')}</span>
      <select value={language} onChange={(event) => setLanguage(event.target.value)}>
        {Object.entries(languages).map(([key, label]) => (
          <option key={key} value={key} lang={key} dir={languageDefinition(key).direction}>
            {label}
          </option>
        ))}
      </select>
    </label>
  );
}
