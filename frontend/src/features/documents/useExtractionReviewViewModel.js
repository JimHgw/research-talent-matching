import { useEffect, useState } from 'react';
import { reviewRepository } from '../../api/review-repository.ts';
import { accessLost, requiresReconciliation, uncertainWrite } from '../../shared/editor-state.js';
import { usePageGuard, useResource, useUnsaved } from '../../shared/hooks.js';
import { useMutation } from '../../shared/useMutation.js';
import { applyReviewedExtraction, loadExtractionReview } from './extraction-review-use-cases.ts';

function unavailable(error) {
  return accessLost(error) || ['EXTRACTION_NOT_READY', 'EXTRACTION_FAILED'].includes(error?.code);
}

export function useExtractionReviewViewModel({
  documentId,
  onClose,
  onApplied,
  onDirty,
  onPending,
  onManual,
  onRefresh,
  confirmDiscard,
  repository = reviewRepository,
}) {
  const resource = useResource(
    ({ signal }) => loadExtractionReview(repository, documentId, { signal }),
    [repository, documentId]
  );
  const [draft, setDraft] = useState(null);
  const { error, clearError, busy, run, isPending } = useMutation();
  const review = draft?.loaded.extraction.documentId === documentId ? draft : null;
  const original = review?.loaded.extraction.suggestedSections;
  const sections = review?.sections;
  const selected = review?.selected ?? [];
  const acknowledged = review?.acknowledged ?? false;
  const dirty =
    !!review &&
    (JSON.stringify(sections) !== JSON.stringify(original) ||
      Object.keys(original).length !== selected.length);
  const blocked = resource.error || (unavailable(error) ? error : null);
  const needsReconciliation = requiresReconciliation(error);
  const uncertain = uncertainWrite(error);
  const canApply =
    !!review &&
    !resource.loading &&
    !blocked &&
    !busy &&
    acknowledged &&
    selected.length > 0 &&
    !needsReconciliation;

  // The modal guards its own closing actions. Its pending write also guards the workspace.
  usePageGuard(false, busy, onDirty, onPending);
  useUnsaved(dirty && !busy);

  useEffect(() => {
    const loaded = resource.data;
    if (!loaded) return;
    setDraft((current) => {
      if (current?.loaded.extraction.documentId === loaded.extraction.documentId) return current;
      const suggestions = loaded.extraction.suggestedSections;
      return {
        loaded,
        sections: structuredClone(suggestions),
        selected: Object.keys(suggestions),
        acknowledged: false,
      };
    });
  }, [resource.data]);

  function updateDraft(update) {
    if (isPending()) return;
    setDraft((current) =>
      current?.loaded.extraction.documentId === documentId
        ? { ...current, ...update(current) }
        : current
    );
  }

  function discardAllowed() {
    return !isPending() && (!dirty || confirmDiscard());
  }

  function close() {
    if (discardAllowed()) onClose();
  }

  function manual() {
    if (!discardAllowed()) return;
    onClose();
    onManual();
  }

  function refreshDocuments() {
    if (discardAllowed()) onRefresh();
  }

  function reload() {
    if (uncertain || !discardAllowed()) return;
    setDraft(null);
    clearError();
    resource.refresh();
  }

  function apply() {
    if (isPending() || !canApply) return;
    clearError();
    run(() => applyReviewedExtraction(repository, review.loaded, sections, selected), onApplied);
  }

  return {
    loading: resource.loading || (!review && !blocked),
    sections,
    selected,
    acknowledged,
    busy,
    error,
    blocked,
    uncertain,
    canApply,
    warnings: review?.loaded.extraction.warnings ?? [],
    uncertainFields: review?.loaded.extraction.uncertainFields ?? [],
    close,
    manual,
    refreshDocuments,
    reload,
    apply,
    edit: (value) => updateDraft(() => ({ sections: value, acknowledged: false })),
    select: (key, checked) =>
      updateDraft((current) => ({
        selected: checked
          ? [...new Set([...current.selected, key])]
          : current.selected.filter((item) => item !== key),
        acknowledged: false,
      })),
    acknowledge: (value) => updateDraft(() => ({ acknowledged: value })),
  };
}
