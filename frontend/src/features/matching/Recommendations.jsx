import RefreshStatus from '../../shared/RefreshStatus.jsx';
import { useLanguage } from '../../shared/i18n.jsx';
import React, { useEffect, useState } from 'react';
import { api } from '../../api/client.js';
import { useResource } from '../../shared/hooks.js';
import { Button, Empty, ErrorNotice, Icon, Loading, Pager } from '../../shared/ui.jsx';
import MatchDetails from './MatchDetails.jsx';
import ProfileConfirmationRequired from '../../shared/ProfileConfirmationRequired.jsx';
import SearchFilters from '../../shared/SearchFilters.jsx';
import SemanticInterest from './SemanticInterest.jsx';

function OpportunityCard({ opportunity, summary, rank, onView, onDetails, CollectionButton }) {
  const { t } = useLanguage();
  const content = opportunity.content;
  const universityInitials = content.university
    .split(' ')
    .filter((word) => !['of', 'the'].includes(word.toLowerCase()))
    .map((word) => word[0])
    .join('')
    .slice(0, 3);
  return (
    <article className="recommendation-card">
      <div className="card-top">
        <span
          className={`university-mark ${content.disciplineGroup === 'BUSINESS' ? 'peach' : ''}`}
        >
          {universityInitials}
        </span>
        <div>
          <small>{content.university}</small>
          <span className="card-category">{t(content.disciplineGroup)}</span>
        </div>
        {summary && (
          <span
            className="score-chip"
            title={t(
              summary.semanticRequirements || summary.semanticInterest
                ? 'Recommendation score'
                : 'Evidence coverage'
            )}
          >
            {summary.recommendationScore ?? summary.score ?? '—'}
            <small>/100</small>
          </span>
        )}
      </div>
      <h3>{content.title}</h3>
      <p className="card-description">{content.description}</p>
      <div className="tag-row">
        <span>{content.discipline}</span>
        <span>{content.researchArea}</span>
      </div>
      {summary && <SemanticInterest summary={summary} compact />}
      {CollectionButton && <CollectionButton opportunityId={opportunity.id} />}
      <div className="card-bottom">
        <span className="muted">
          {rank
            ? t('#{rank} recommendation', { rank })
            : t('{count} requirements', { count: content.requirements.length })}
        </span>
        <Button variant="text" onClick={onView}>
          {summary ? t('Why this match?') : t('View details')}
          <Icon name="arrow" size={16} />
        </Button>
        {onDetails && (
          <Button variant="text" onClick={onDetails}>
            {t('View opportunity')}
            <Icon name="briefcase" size={16} />
          </Button>
        )}
      </div>
    </article>
  );
}

export default function Recommendations({ navigate, OpportunityDetails, CollectionButton }) {
  const { t } = useLanguage();
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState(null);
  const [details, setDetails] = useState(null);
  const [filters, setFilters] = useState({});
  const resource = useResource(
    ({ signal }) => api.recommendations(page, filters, { signal }),
    [page, filters],
    true,
    { retainData: true }
  );
  useEffect(() => {
    if (!resource.data?.items.some((item) => item.opportunity.id === selected)) setSelected(null);
    if (!resource.data?.items.some((item) => item.opportunity.id === details)) setDetails(null);
  }, [resource.data, selected, details]);
  return (
    <>
      <div className="section-title">
        <div>
          <h2>{t('Your recommended opportunities')}</h2>
          <p>{t('Ranked using your current confirmed profile.')}</p>
        </div>
        <span className="subtle-pill">
          {t('{count} opportunities', { count: resource.data?.total ?? '—' })}
        </span>
      </div>
      <SearchFilters
        onApply={(next) => {
          setPage(1);
          setSelected(null);
          setDetails(null);
          setFilters(next);
        }}
      />
      <RefreshStatus resource={resource} />
      {resource.initialLoading ? (
        <Loading />
      ) : resource.error?.code === 'PROFILE_UNCONFIRMED' ? (
        <ProfileConfirmationRequired onReview={() => navigate('profile')} />
      ) : resource.error ? (
        <ErrorNotice error={resource.error} retry={resource.refresh} />
      ) : resource.data.items.length ? (
        <div className="card-grid">
          {resource.data.items.map((item) => (
            <OpportunityCard
              key={item.opportunity.id}
              opportunity={item.opportunity}
              summary={item.summary}
              rank={item.rank}
              CollectionButton={CollectionButton}
              onView={() => setSelected(item.opportunity.id)}
              onDetails={() => setDetails(item.opportunity.id)}
            />
          ))}
        </div>
      ) : (
        <Empty
          title={
            Object.keys(filters).length
              ? t('No results match these filters.')
              : t('No opportunities just yet')
          }
        >
          {Object.keys(filters).length
            ? t('Try changing or clearing the filters.')
            : t('Published opportunities will appear here when teams add them.')}
        </Empty>
      )}
      <Pager
        data={resource.data}
        onPage={(next) => {
          setSelected(null);
          setDetails(null);
          setPage(next);
        }}
      />

      {resource.data?.items.some((item) => item.opportunity.id === selected) && (
        <MatchDetails
          opportunityId={selected}
          navigate={navigate}
          onClose={() => setSelected(null)}
        />
      )}
      {resource.data?.items.some((item) => item.opportunity.id === details) &&
        OpportunityDetails && (
          <OpportunityDetails
            opportunityId={details}
            onClose={() => setDetails(null)}
            onMatch={() => {
              setDetails(null);
              setSelected(details);
            }}
          />
        )}
    </>
  );
}
