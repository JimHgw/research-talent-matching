import React, { useState } from 'react';
import { api } from '../../api/client.js';
import { useResource } from '../../shared/hooks.js';
import { displayDate } from '../../shared/format.js';
import { Badge, Button, Empty, ErrorNotice, Icon, Loading, Pager } from '../../shared/ui.jsx';
import OpportunityEditor from './OpportunityEditor.jsx';

export default function TeamOpportunities({ tags, notify, navigate, onDirty }) {
  const [page, setPage] = useState(1);
  const [editor, setEditor] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(null);
  const resource = useResource(() => api.opportunities('mine', page), [page], true);
  async function publish(opportunity) {
    setBusy(opportunity.id);
    setError(null);
    try {
      await api.publish(opportunity.id, opportunity.revision);
      resource.refresh();
      notify('Opportunity published. Talent can now discover it.');
    } catch (e) {
      setError(e);
    } finally {
      setBusy(null);
    }
  }
  return (
    <>
      <div className="section-title">
        <div>
          <h2>Your research opportunities</h2>
          <p>Manage drafts and publish the work you want to move forward.</p>
        </div>
        <Button onClick={() => setEditor({})}>
          <Icon name="plus" size={16} />
          New opportunity
        </Button>
      </div>
      <ErrorNotice
        error={error}
        retry={error?.code === 'REVISION_CONFLICT' ? resource.refresh : undefined}
      />
      {resource.loading ? (
        <Loading />
      ) : resource.error ? (
        <ErrorNotice error={resource.error} retry={resource.refresh} />
      ) : !resource.data.items.length ? (
        <Empty
          icon="briefcase"
          title="Your next project starts here"
          action={<Button onClick={() => setEditor({})}>Create an opportunity</Button>}
        >
          Add a research opportunity to start discovering talent.
        </Empty>
      ) : (
        <div className="team-opportunities">
          {resource.data.items.map((opportunity) => (
            <article className="panel team-opportunity" key={opportunity.id}>
              <div className="row-between">
                <span className="eyebrow">
                  {opportunity.content.university} · {opportunity.content.disciplineGroup}
                </span>
                <Badge status={opportunity.status} />
              </div>
              <h3>{opportunity.content.title}</h3>
              <p>{opportunity.content.description}</p>
              <div className="tag-row">
                <span>{opportunity.content.researchArea}</span>
                <span>{opportunity.content.requirements.length} requirements</span>
              </div>
              <div className="card-bottom">
                <small className="muted">
                  Updated {displayDate(opportunity.updatedAt)}
                  {opportunity.status === 'DRAFT' && !opportunity.content.requirements.length && (
                    <span className="publish-hint">Add a requirement to publish.</span>
                  )}
                </small>
                <div className="actions compact">
                  <Button variant="secondary" onClick={() => setEditor(opportunity)}>
                    Edit
                  </Button>
                  {opportunity.status === 'DRAFT' ? (
                    <Button
                      disabled={busy === opportunity.id || !opportunity.content.requirements.length}
                      title={
                        !opportunity.content.requirements.length
                          ? 'Add at least one requirement before publishing'
                          : undefined
                      }
                      onClick={() => publish(opportunity)}
                    >
                      {busy === opportunity.id ? 'Publishing…' : 'Publish'}
                    </Button>
                  ) : (
                    <Button
                      onClick={() => navigate('talent', { initialOpportunity: opportunity.id })}
                    >
                      Discover talent
                      <Icon name="arrow" size={16} />
                    </Button>
                  )}
                </div>
              </div>
            </article>
          ))}
        </div>
      )}
      <Pager data={resource.data} onPage={setPage} />
      {editor && (
        <OpportunityEditor
          onDirty={onDirty}
          opportunity={editor.id ? editor : null}
          tags={tags}
          onClose={() => setEditor(null)}
          onSaved={() => {
            setEditor(null);
            resource.refresh();
            notify('Opportunity saved.');
          }}
        />
      )}
    </>
  );
}
