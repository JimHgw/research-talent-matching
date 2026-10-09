import React, { useEffect, useState } from 'react';
import { api } from '../../api/client.js';
import { useResource } from '../../shared/hooks.js';
import {
  Button,
  Empty,
  ErrorNotice,
  Field,
  Icon,
  Loading,
  Notice,
  Pager,
} from '../../shared/ui.jsx';
import MatchDetails from './MatchDetails.jsx';

async function loadPublishedOpportunities() {
  const firstPage = await api.opportunities('mine');
  let opportunities = firstPage.items;
  const pageCount = Math.ceil(firstPage.total / firstPage.pageSize);

  for (let page = 2; page <= pageCount; page++) {
    const nextPage = await api.opportunities('mine', page);
    opportunities = opportunities.concat(nextPage.items);
  }

  return opportunities.filter((opportunity) => opportunity.status === 'PUBLISHED');
}

function TalentResults({ opportunityId }) {
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState(null);
  const resource = useResource(() => api.talents(opportunityId, page), [opportunityId, page], true);
  useEffect(() => {
    setPage(1);
    setSelected(null);
  }, [opportunityId]);
  return (
    <>
      {resource.loading ? (
        <Loading />
      ) : resource.error ? (
        <ErrorNotice error={resource.error} retry={resource.refresh} />
      ) : !resource.data.items.length ? (
        <Empty icon="user" title="No discoverable talent yet">
          Talent appears here after confirming their profile and choosing to be discovered.
        </Empty>
      ) : (
        <div className="talent-grid">
          {resource.data.items.map((item) => (
            <article className="panel talent-card" key={item.talent.talentId}>
              <div className="row-between">
                <span className="avatar large">
                  {(item.talent.fields.displayName || '?')
                    .split(' ')
                    .map((x) => x[0])
                    .join('')
                    .slice(0, 2)}
                </span>
                <span className="score-chip">
                  {item.summary.score ?? '—'}
                  <small>/100</small>
                </span>
              </div>
              <h3>{item.talent.fields.displayName || 'Anonymous talent'}</h3>
              <p className="muted">
                {item.talent.fields.education?.[0]?.qualification || 'Shared research profile'}
                {item.talent.fields.education?.[0]?.institution
                  ? ` · ${item.talent.fields.education[0].institution}`
                  : ''}
              </p>
              <div className="tag-row">
                {item.talent.fields.skills
                  ?.filter((s) => s.claim === 'HAS')
                  .slice(0, 4)
                  .map((s) => (
                    <span key={s.tagId}>{s.tagId.replace('skill_', '').replaceAll('_', ' ')}</span>
                  ))}
              </div>
              <p className="help">
                {item.summary.unknownWeightPercent == null
                  ? 'Not available'
                  : `${item.summary.unknownWeightPercent}%`}{' '}
                unknown evidence · {item.summary.requiredGapCount} required gaps
              </p>
              <div className="card-bottom">
                <small className="muted">#{item.rank} match</small>
                <Button variant="text" onClick={() => setSelected(item.talent.talentId)}>
                  View evidence
                  <Icon name="arrow" size={16} />
                </Button>
              </div>
            </article>
          ))}
        </div>
      )}
      <Pager data={resource.data} onPage={setPage} />
      {selected && (
        <MatchDetails
          opportunityId={opportunityId}
          talentId={selected}
          onClose={() => setSelected(null)}
        />
      )}
    </>
  );
}
export default function TalentPage({ initialOpportunity, navigate }) {
  const resource = useResource(loadPublishedOpportunities, [], true);
  const [selected, setSelected] = useState(initialOpportunity || '');
  useEffect(() => {
    if (
      resource.data?.length &&
      !resource.data.some((opportunity) => opportunity.id === selected)
    ) {
      setSelected(resource.data[0].id);
    }
  }, [resource.data, selected]);
  return (
    <>
      <div className="section-title">
        <div>
          <h2>Find people for your next idea</h2>
          <p>Confirmed profiles, shared with consent. Every match has an explanation.</p>
        </div>
      </div>
      <Notice>
        Scores and evidence use only the fields each talent has chosen to share. A low score can
        mean limited shared information.
      </Notice>
      {resource.loading ? (
        <Loading />
      ) : resource.error ? (
        <ErrorNotice error={resource.error} retry={resource.refresh} />
      ) : !resource.data.length ? (
        <Empty
          icon="briefcase"
          title="Publish an opportunity first"
          action={<Button onClick={() => navigate('opportunities')}>Manage opportunities</Button>}
        >
          Talent discovery is available for your published opportunities.
        </Empty>
      ) : (
        <>
          <div className="opportunity-select">
            <Field label="Match talent to this opportunity">
              <select value={selected} onChange={(e) => setSelected(e.target.value)}>
                {resource.data.map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.content.title}
                  </option>
                ))}
              </select>
            </Field>
          </div>
          {selected && <TalentResults key={selected} opportunityId={selected} />}
        </>
      )}
    </>
  );
}
