import { useLanguage } from '../../shared/i18n.jsx';
import React, { useState } from 'react';
import { api } from '../../api/client.js';
import { useResource, usePageGuard } from '../../shared/hooks.js';
import { useMutation } from '../../shared/useMutation.js';
import { displayDate } from '../../shared/format.js';
import { Badge, Button, Empty, ErrorNotice, Icon, Loading, Pager } from '../../shared/ui.jsx';
import OpportunityEditor from './TeamOpportunityEditor.jsx';
import OpportunityMetadata from './OpportunityMetadata.jsx';

export default function TeamOpportunities({ tags, notify, navigate, onDirty, onPending }) {
  const { t, language } = useLanguage();
  const [page, setPage] = useState(1);
  const [editor, setEditor] = useState(null);
  const { error, clearError, busy, run, isPending } = useMutation();
  const resource = useResource(() => api.opportunities('mine', page), [page], true);
  usePageGuard(false, busy, onDirty, onPending);
  function publish(opportunity) {
    if (isPending()) return;
    clearError();
    run(
      () => api.publish(opportunity.id, opportunity.revision),
      () => {
        resource.refresh();
        notify('Opportunity published. Talent can now discover it.');
      }
    );
  }
  return (
    <>
      <div className="section-title">
        <div>
          <h2>{t('Your research opportunities')}</h2>
          <p>{t('Manage drafts and publish the work you want to move forward.')}</p>
        </div>
        <Button disabled={busy} onClick={() => setEditor({})}>
          <Icon name="plus" size={16} />
          {t('New opportunity')}
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
          title={t('Your next project starts here')}
          action={<Button onClick={() => setEditor({})}>{t('Create an opportunity')}</Button>}
        >
          {t('Add a research opportunity to start discovering talent.')}
        </Empty>
      ) : (
        <div className="team-opportunities">
          {resource.data.items.map((opportunity) => (
            <article className="panel team-opportunity" key={opportunity.id}>
              <div className="row-between">
                <span className="eyebrow">
                  {opportunity.content.university} · {t(opportunity.content.disciplineGroup)}
                </span>
                <Badge
                  status={
                    opportunity.availabilityStatus === 'EXPIRED' ? 'EXPIRED' : opportunity.status
                  }
                />
              </div>
              <h3>{opportunity.content.title}</h3>
              <p>{opportunity.content.description}</p>
              <OpportunityMetadata content={opportunity.content} />
              <div className="tag-row">
                <span>{opportunity.content.researchArea}</span>
                <span>
                  {t('{count} requirements', { count: opportunity.content.requirements.length })}
                </span>
              </div>
              <div className="card-bottom">
                <small className="muted">
                  {t('Updated {date}', { date: displayDate(opportunity.updatedAt, language) })}
                  {opportunity.status === 'DRAFT' && !opportunity.content.requirements.length && (
                    <span className="publish-hint">{t('Add a requirement to publish.')}</span>
                  )}
                </small>
                <div className="actions compact">
                  <Button
                    variant="secondary"
                    disabled={busy}
                    onClick={() => setEditor(opportunity)}
                  >
                    {t('Edit')}
                  </Button>
                  {opportunity.status === 'DRAFT' ? (
                    <Button
                      disabled={busy || !opportunity.content.requirements.length}
                      title={
                        !opportunity.content.requirements.length
                          ? t('Add at least one requirement before publishing')
                          : undefined
                      }
                      onClick={() => publish(opportunity)}
                    >
                      {busy ? t('Publishing…') : t('Publish')}
                    </Button>
                  ) : (
                    <Button
                      disabled={opportunity.availabilityStatus === 'EXPIRED'}
                      onClick={() => navigate('talent', { initialOpportunity: opportunity.id })}
                    >
                      {t('Discover talent')}
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
          onPending={onPending}
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
