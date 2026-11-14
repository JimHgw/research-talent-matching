import React from 'react';
import { primaryMatchScore } from '../../api/match-contract.ts';
import { useLanguage } from '../../shared/i18n.jsx';

export default function MatchScore({ summary, detail = false }) {
  const { t } = useLanguage();
  const { label, name, value } = primaryMatchScore(summary);
  if (detail) {
    return (
      <div className="score-large">
        {value ?? '—'}
        <small>{t(value === null ? name : label)}</small>
      </div>
    );
  }

  return (
    <span
      className="score-chip"
      title={t(name)}
      aria-label={`${t(name)}: ${value ?? t('Not available')}`}
    >
      {value ?? '—'}
      {value !== null && <small>/100</small>}
    </span>
  );
}
