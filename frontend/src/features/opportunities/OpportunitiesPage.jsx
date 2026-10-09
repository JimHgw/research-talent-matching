import React, { useState } from 'react';
import { api } from '../../api/client.js';
import { Badge, Button, Empty, ErrorNotice, Loading, Pager } from '../../shared/ui.jsx';
import { useResource } from '../../shared/hooks.js';
import { displayDate } from '../../shared/format.js';
import OpportunityEditor from './OpportunityEditor.jsx';
import OpportunityDetails from './OpportunityDetails.jsx';

function SelectedOpportunity({ id, editable, onBack, ...props }) {
  const resource = useResource(() => api.opportunity(id), [id]);
  if (resource.loading) return <Loading />;
  if (resource.error)
    return (
      <>
        <Button variant="text" onClick={onBack}>
          Back to opportunities
        </Button>
        <ErrorNotice error={resource.error} retry={resource.refresh} />
      </>
    );
  if (editable) return <OpportunityEditor opportunity={resource.data} onBack={onBack} {...props} />;
  return (
    <>
      <Button variant="text" onClick={onBack}>
        Back to opportunities
      </Button>
      <OpportunityDetails opportunity={resource.data} tags={props.tags} />
    </>
  );
}

function OpportunityList({ scope, onSelect }) {
  const [page, setPage] = useState(1);
  const resource = useResource(() => api.opportunities(scope, page), [scope, page], true);
  if (resource.loading) return <Loading />;
  if (resource.error) return <ErrorNotice error={resource.error} retry={resource.refresh} />;
  const data = resource.data;
  return (
    <>
      <div className="opportunity-list-heading">
        <p className="muted">{data.total} opportunities</p>
        <Button variant="text" onClick={resource.refresh}>
          Refresh opportunities
        </Button>
      </div>
      {!data.items.length && (
        <Empty
          icon="briefcase"
          title={
            page > 1
              ? 'No opportunities on this page'
              : scope === 'mine'
                ? 'Create your first opportunity'
                : 'No published opportunities yet'
          }
        >
          {scope === 'mine'
            ? 'Describe your research and the skills or interests your team is looking for.'
            : 'Published opportunities will appear here when research teams share them.'}
        </Empty>
      )}
      <div className="opportunity-list">
        {data.items.map((item) => (
          <article className="panel opportunity-card" key={item.id}>
            <div className="opportunity-meta">
              <Badge status={item.status} />
              <span>{item.content.disciplineGroup}</span>
            </div>
            <h2>{item.content.title}</h2>
            <p className="muted">
              {item.content.university} · {item.content.discipline}
            </p>
            <p>{item.content.researchArea}</p>
            <p className="opportunity-excerpt">{item.content.description}</p>
            <div className="opportunity-card-footer">
              <small>Updated {displayDate(item.updatedAt)}</small>
              <Button variant="secondary" onClick={() => onSelect(item.id)}>
                {scope === 'mine' ? 'View and edit' : 'View details'}
              </Button>
            </div>
          </article>
        ))}
      </div>
      <Pager data={data} onPage={setPage} />
      {!data.items.length && page > 1 && (
        <Button variant="secondary" onClick={() => setPage(1)}>
          Back to first page
        </Button>
      )}
    </>
  );
}

export default function OpportunitiesPage({ user, tags, onDirty, onPending, notify }) {
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
          <div className="actions" role="group" aria-label="Opportunity scope">
            <Button
              variant={scope === 'mine' ? 'primary' : 'secondary'}
              aria-pressed={scope === 'mine'}
              onClick={() => setScope('mine')}
            >
              My opportunities
            </Button>
            <Button
              variant={scope === 'published' ? 'primary' : 'secondary'}
              aria-pressed={scope === 'published'}
              onClick={() => setScope('published')}
            >
              Published opportunities
            </Button>
          </div>
        ) : (
          <p className="muted">Explore published research opportunities.</p>
        )}
        {team && <Button onClick={() => setSelected('new')}>Create opportunity</Button>}
      </div>
      <OpportunityList key={scope} scope={scope} onSelect={setSelected} />
    </div>
  );
}
