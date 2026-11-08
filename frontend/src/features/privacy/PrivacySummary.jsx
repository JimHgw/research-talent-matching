import React from 'react';
import { useLanguage } from '../../shared/i18n.jsx';
import { labels } from '../../shared/profile-labels.js';

export default function PrivacySummary({ value }) {
  const { t } = useLanguage();
  return (
    <div>
      <p>
        {t('Allow teams to discover me')}: {t(value.discoverable ? 'On' : 'Off')}
      </p>
      <ul>
        {value.visibleFields.map((field) => (
          <li key={field}>{t(labels[field])}</li>
        ))}
      </ul>
    </div>
  );
}
