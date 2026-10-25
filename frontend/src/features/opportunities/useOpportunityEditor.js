import { useState } from 'react';
import { api } from '../../api/client.js';
import { usePageGuard } from '../../shared/hooks.js';
import { useMutation } from '../../shared/useMutation.js';
import { emptyContent, validateOpportunity } from './fields.js';
import { futureDeadline } from './metadata.js';

export function useOpportunityEditor({ opportunity, tags, onDirty, onPending, onSaved, notify }) {
  const [saved, setSaved] = useState(opportunity);
  const [content, setContent] = useState(() =>
    structuredClone(opportunity?.content || emptyContent())
  );
  const [latest, setLatest] = useState(null);
  const [recent, setRecent] = useState(null);
  const { busy, error, clearError, setError, run, isPending } = useMutation();
  const dirty = JSON.stringify(content) !== JSON.stringify(saved?.content || emptyContent());
  const uncertain =
    ['NETWORK_ERROR', 'INVALID_RESPONSE'].includes(error?.code) || error?.status >= 500;
  const needsReview = error?.code === 'REVISION_CONFLICT' || uncertain;
  usePageGuard(dirty, busy, onDirty, onPending);
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
      () => api.saveOpportunity(saved?.id, saved?.revision, content),
      (result) => {
        setSaved(result);
        setContent(structuredClone(result.content));
        setLatest(null);
        notify?.('Opportunity saved.');
        onSaved?.(result);
      }
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
      () => api.publish(saved.id, saved.revision),
      (result) => {
        setSaved(result);
        notify?.('Opportunity published. Signed-in users can now discover it.');
      }
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
      () => api.saveOpportunity(saved.id, saved.revision, content, true),
      (result) => {
        setSaved(result);
        setContent(structuredClone(result.content));
        notify?.('Opportunity reopened.');
        onSaved?.(result);
      }
    );
  }
  function loadRecent(page = 1) {
    run(() => api.opportunities('mine', page), setRecent);
  }
  function reload() {
    // Read for comparison; never replace local input or retry a failed write here.
    if (saved) run(() => api.opportunity(saved.id), setLatest);
    else loadRecent();
  }
  function resolve(useLatest) {
    if (isPending() || !latest) return;
    setSaved(latest);
    if (useLatest) setContent(structuredClone(latest.content));
    setLatest(null);
    clearError();
  }
  function openRecent(item) {
    if (isPending()) return;
    setSaved(item);
    setContent(structuredClone(item.content));
    setRecent(null);
    clearError();
  }
  function continueCreating() {
    if (isPending()) return;
    setRecent(null);
    clearError();
  }
  return {
    saved,
    content,
    change,
    dirty,
    busy,
    error,
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
