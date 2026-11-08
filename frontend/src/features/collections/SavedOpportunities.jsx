import RefreshStatus from '../../shared/RefreshStatus.jsx';
import { useDataInvalidation } from '../../shared/data-invalidation.js';
import { useLanguage } from '../../shared/i18n.jsx';
import React, { useEffect, useState } from 'react';
import { api } from '../../api/client.js';
import { useResource } from '../../shared/hooks.js';
import { Button, Empty, ErrorNotice, Loading, Pager } from '../../shared/ui.jsx';
import CollectionButton, { collectionChanged } from './CollectionButton.jsx';

export default function SavedOpportunities({ OpportunityDetails, MatchDetails, navigate }) {
  const { t } = useLanguage();
  const [page, setPage] = useState(1);
  const [details, setDetails] = useState(null);
  const [match, setMatch] = useState(null);
  const resource = useResource(
    ({ signal }) => api.savedOpportunities(page, { signal }),
    [page],
    true,
    { retainData: true }
  );
  useEffect(() => {
    window.addEventListener(collectionChanged, resource.refresh);
    return () => window.removeEventListener(collectionChanged, resource.refresh);
  }, [resource.refresh]);
  useDataInvalidation(resource.refresh, ['matching', 'collections', 'opportunities']);
  useEffect(() => {
    if (!resource.data?.items.some((item) => item.id === details)) setDetails(null);
    if (!resource.data?.items.some((item) => item.id === match)) setMatch(null);
  }, [resource.data, details, match]);
  return (
    <>
      <div className="section-title">
        <h2>{t('My Saved Opportunities')}</h2>
        <Button disabled={resource.loading} onClick={resource.refresh}>
          {t('Refresh saved')}
        </Button>
      </div>
      <RefreshStatus resource={resource} />
      {resource.initialLoading ? (
        <Loading />
      ) : resource.error ? (
        <ErrorNotice error={resource.error} retry={resource.refresh} />
      ) : !resource.data.items.length ? (
        <Empty title={t('No saved opportunities here')}>
          {t(
            'Save opportunities from your recommendations. Only currently published opportunities appear.'
          )}
          {page > 1 && <Button onClick={() => setPage(1)}>{t('Back to first page')}</Button>}
        </Empty>
      ) : (
        <div className="card-grid">
          {resource.data.items.map((opportunity) => (
            <article className="panel" key={opportunity.id}>
              <small>{opportunity.content.university}</small>
              <h3>{opportunity.content.title}</h3>
              <p>{opportunity.content.description}</p>
              <Button onClick={() => setDetails(opportunity.id)}>{t('View opportunity')}</Button>
              <CollectionButton opportunityId={opportunity.id} />
            </article>
          ))}
        </div>
      )}
      <Pager
        data={resource.data}
        onPage={(next) => {
          setDetails(null);
          setMatch(null);
          setPage(next);
        }}
      />
      {resource.data?.items.some((item) => item.id === details) && (
        <OpportunityDetails
          opportunityId={details}
          onClose={() => setDetails(null)}
          onMatch={() => {
            setMatch(details);
            setDetails(null);
          }}
        />
      )}
      {resource.data?.items.some((item) => item.id === match) && (
        <MatchDetails opportunityId={match} navigate={navigate} onClose={() => setMatch(null)} />
      )}
    </>
  );
}
