import { useCallback, useEffect, useState } from 'react';
import { api } from '../../api/client.js';
import { useResource } from '../../shared/hooks.js';

export const DOCUMENT_POLL_INTERVAL = 2000;
export const DOCUMENT_POLL_BUDGET = 60000;

// List refreshes never replace the independently selected review draft/revision.
export function useDocumentsQuery(page, documents = api.documents) {
  const resource = useResource(
    ({ signal }) => documents(page, { signal }),
    [page, documents],
    false,
    { retainData: true }
  );
  const [deadline, setDeadline] = useState(() => Date.now() + DOCUMENT_POLL_BUDGET);
  const [paused, setPaused] = useState(false);
  const [visible, setVisible] = useState(() => document.visibilityState !== 'hidden');
  const pending = !!resource.data?.items.some((item) =>
    ['QUEUED', 'PROCESSING'].includes(item.status)
  );
  const refresh = useCallback(() => {
    setDeadline(Date.now() + DOCUMENT_POLL_BUDGET);
    setPaused(false);
    resource.refresh();
  }, [resource.refresh]);

  useEffect(() => {
    if (!pending || paused) return;
    const remaining = deadline - Date.now();
    if (remaining <= 0) {
      setPaused(true);
      return;
    }
    const timer = setTimeout(() => setPaused(true), remaining);
    return () => clearTimeout(timer);
  }, [pending, paused, deadline]);

  useEffect(() => {
    const onVisibility = () => {
      const next = document.visibilityState !== 'hidden';
      setVisible(next);
      if (!next || !pending || paused) return;
      if (Date.now() >= deadline) setPaused(true);
      else if (!resource.loading) resource.refresh();
    };
    document.addEventListener('visibilitychange', onVisibility);
    return () => document.removeEventListener('visibilitychange', onVisibility);
  }, [pending, paused, deadline, resource.loading, resource.refresh]);

  useEffect(() => {
    if (!pending || paused || !visible || resource.loading || Date.now() >= deadline) return;
    const timer = setTimeout(() => {
      if (document.visibilityState !== 'hidden' && Date.now() < deadline) resource.refresh();
    }, DOCUMENT_POLL_INTERVAL);
    return () => clearTimeout(timer);
  }, [pending, paused, visible, deadline, resource.loading, resource.data, resource.refresh]);

  return { ...resource, refresh, paused: pending && paused };
}
