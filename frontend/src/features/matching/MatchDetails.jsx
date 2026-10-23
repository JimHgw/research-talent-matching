import { useLanguage } from '../../shared/i18n.jsx';
import React from 'react';
import { api } from '../../api/client.js';
import { useResource } from '../../shared/hooks.js';
import { displayDate } from '../../shared/format.js';
import { Badge, ErrorNotice, Icon, Loading, Modal } from '../../shared/ui.jsx';
import { labels } from '../../shared/profile-labels.js';
import ProfileConfirmationRequired from '../../shared/ProfileConfirmationRequired.jsx';

const matchReasons = {
  ALL_SKILLS_SUPPORTED: 'All requested skills have confirmed supporting evidence.',
  SOME_SKILLS_SUPPORTED:
    'Some requested skills have confirmed evidence; the remaining skills have insufficient evidence.',
  ALL_TAGS_SUPPORTED: 'All requested tags have confirmed supporting evidence.',
  SOME_TAGS_SUPPORTED:
    'Some requested tags have confirmed evidence; the remaining tags have insufficient evidence.',
  EXPLICIT_NEGATIVE_CLAIM: 'A requested skill has an explicit confirmed negative claim.',
  INSUFFICIENT_EVIDENCE: 'There is insufficient confirmed evidence for this requirement.',
};

export default function MatchDetails({ opportunityId, talentId, onClose, navigate, tags = [] }) {
  const { t, language } = useLanguage();
  const resource = useResource(
    () => (talentId ? api.talentMatch(opportunityId, talentId) : api.match(opportunityId)),
    [opportunityId, talentId],
    true
  );
  const result = resource.data;
  return (
    <Modal title={t('Why this match?')} onClose={onClose}>
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
              <div className="eyebrow">{t('EVIDENCE, NOT ASSUMPTIONS')}</div>
              <h3>
                {result.talent
                  ? result.talent.fields.displayName || t('Anonymous talent')
                  : result.opportunity?.content.title}
              </h3>
              <p className="muted">
                {t('Evaluated {date} · Confirmed information only', {
                  date: displayDate(result.evaluatedAt, language),
                })}
              </p>
            </div>
            <div className="score-large">
              {result.summary.score ?? '—'}
              <small>{t('coverage / 100')}</small>
            </div>
          </div>
          <div className="match-metrics">
            <span>
              <strong>
                {result.summary.unknownWeightPercent == null
                  ? t('Not available')
                  : `${result.summary.unknownWeightPercent}%`}
              </strong>{' '}
              {t('unknown evidence')}
            </span>
            <span>
              <strong>{result.summary.requiredGapCount}</strong> {t('required gaps')}
            </span>
          </div>
          <p className="help">
            {t(
              'Coverage reflects the available evidence, not the probability of being selected. Missing information is shown as Unknown.'
            )}
          </p>
          {result.talent && <VisibleTalent talent={result.talent} tags={tags} />}
          <div className="evidence-list">
            {result.requirements.map((item) => (
              <article className="evidence-row" key={item.requirement.id}>
                <div className="row-between">
                  <div>
                    <small className="eyebrow">{t(item.requirement.importance)}</small>
                    <h4>{item.requirement.label}</h4>
                  </div>
                  <Badge status={item.status} />
                </div>
                <p>
                  {language === 'en'
                    ? item.reason
                    : t(matchReasons[item.reasonCode] || item.reason)}
                </p>
                {item.evidence.length ? (
                  <div className="evidence-box">
                    <Icon name="file" size={16} />
                    <div>
                      {item.evidence.map((e, i) => (
                        <p key={i}>
                          {language === 'en' ? (
                            e.valueSummary
                          ) : (
                            <EvidenceSummary evidence={e} t={t} />
                          )}
                          <small>
                            {t(labels[e.field])}
                            {e.sourceType === 'USER_REVIEWED_DOCUMENT'
                              ? t(' · Reviewed document import')
                              : ''}
                          </small>
                        </p>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div className="no-evidence">{t('No supporting evidence available.')}</div>
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
  const { t } = useLanguage();
  const fields = talent.fields;

  function formatItem(item) {
    if (item.label) return item.label;
    if (typeof item === 'string') {
      return tags.find((tag) => tag.id === item)?.label || t('Unlabelled interest');
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

  function formatField(value, key) {
    if (key === 'disciplineGroup') return t(value);
    if (Array.isArray(value)) {
      if (value.length === 0) return t('None provided');
      return value.map(formatItem).join(' · ');
    }
    return value || t('Not provided');
  }

  return (
    <section className="shared-profile">
      <h4>{t('Shared profile')}</h4>
      {Object.keys(fields).length === 0 ? (
        <p className="muted">{t('This talent has not shared any profile fields.')}</p>
      ) : (
        Object.entries(fields).map(([key, value]) => (
          <div key={key}>
            <strong>{t(labels[key])}</strong>
            <p>{formatField(value, key)}</p>
          </div>
        ))
      )}
    </section>
  );
}

function EvidenceSummary({ evidence, t }) {
  const prefixes = [
    'Confirmed skill claim: ',
    'Explicitly reports not having skill: ',
    'Confirmed research interest: ',
  ];
  const prefix = prefixes.find((value) => evidence.valueSummary.startsWith(value));
  if (!prefix) return evidence.valueSummary;
  return (
    <>
      {t(prefix)}
      <bdi>{evidence.valueSummary.slice(prefix.length)}</bdi>
    </>
  );
}
