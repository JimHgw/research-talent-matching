import { useLanguage } from '../../shared/i18n.jsx';
import React, { useState } from 'react';
import { Button, Modal } from '../../shared/ui.jsx';
import { useOpportunityEditor } from './useOpportunityEditor.js';
import OpportunityFields from './OpportunityFields.jsx';
import OpportunityRecovery from './OpportunityRecovery.jsx';

export default function TeamOpportunityEditor({
  opportunity,
  tags,
  onClose,
  onSaved,
  onDirty,
  onPending,
}) {
  const { t } = useLanguage();
  const editor = useOpportunityEditor({ opportunity, tags, onSaved, onDirty, onPending });
  const { saved, content, change, dirty, busy, needsReview, save, isPending } = editor;
  const [pendingClose, setPendingClose] = useState(false);
  function close() {
    if (isPending()) return;
    if (dirty) setPendingClose(true);
    else onClose();
  }
  return (
    <Modal
      title={saved ? t('Edit research opportunity') : t('Create research opportunity')}
      onClose={close}
    >
      {pendingClose ? (
        <div className="editor-confirm" role="alert">
          <h3>{t('Leave without saving?')}</h3>
          <p>{t('Your unsaved opportunity changes will be discarded.')}</p>
          <div className="actions">
            <Button variant="secondary" onClick={() => setPendingClose(false)}>
              {t('Keep editing')}
            </Button>
            <Button onClick={onClose}>{t('Discard changes')}</Button>
          </div>
        </div>
      ) : (
        <>
          <OpportunityRecovery editor={editor} tags={tags} />
          <form onSubmit={save}>
            <fieldset className="team-opportunity-fields" disabled={busy}>
              {dirty && (
                <span className="editor-dirty" role="status">
                  {t('Unsaved changes')}
                </span>
              )}
              <OpportunityFields
                content={content}
                onChange={change}
                tags={tags}
                status={saved?.status}
                requiredLabels
              />
              <div className="actions">
                <Button variant="secondary" disabled={busy} onClick={close}>
                  {t('Cancel')}
                </Button>
                <Button type="submit" disabled={busy || needsReview || (saved && !dirty)}>
                  {busy ? t('Saving…') : saved ? t('Save opportunity') : t('Save draft')}
                </Button>
              </div>
            </fieldset>
          </form>
        </>
      )}
    </Modal>
  );
}
