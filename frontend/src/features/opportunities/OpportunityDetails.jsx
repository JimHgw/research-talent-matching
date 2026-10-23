import React from 'react';
import { Badge } from '../../shared/ui.jsx';
import { displayDate } from '../../shared/format.js';

export function OpportunityContent({ content, tags }) {
  const labels = new Map(tags.map((tag) => [tag.id, tag.label]));
  return (
    <div className="opportunity-content">
      <h3>{content.title || 'Untitled opportunity'}</h3>
      <p className="muted">
        {content.university} · {content.disciplineGroup} · {content.discipline}
      </p>
      <h4>Research area</h4>
      <p>{content.researchArea}</p>
      <h4>Description</h4>
      <p className="opportunity-description">{content.description}</p>
      <h4>Requirements</h4>
      {!content.requirements.length && <p className="muted">No requirements yet.</p>}
      <ol className="opportunity-requirement-list">
        {content.requirements.map((row) => (
          <li key={row.id}>
            <strong>{row.label}</strong>
            <p>
              {row.importance === 'REQUIRED' ? 'Required' : 'Preferred'} ·{' '}
              {row.kind === 'SKILL' ? 'Skill' : 'Research interest'}
            </p>
            <p>{(row.skillTitles || row.tagIds.map((id) => labels.get(id) || id)).join(' + ')}</p>
          </li>
        ))}
      </ol>
    </div>
  );
}

export default function OpportunityDetails({ opportunity, tags }) {
  return (
    <article className="panel">
      <div className="opportunity-meta">
        <Badge status={opportunity.status} />
        <span className="muted">Updated {displayDate(opportunity.updatedAt)}</span>
      </div>
      <OpportunityContent content={opportunity.content} tags={tags} />
    </article>
  );
}
