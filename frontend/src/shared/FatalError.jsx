import React from 'react';
import { LanguageProvider, useLanguage } from './i18n.jsx';
import LanguageSelect from './LanguageSelect.jsx';

function Recovery() {
  const { t } = useLanguage();
  return (
    <main className="fatal">
      <LanguageSelect />
      <h1>{t('Something interrupted this page.')}</h1>
      <p>{t('Your saved work is still available. Reload to try again.')}</p>
      <button onClick={() => window.location.reload()}>{t('Reload page')}</button>
    </main>
  );
}

// The failed application provider may have unmounted with the error boundary.
export default function FatalError() {
  return (
    <LanguageProvider>
      <Recovery />
    </LanguageProvider>
  );
}
