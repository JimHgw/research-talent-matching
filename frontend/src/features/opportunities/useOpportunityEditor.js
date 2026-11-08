import { useEffect, useRef, useState } from 'react';
import { api } from '../../api/client.js';
import { usePageGuard } from '../../shared/hooks.js';
import { useMutation } from '../../shared/useMutation.js';
import { emptyContent, validateOpportunity } from './fields.js';
import { futureDeadline } from './metadata.js';
import {
  accessLost,
  requiresReconciliation,
  uncertainWrite,
  requireSnapshot,
} from '../../shared/editor-state.js';
import { invalidateData } from '../../shared/data-invalidation.js';
import { validateOpportunitySnapshot } from './opportunity-state.js';

export function useOpportunityEditor({
  opportunity,
  tags,
  onDirty,
  onPending,
  onSaved,
  notify,
  initialError = null,
  onReconciled,
}) {
  const [saved, setSaved] = useState(opportunity);
  const [content, setContent] = useState(() =>
    structuredClone(opportunity?.content || emptyContent())
  );
  const [latest, setLatest] = useState(null);
  const [recent, setRecent] = useState(null);
  const [failure, setFailure] = useState(initialError);
  const [unavailable, setUnavailable] = useState(accessLost(initialError) ? initialError : null);
  const readController = useRef(null);
  useEffect(() => () => readController.current?.abort(), []);
  const { busy, error, clearError, setError, run, isPending } = useMutation();
  const dirty = JSON.stringify(content) !== JSON.stringify(saved?.content || emptyContent());
  const uncertain = uncertainWrite(failure || error);
  const needsReview = !!failure || !!latest || requiresReconciliation(error) || !!unavailable;
  usePageGuard(dirty || needsReview, busy, onDirty, onPending);
  function failedWrite(error) {
    if (accessLost(error)) revoke(error);
    else if (requiresReconciliation(error)) setFailure(error);
  }
  function revoke(error) {
    setUnavailable(error);
    setSaved(null);
    setContent(emptyContent());
    setLatest(null);
    setRecent(null);
    setFailure(null);
  }
  function checkedWrite(action, operation) {
    return async () => validateOpportunitySnapshot(await action(), { previous: saved, operation });
  }
  function change(next) {
    if (!isPending()) setContent(next);
  }
  function save(event) {
    event.preventDefault();
    if (isPending() || needsReview || (saved && !dirty)) return;
    const message = validateOpportunity(content, tags, saved?.status);
    if (message) {
      setError({ code: 'VALIDATION_ERROR', message });
      return;
    }
    clearError();
    run(
      checkedWrite(() => api.saveOpportunity(saved?.id, saved?.revision, content), 'save'),
      (result) => {
        setSaved(result);
        setContent(structuredClone(result.content));
        setLatest(null);
        setFailure(null);
        invalidateData('opportunities', 'matching', 'collections');
        notify?.('Opportunity saved.');
        onSaved?.(result);
      },
      failedWrite
    );
  }
  function publish() {
    if (
      isPending() ||
      needsReview ||
      dirty ||
      saved?.status !== 'DRAFT' ||
      !saved.content.requirements.length
    )
      return;
    clearError();
    run(
      checkedWrite(() => api.publish(saved.id, saved.revision), 'publish'),
      (result) => {
        setSaved(result);
        invalidateData('opportunities', 'matching', 'collections');
        notify?.('Opportunity published. Signed-in users can now discover it.');
      },
      failedWrite
    );
  }
  function reopen() {
    if (
      isPending() ||
      needsReview ||
      saved?.status !== 'PUBLISHED' ||
      saved?.availabilityStatus !== 'EXPIRED'
    )
      return;
    const message = validateOpportunity(content, tags, saved.status);
    if (message || !futureDeadline(content.deadlineAt)) {
      setError({
        code: 'VALIDATION_ERROR',
        message: message || 'Choose a future deadline or remove it before reopening.',
      });
      return;
    }
    clearError();
    run(
      checkedWrite(() => api.saveOpportunity(saved.id, saved.revision, content, true), 'reopen'),
      (result) => {
        setSaved(result);
        setContent(structuredClone(result.content));
        invalidateData('opportunities', 'matching', 'collections');
        notify?.('Opportunity reopened.');
        onSaved?.(result);
      },
      failedWrite
    );
  }
  function loadRecent(page = 1) {
    if (isPending()) return;
    readController.current?.abort();
    const controller = new AbortController();
    readController.current = controller;
    run(
      async () => {
        const result = await api.opportunities('mine', page, {}, { signal: controller.signal });
        requireSnapshot(Array.isArray(result?.items));
        result.items.forEach((item) => validateOpportunitySnapshot(item));
        return result;
      },
      setRecent,
      (error) => {
        if (accessLost(error)) revoke(error);
      }
    );
  }
  function reload() {
    // Read for comparison; never replace local input or retry a failed write here.
    if (isPending()) return;
    readController.current?.abort();
    const controller = new AbortController();
    readController.current = controller;
    if (saved)
      run(
        async () =>
          validateOpportunitySnapshot(
            await api.opportunity(saved.id, { signal: controller.signal }),
            { previous: saved }
          ),
        setLatest,
        (error) => {
          if (accessLost(error)) revoke(error);
        }
      );
    else loadRecent();
  }
  function resolve(useLatest) {
    if (isPending() || !latest) return;
    setSaved(latest);
    if (useLatest) setContent(structuredClone(latest.content));
    setLatest(null);
    setFailure(null);
    clearError();
    onReconciled?.(latest);
    invalidateData('opportunities', 'matching', 'collections');
  }
  function openRecent(item) {
    if (isPending()) return;
    setSaved(item);
    setContent(structuredClone(item.content));
    setRecent(null);
    setFailure(null);
    clearError();
    onReconciled?.(item);
  }
  function continueCreating() {
    if (isPending() || !recent) return;
    setRecent(null);
    setFailure(null);
    clearError();
  }
  return {
    saved,
    content,
    change,
    dirty,
    busy,
    error: failure || error,
    readError: failure && error !== failure ? error : null,
    unavailable,
    uncertain,
    needsReview,
    latest,
    recent,
    save,
    publish,
    reopen,
    reload,
    resolve,
    openRecent,
    loadRecent,
    continueCreating,
    isPending,
  };
}
