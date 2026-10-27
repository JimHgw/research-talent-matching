import React from 'react';
import { useLanguage } from '../../shared/i18n.jsx';

export default function SemanticInterest({ summary, compact = false }) {
  const { t } = useLanguage();
  const interest = summary.semanticInterest;
  if (!interest) return null;
  const available = interest.status === 'AVAILABLE';
  const relevance = {
    RELEVANT: t('Closely related'),
    PARTIAL: t('Partly related'),
    UNRELATED: t('Low similarity'),
  };
  return (
    <section className={`semantic-interest ${compact ? 'compact' : ''}`}>
      <div className="row-between">
        <strong>{t('Research interest similarity')}</strong>
        {available && <span>{interest.score}/100</span>}
      </div>
      <p className="help">
        {available
          ? relevance[interest.relevance]
          : interest.status === 'MISSING_EVIDENCE'
            ? t('Interest information is unavailable; ranked by evidence coverage.')
            : t('Interest similarity is unavailable; ranked by evidence coverage.')}
      </p>
      {!compact && available && (
        <>
          <p className="help">
            {t('Evidence weight {evidence}%; interest weight {interest}%.', {
              evidence: Math.round((1 - interest.weight) * 100),
              interest: Math.round(interest.weight * 100),
            })}
          </p>
          <p className="help">
            {t(
              'Interest similarity influences ranking; skills and qualifications use confirmed evidence.'
            )}
          </p>
        </>
      )}
    </section>
  );
}
