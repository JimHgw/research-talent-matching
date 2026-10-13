import React, { useEffect, useState } from 'react';
import { api } from '../../api/client.js';
import { useResource } from '../../shared/hooks.js';
import { useMutation } from '../../shared/useMutation.js';
import { Button, ErrorNotice } from '../../shared/ui.jsx';

export const collectionChanged = 'research-collection-changed';

export default function CollectionButton({ opportunityId, talentId, onChange }) {
  const resource = useResource(
    () => api.collectionState(opportunityId, talentId),
    [opportunityId, talentId],
    true
  );
  const mutation = useMutation();
  const [message, setMessage] = useState('');
  useEffect(() => {
    const refresh = () => resource.refresh();
    window.addEventListener(collectionChanged, refresh);
    return () => window.removeEventListener(collectionChanged, refresh);
  }, [resource.refresh]);
  const saved = resource.data?.saved;
  const label = talentId
    ? saved
      ? 'Remove from Shortlist'
      : 'Add to Shortlist'
    : saved
      ? 'Remove from Saved'
      : 'Save Opportunity';
  return (
    <div>
      {saved && <span className="subtle-pill">{talentId ? 'Shortlisted' : 'Saved'}</span>}
      <Button
        variant="secondary"
        disabled={resource.loading || !!resource.error || mutation.busy}
        onClick={() => {
          mutation.clearError();
          setMessage('');
          mutation.run(
            () => api.setCollection(opportunityId, talentId, !saved),
            (result) => {
              setMessage(result.saved ? 'Saved successfully.' : 'Removed successfully.');
              window.dispatchEvent(new window.Event(collectionChanged));
              onChange?.();
            }
          );
        }}
      >
        {resource.loading ? 'Checking saved state…' : mutation.busy ? 'Saving…' : label}
      </Button>
      {message && <p role="status">{message}</p>}
      {resource.error && <ErrorNotice error={resource.error} retry={resource.refresh} />}
      {mutation.error && <ErrorNotice error={mutation.error} retry={resource.refresh} />}
    </div>
  );
}
