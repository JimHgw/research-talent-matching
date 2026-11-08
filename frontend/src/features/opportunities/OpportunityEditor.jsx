import { useLanguage } from '../../shared/i18n.jsx';
import React from 'react';
import { Badge, Button, ErrorNotice } from '../../shared/ui.jsx';
import { useOpportunityEditor } from './useOpportunityEditor.js';
import OpportunityFields from './OpportunityFields.jsx';
import OpportunityRecovery from './OpportunityRecovery.jsx';

export default function OpportunityEditor({
  opportunity,
  tags,
  onDirty,
  onPending,
  notify,
  onBack,
}) {
  const { t } = useLanguage();
  const editor = useOpportunityEditor({ opportunity, tags, onDirty, onPending, notify });
  const { saved, content, change, busy, dirty, needsReview, save, publish, isPending } = editor;
  function back() {
    if (isPending()) return;
    if ((!dirty && !needsReview) || window.confirm(t('Discard your unsaved opportunity changes?')))
      onBack();
  }
  if (editor.unavailable)
    return (
      <>
        <Button variant="text" onClick={onBack}>
          {t('Back to opportunities')}
        </Button>
        <ErrorNotice error={editor.unavailable} />
      </>
    );
  return (
    <div className="opportunity-editor">
      <Button variant="text" onClick={back} disabled={busy}>
        {t('Back to opportunities')}
      </Button>
      <div className="section-title">
        <h2>{saved ? t('Edit opportunity') : t('Create opportunity')}</h2>
        <Badge
          status={saved?.availabilityStatus === 'EXPIRED' ? 'EXPIRED' : saved?.status || 'DRAFT'}
        />
      </div>
      <OpportunityRecovery editor={editor} tags={tags} />
      <form onSubmit={save}>
        <fieldset disabled={busy} className="opportunity-form-fields">
          <OpportunityFields
            content={content}
            onChange={change}
            tags={tags}
            status={saved?.status}
          />
          <div className="actions">
            <Button type="submit" disabled={busy || needsReview || (!dirty && !!saved)}>
              {busy ? t('Working…') : saved ? t('Save changes') : t('Save draft')}
            </Button>
            {saved?.status === 'DRAFT' && (
              <Button
                variant="secondary"
                onClick={publish}
                disabled={busy || dirty || needsReview || !saved.content.requirements.length}
              >
                {t('Publish opportunity')}
              </Button>
            )}
            {saved?.availabilityStatus === 'EXPIRED' && (
              <Button disabled={busy || needsReview} onClick={editor.reopen}>
                {dirty ? t('Save and reopen opportunity') : t('Reopen opportunity')}
              </Button>
            )}
          </div>
        </fieldset>
      </form>
    </div>
  );
}
