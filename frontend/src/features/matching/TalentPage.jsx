import RefreshStatus from '../../shared/RefreshStatus.jsx';
import { useDataInvalidation } from '../../shared/data-invalidation.js';
import { useLanguage } from '../../shared/i18n.jsx';
import React, { useEffect, useState } from 'react';
import { api } from '../../api/client.js';
import { requireMatchPage } from '../../api/match-contract.ts';
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
import SearchFilters from '../../shared/SearchFilters.jsx';
import SemanticInterest from './SemanticInterest.jsx';

async function loadPublishedOpportunities({ signal }) {
  const firstPage = await api.opportunities('mine', 1, {}, { signal });
  let opportunities = firstPage.items;
  const pageCount = Math.ceil(firstPage.total / firstPage.pageSize);

  for (let page = 2; page <= pageCount; page++) {
    signal.throwIfAborted();
    const nextPage = await api.opportunities('mine', page, {}, { signal });
    opportunities = opportunities.concat(nextPage.items);
  }

  return opportunities.filter(
    (opportunity) =>
      opportunity.status === 'PUBLISHED' && opportunity.availabilityStatus !== 'EXPIRED'
  );
}

function TalentResults({
  opportunityId,
  tags,
  shortlist,
  CollectionButton,
  filters,
  onFiltersChange,
  refreshVersion,
}) {
  const { t } = useLanguage();
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState(null);
  const resource = useResource(
    ({ signal }) =>
      (shortlist
        ? api.shortlist(opportunityId, page, { signal })
        : api.talents(opportunityId, page, filters, { signal })
      ).then(requireMatchPage),
    [opportunityId, page, shortlist, filters],
    true,
    { retainData: true }
  );
  useEffect(() => {
    if (refreshVersion) {
      setSelected(null);
      resource.refresh();
    }
  }, [refreshVersion, resource.refresh]);
  useDataInvalidation(resource.refresh, ['matching', 'collections', 'opportunities']);
  useEffect(() => {
    if (!resource.data?.items.some((item) => item.talent.talentId === selected)) setSelected(null);
  }, [resource.data, selected]);
  useEffect(() => {
    // Reopen team evidence from the refreshed consent boundary after returning to the page.
    // Keep the list visible, but never keep a previously opened private evidence dialog.
    const closeEvidence = () => setSelected(null);
    window.addEventListener('focus', closeEvidence);
    return () => window.removeEventListener('focus', closeEvidence);
  }, []);
  return (
    <>
      {!shortlist && (
        <SearchFilters
          talent
          initialFilters={filters}
          onApply={(next) => {
            setPage(1);
            setSelected(null);
            onFiltersChange(next);
          }}
        />
      )}
      <RefreshStatus resource={resource} />
      {resource.initialLoading ? (
        <Loading />
      ) : resource.error ? (
        <ErrorNotice error={resource.error} retry={resource.refresh} />
      ) : !resource.data.items.length ? (
        <Empty
          icon="user"
          title={
            !shortlist && Object.keys(filters).length
              ? t('No results match these filters.')
              : shortlist
                ? t('No currently discoverable shortlisted candidates')
                : page > 1
                  ? t('No talent on this page')
                  : t('No discoverable talent yet')
          }
          action={
            page > 1 ? <Button onClick={() => setPage(1)}>{t('Back to first page')}</Button> : null
          }
        >
          {t('Talent appears here after confirming their profile and choosing to be discovered.')}
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
                <span
                  className="score-chip"
                  title={t(
                    item.summary.semanticRequirements || item.summary.semanticInterest
                      ? 'Recommendation score'
                      : 'Evidence coverage'
                  )}
                >
                  {item.summary.recommendationScore ?? item.summary.score ?? '—'}
                  <small>/100</small>
                </span>
              </div>
              <h3>{item.talent.fields.displayName || t('Anonymous talent')}</h3>
              <p className="muted">
                {item.talent.fields.education?.[0]?.qualification || t('Shared research profile')}
                {item.talent.fields.education?.[0]?.institution
                  ? ` · ${item.talent.fields.education[0].institution}`
                  : ''}
              </p>
              <div className="tag-row">
                {item.talent.fields.skills?.slice(0, 4).map((s) => (
                  <span key={s.id}>{s.title}</span>
                ))}
              </div>
              <SemanticInterest summary={item.summary} compact />
              <p className="help">
                {item.summary.unknownWeightPercent == null
                  ? t('Not available')
                  : `${item.summary.unknownWeightPercent}%`}{' '}
                {t('unknown evidence')} ·{' '}
                {t('{count} required gaps', { count: item.summary.requiredGapCount })}
              </p>
              {CollectionButton && (
                <CollectionButton
                  opportunityId={opportunityId}
                  talentId={item.talent.talentId}
                  onChange={shortlist ? resource.refresh : undefined}
                />
              )}
              <div className="card-bottom">
                <small className="muted">{t('#{rank} match', { rank: item.rank })}</small>
                <Button variant="text" onClick={() => setSelected(item.talent.talentId)}>
                  {t('View evidence')}
                  <Icon name="arrow" size={16} />
                </Button>
              </div>
            </article>
          ))}
        </div>
      )}
      <Pager
        data={resource.data}
        onPage={(nextPage) => {
          setSelected(null);
          setPage(nextPage);
        }}
      />
      {resource.data?.items.some((item) => item.talent.talentId === selected) && (
        <MatchDetails
          opportunityId={opportunityId}
          talentId={selected}
          tags={tags}
          onClose={() => setSelected(null)}
        />
      )}
    </>
  );
}
export default function TalentPage({
  initialOpportunity,
  navigate,
  tags = [],
  initialShortlist = false,
  CollectionButton,
}) {
  const { t } = useLanguage();
  const resource = useResource(loadPublishedOpportunities, [], true, { retainData: true });
  useDataInvalidation(resource.refresh, ['opportunities']);
  const [refreshVersion, setRefreshVersion] = useState(0);
  const [selected, setSelected] = useState(initialOpportunity || '');
  const [shortlist, setShortlist] = useState(initialShortlist);
  const [filters, setFilters] = useState({});
  const activeOpportunity = resource.data?.some((opportunity) => opportunity.id === selected)
    ? selected
    : resource.data?.[0]?.id;
  return (
    <>
      <div className="section-title">
        <div>
          <h2>{shortlist ? t('Shortlisted Candidates') : t('Find people for your next idea')}</h2>
          <p>{t('Confirmed profiles, shared with consent. Every match has an explanation.')}</p>
        </div>
        <Button
          variant="secondary"
          disabled={resource.loading}
          onClick={() => {
            resource.refresh();
            setRefreshVersion((value) => value + 1);
          }}
        >
          {t('Refresh talent')}
        </Button>
      </div>
      <Button variant="secondary" onClick={() => setShortlist(!shortlist)}>
        {shortlist ? t('Discover talent') : t('View Shortlisted Candidates')}
      </Button>
      <Notice>
        {t(
          'Scores and evidence use only the fields each talent has chosen to share. A low score can mean limited shared information.'
        )}
      </Notice>
      <RefreshStatus resource={resource} />
      {resource.initialLoading ? (
        <Loading />
      ) : resource.error ? (
        <ErrorNotice error={resource.error} retry={resource.refresh} />
      ) : !resource.data.length ? (
        <Empty
          icon="briefcase"
          title={t('Publish an opportunity first')}
          action={
            <Button onClick={() => navigate('teamOpportunities')}>
              {t('Manage opportunities')}
            </Button>
          }
        >
          {t('Talent discovery is available for your published opportunities.')}
        </Empty>
      ) : (
        <>
          <div className="opportunity-select">
            <Field label={t('Match talent to this opportunity')}>
              <select value={activeOpportunity} onChange={(e) => setSelected(e.target.value)}>
                {resource.data.map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.content.title}
                  </option>
                ))}
              </select>
            </Field>
          </div>
          {activeOpportunity && (
            <TalentResults
              key={activeOpportunity + shortlist}
              opportunityId={activeOpportunity}
              tags={tags}
              shortlist={shortlist}
              CollectionButton={CollectionButton}
              filters={filters}
              onFiltersChange={setFilters}
              refreshVersion={refreshVersion}
            />
          )}
        </>
      )}
    </>
  );
}
