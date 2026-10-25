import React from 'react';
import { useLanguage } from '../../shared/i18n.jsx';
import { dateTimeZone } from '../../shared/search.js';
import { validSourceUrl } from './metadata.js';

export default function OpportunityMetadata({ content }) {
  const { t, language } = useLanguage();
  const deadline = content.deadlineAt && new Date(content.deadlineAt);
  return (
    <div className="opportunity-metadata">
      {deadline && !Number.isNaN(deadline.getTime()) && (
        <p>
          {t('Deadline')}:{' '}
          <time dateTime={content.deadlineAt}>
            {deadline.toLocaleString(language, { timeZoneName: 'short' })}
          </time>{' '}
          ({dateTimeZone()})
        </p>
      )}
      {content.sourceUrl && validSourceUrl(content.sourceUrl) && (
        <p>
          <a href={content.sourceUrl} target="_blank" rel="noopener noreferrer">
            {t('Opportunity source (opens in a new tab)')}
          </a>
        </p>
      )}
    </div>
  );
}
