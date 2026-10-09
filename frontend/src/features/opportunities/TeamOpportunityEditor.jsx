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
      title={saved ? 'Edit research opportunity' : 'Create research opportunity'}
      onClose={close}
    >
      {pendingClose ? (
        <div className="editor-confirm" role="alert">
          <h3>Leave without saving?</h3>
          <p>Your unsaved opportunity changes will be discarded.</p>
          <div className="actions">
            <Button variant="secondary" onClick={() => setPendingClose(false)}>
              Keep editing
            </Button>
            <Button onClick={onClose}>Discard changes</Button>
          </div>
        </div>
      ) : (
        <>
          <OpportunityRecovery editor={editor} tags={tags} />
          <form onSubmit={save}>
            <fieldset className="team-opportunity-fields" disabled={busy}>
              {dirty && (
                <span className="editor-dirty" role="status">
                  Unsaved changes
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
                  Cancel
                </Button>
                <Button type="submit" disabled={busy || needsReview || (saved && !dirty)}>
                  {busy ? 'Saving…' : saved ? 'Save opportunity' : 'Save draft'}
                </Button>
              </div>
            </fieldset>
          </form>
        </>
      )}
    </Modal>
  );
}
