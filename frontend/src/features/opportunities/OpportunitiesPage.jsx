import { useLanguage } from '../../shared/i18n.jsx';
import React, { useState } from 'react';
import { api } from '../../api/client.js';
import { Badge, Button, Empty, ErrorNotice, Loading, Pager } from '../../shared/ui.jsx';
import { useResource } from '../../shared/hooks.js';
import { displayDate } from '../../shared/format.js';
import OpportunityEditor from './OpportunityEditor.jsx';
import OpportunityDetails from './OpportunityDetails.jsx';
import SearchFilters from '../../shared/SearchFilters.jsx';
import OpportunityMetadata from './OpportunityMetadata.jsx';

function SelectedOpportunity({ id, editable, onBack, ...props }) {
  const { t, language } = useLanguage();
  const resource = useResource(() => api.opportunity(id), [id], !editable);
  if (resource.loading) return <Loading />;
  if (resource.error)
    return (
      <>
        <Button variant="text" onClick={onBack}>
          {t('Back to opportunities')}
        </Button>
        <ErrorNotice error={resource.error} retry={resource.refresh} />
      </>
    );
  if (editable) return <OpportunityEditor opportunity={resource.data} onBack={onBack} {...props} />;
  return (
    <>
      <Button variant="text" onClick={onBack}>
        {t('Back to opportunities')}
      </Button>
      <OpportunityDetails opportunity={resource.data} tags={props.tags} />
    </>
  );
}

function OpportunityList({ scope, onSelect }) {
  const { t, language } = useLanguage();
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState({});
  const resource = useResource(
    () => api.opportunities(scope, page, filters),
    [scope, page, filters],
    true
  );
  const data = resource.data;
  return (
    <>
      <SearchFilters
        onApply={(next) => {
          setPage(1);
          setFilters(next);
        }}
      />
      {resource.loading ? (
        <Loading />
      ) : resource.error ? (
        <ErrorNotice error={resource.error} retry={resource.refresh} />
      ) : (
        <>
          <div className="opportunity-list-heading">
            <p className="muted">{t('{count} opportunities', { count: data.total })}</p>
            <Button variant="text" onClick={resource.refresh}>
              {t('Refresh opportunities')}
            </Button>
          </div>
          {!data.items.length && (
            <Empty
              icon="briefcase"
              title={
                Object.keys(filters).length
                  ? t('No results match these filters.')
                  : page > 1
                    ? t('No opportunities on this page')
                    : scope === 'mine'
                      ? t('Create your first opportunity')
                      : t('No published opportunities yet')
              }
            >
              {Object.keys(filters).length
                ? t('Try changing or clearing the filters.')
                : scope === 'mine'
                  ? t(
                      'Describe your research and the skills or interests your team is looking for.'
                    )
                  : t('Published opportunities will appear here when research teams share them.')}
            </Empty>
          )}
          <div className="opportunity-list">
            {data.items.map((item) => (
              <article className="panel opportunity-card" key={item.id}>
                <div className="opportunity-meta">
                  <Badge status={item.availabilityStatus === 'EXPIRED' ? 'EXPIRED' : item.status} />
                  <span>{t(item.content.disciplineGroup)}</span>
                </div>
                <h2>{item.content.title}</h2>
                <p className="muted">
                  {item.content.university} · {item.content.discipline}
                </p>
                <p>{item.content.researchArea}</p>
                <p className="opportunity-excerpt">{item.content.description}</p>
                <OpportunityMetadata content={item.content} />
                <div className="opportunity-card-footer">
                  <small>
                    {t('Updated {date}', { date: displayDate(item.updatedAt, language) })}
                  </small>
                  <Button variant="secondary" onClick={() => onSelect(item.id)}>
                    {scope === 'mine' ? t('View and edit') : t('View details')}
                  </Button>
                </div>
              </article>
            ))}
          </div>
          <Pager data={data} onPage={setPage} />
          {!data.items.length && page > 1 && (
            <Button variant="secondary" onClick={() => setPage(1)}>
              {t('Back to first page')}
            </Button>
          )}
        </>
      )}
    </>
  );
}

export default function OpportunitiesPage({ user, tags, onDirty, onPending, notify }) {
  const { t, language } = useLanguage();
  const team = user.role === 'RESEARCH_TEAM';
  const [scope, setScope] = useState(team ? 'mine' : 'published');
  const [selected, setSelected] = useState(null);
  function back() {
    onDirty(false);
    setSelected(null);
  }
  const editorProps = { tags, onDirty, onPending, notify, onBack: back };
  if (selected === 'new') return <OpportunityEditor {...editorProps} />;
  if (selected)
    return <SelectedOpportunity id={selected} editable={scope === 'mine'} {...editorProps} />;
  return (
    <div>
      <div className="section-title opportunity-toolbar">
        {team ? (
          <div className="actions" role="group" aria-label={t('Opportunity scope')}>
            <Button
              variant={scope === 'mine' ? 'primary' : 'secondary'}
              aria-pressed={scope === 'mine'}
              onClick={() => setScope('mine')}
            >
              {t('My opportunities')}
            </Button>
            <Button
              variant={scope === 'published' ? 'primary' : 'secondary'}
              aria-pressed={scope === 'published'}
              onClick={() => setScope('published')}
            >
              {t('Published opportunities')}
            </Button>
          </div>
        ) : (
          <p className="muted">{t('Explore published research opportunities.')}</p>
        )}
        {team && <Button onClick={() => setSelected('new')}>{t('Create opportunity')}</Button>}
      </div>
      <OpportunityList key={scope} scope={scope} onSelect={setSelected} />
    </div>
  );
}
