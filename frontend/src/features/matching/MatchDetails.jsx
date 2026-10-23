import React from 'react';
import { api } from '../../api/client.js';
import { useResource } from '../../shared/hooks.js';
import { displayDate } from '../../shared/format.js';
import { Badge, ErrorNotice, Icon, Loading, Modal } from '../../shared/ui.jsx';
import { labels } from '../../shared/profile-labels.js';
import ProfileConfirmationRequired from '../../shared/ProfileConfirmationRequired.jsx';

export default function MatchDetails({ opportunityId, talentId, onClose, navigate, tags = [] }) {
  const resource = useResource(
    () => (talentId ? api.talentMatch(opportunityId, talentId) : api.match(opportunityId)),
    [opportunityId, talentId],
    true
  );
  const result = resource.data;
  return (
    <Modal title="Why this match?" onClose={onClose}>
      {resource.loading ? (
        <Loading />
      ) : !talentId && resource.error?.code === 'PROFILE_UNCONFIRMED' ? (
        <ProfileConfirmationRequired
          onReview={
            navigate &&
            (() => {
              onClose();
              navigate('profile');
            })
          }
        />
      ) : resource.error ? (
        <ErrorNotice error={resource.error} retry={resource.refresh} />
      ) : (
        <>
          <div className="match-intro">
            <div>
              <div className="eyebrow">EVIDENCE, NOT ASSUMPTIONS</div>
              <h3>
                {result.talent
                  ? result.talent.fields.displayName || 'Anonymous talent'
                  : result.opportunity?.content.title}
              </h3>
              <p className="muted">
                Evaluated {displayDate(result.evaluatedAt)} · Confirmed information only
              </p>
            </div>
            <div className="score-large">
              {result.summary.score ?? '—'}
              <small>coverage / 100</small>
            </div>
          </div>
          <div className="match-metrics">
            <span>
              <strong>
                {result.summary.unknownWeightPercent == null
                  ? 'Not available'
                  : `${result.summary.unknownWeightPercent}%`}
              </strong>{' '}
              unknown evidence
            </span>
            <span>
              <strong>{result.summary.requiredGapCount}</strong> required gaps
            </span>
          </div>
          <p className="help">
            Coverage reflects the available evidence, not the probability of being selected. Missing
            information is shown as Unknown.
          </p>
          {result.talent && <VisibleTalent talent={result.talent} tags={tags} />}
          <div className="evidence-list">
            {result.requirements.map((item) => (
              <article className="evidence-row" key={item.requirement.id}>
                <div className="row-between">
                  <div>
                    <small className="eyebrow">{item.requirement.importance}</small>
                    <h4>{item.requirement.label}</h4>
                  </div>
                  <Badge status={item.status} />
                </div>
                <p>{item.reason}</p>
                {item.evidence.length ? (
                  <div className="evidence-box">
                    <Icon name="file" size={16} />
                    <div>
                      {item.evidence.map((e, i) => (
                        <p key={i}>
                          {e.valueSummary}
                          <small>
                            {labels[e.field]}
                            {e.sourceType === 'USER_REVIEWED_DOCUMENT'
                              ? ' · Reviewed document import'
                              : ''}
                          </small>
                        </p>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div className="no-evidence">No supporting evidence available.</div>
                )}
              </article>
            ))}
          </div>
          <div className="legend">
            {['MATCHED', 'PARTIAL', 'GAP', 'UNKNOWN'].map((s) => (
              <Badge key={s} status={s} />
            ))}
          </div>
        </>
      )}
    </Modal>
  );
}
function VisibleTalent({ talent, tags }) {
  const fields = talent.fields;

  function formatItem(item) {
    if (item.label) return item.label;
    if (typeof item === 'string') {
      return tags.find((tag) => tag.id === item)?.label || 'Unlabelled interest';
    }
    if (item.institution) {
      return `${item.qualification}, ${item.institution}`;
    }
    let text = `${item.title || item.name}`;
    if (item.evidenceText) {
      text += ` — ${item.evidenceText}`;
    }
    if (item.description) {
      text += ` — ${item.description}`;
    }
    return text;
  }

  function formatField(value) {
    if (Array.isArray(value)) {
      if (value.length === 0) return 'None provided';
      return value.map(formatItem).join(' · ');
    }
    return value || 'Not provided';
  }

  return (
    <section className="shared-profile">
      <h4>Shared profile</h4>
      {Object.keys(fields).length === 0 ? (
        <p className="muted">This talent has not shared any profile fields.</p>
      ) : (
        Object.entries(fields).map(([key, value]) => (
          <div key={key}>
            <strong>{labels[key]}</strong>
            <p>{formatField(value)}</p>
          </div>
        ))
      )}
    </section>
  );
}
