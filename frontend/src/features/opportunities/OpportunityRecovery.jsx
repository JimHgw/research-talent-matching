import { useLanguage } from '../../shared/i18n.jsx';
import React from 'react';
import { Badge, Button, ErrorNotice, Notice, Pager } from '../../shared/ui.jsx';
import { OpportunityContent } from './OpportunityDetails.jsx';

export default function OpportunityRecovery({ editor, tags }) {
  const { t } = useLanguage();
  const {
    busy,
    error,
    uncertain,
    needsReview,
    latest,
    recent,
    content,
    reload,
    resolve,
    openRecent,
    loadRecent,
    continueCreating,
  } = editor;
  return (
    <>
      <ErrorNotice error={error} retry={needsReview && !busy ? reload : undefined} />
      <ErrorNotice error={editor.readError} retry={!busy ? reload : undefined} />
      {uncertain && (
        <Notice>
          {t(
            'The request may have succeeded. Reload the latest data and check it before trying again.'
          )}
        </Notice>
      )}
      {latest && (
        <section className="panel" aria-label={t('Compare opportunity versions')}>
          <h3>{t('Compare before continuing')}</h3>
          <p>
            {t(
              'Your input is still here. Review both versions, then choose which content to continue editing.'
            )}
          </p>
          <div className="opportunity-comparison">
            <div>
              <h4>{t('Your local version')}</h4>
              <OpportunityContent content={content} tags={tags} />
            </div>
            <div>
              <h4>{t('Latest saved version')}</h4>
              <Badge status={latest.status} />
              <OpportunityContent content={latest.content} tags={tags} />
            </div>
          </div>
          <div className="actions">
            <Button variant="secondary" disabled={busy} onClick={() => resolve(true)}>
              {t('Use latest version')}
            </Button>
            <Button disabled={busy} onClick={() => resolve(false)}>
              {t('Continue editing my version')}
            </Button>
          </div>
          <p className="help">
            {t(
              'Continuing with your version does not save it. Review and merge any changes before saving again.'
            )}
          </p>
        </section>
      )}
      {recent && (
        <section className="panel">
          <h3>{t('Recently saved opportunities')}</h3>
          <p>
            {t(
              'Check whether this draft was created before submitting again. Your form is preserved below.'
            )}
          </p>
          <fieldset className="form-fields" disabled={busy}>
            {recent.items.map((item) => (
              <div key={item.id}>
                <OpportunityContent content={item.content} tags={tags} />
                <Button variant="secondary" onClick={() => openRecent(item)}>
                  {t('Open saved draft: {title}', { title: item.content.title })}
                </Button>
              </div>
            ))}
            <Pager data={recent} onPage={loadRecent} />
            <Button variant="text" onClick={continueCreating}>
              {t('I checked; keep creating this draft')}
            </Button>
          </fieldset>
        </section>
      )}
    </>
  );
}
