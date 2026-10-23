import { useLanguage } from '../../shared/i18n.jsx';
import React from 'react';
import { Badge } from '../../shared/ui.jsx';
import { displayDate } from '../../shared/format.js';

export function OpportunityContent({ content, tags }) {
  const { t } = useLanguage();
  const labels = new Map(tags.map((tag) => [tag.id, tag.label]));
  return (
    <div className="opportunity-content">
      <h3>{content.title || t('Untitled opportunity')}</h3>
      <p className="muted">
        {content.university} · {t(content.disciplineGroup)} · {content.discipline}
      </p>
      <h4>{t('Research area')}</h4>
      <p>{content.researchArea}</p>
      <h4>{t('Description')}</h4>
      <p className="opportunity-description">{content.description}</p>
      <h4>{t('Requirements')}</h4>
      {!content.requirements.length && <p className="muted">{t('No requirements yet.')}</p>}
      <ol className="opportunity-requirement-list">
        {content.requirements.map((row) => (
          <li key={row.id}>
            <strong>{row.label}</strong>
            <p>
              {row.importance === 'REQUIRED' ? t('Required') : t('Preferred')} ·{' '}
              {row.kind === 'SKILL' ? t('Skill') : t('Research interest')}
            </p>
            <p>{row.tagIds.map((id) => labels.get(id) || id).join(' + ')}</p>
          </li>
        ))}
      </ol>
    </div>
  );
}

export default function OpportunityDetails({ opportunity, tags }) {
  const { t, language } = useLanguage();
  return (
    <article className="panel">
      <div className="opportunity-meta">
        <Badge status={opportunity.status} />
        <span className="muted">
          {t('Updated {date}', { date: displayDate(opportunity.updatedAt, language) })}
        </span>
      </div>
      <OpportunityContent content={opportunity.content} tags={tags} />
    </article>
  );
}
