import React from 'react';
import { useLanguage } from '../../shared/i18n.jsx';
import { labels } from '../../shared/profile-labels.js';

const methods = {
  EXACT: 'Exact confirmed match',
  SEMANTIC: 'Semantic relevance',
  STRUCTURED: 'Structured evidence score',
  EXPLICIT_GAP: 'Explicitly reported gap',
  MISSING_EVIDENCE: 'No available information for this requirement',
  UNAVAILABLE: 'Model unavailable; using structured evidence',
};

export default function RequirementScore({ scoring }) {
  const { t } = useLanguage();
  if (!scoring) return null;
  return (
    <section className="requirement-score">
      <p>
        <strong>
          {t('Requirement score')}: {scoring.score}/100
        </strong>
        {' · '}
        {t('Weight')}: {scoring.weight}
        {' · '}
        {t('Total contribution')}: {scoring.contribution}
      </p>
      <p className="help">{t(methods[scoring.method])}</p>
      {scoring.matches.map((match, index) => (
        <p className="help" key={index}>
          {t(labels[match.field] || match.field)}: <bdi>{match.text}</bdi>
          {' → '}
          <bdi>{match.criterion}</bdi>
        </p>
      ))}
    </section>
  );
}
