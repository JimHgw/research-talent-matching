import { useLanguage, translateDiagnostic } from '../../shared/i18n.jsx';
import React, { useEffect, useState } from 'react';
import { api, ApiError } from '../../api/client.js';
import { Button, ErrorNotice, Loading, Modal, Notice } from '../../shared/ui.jsx';
import { useResource, usePageGuard, useUnsaved } from '../../shared/hooks.js';
import { useMutation } from '../../shared/useMutation.js';
import { labels } from '../../shared/profile-labels.js';
import ProfileFields from '../profile/ProfileFields.jsx';
import ReviewRecovery from './ReviewRecovery.jsx';

async function loadReview(documentId, { signal }) {
  const result = await Promise.all([
    api.extraction(documentId, { signal }),
    api.profile({ signal }),
  ]);
  if (result[0].documentId !== documentId || result[0].status !== 'READY') {
    throw new ApiError(502, {
      error: {
        code: 'INVALID_RESPONSE',
        message:
          'The review result did not match this document or its ready state. Refresh its status before reviewing.',
      },
    });
  }
  return result;
}

const unavailable = (error) =>
  ['EXTRACTION_NOT_READY', 'EXTRACTION_FAILED'].includes(error?.code) ||
  [401, 403, 404].includes(error?.status);

export default function ExtractionReview({
  document,
  tags,
  onClose,
  onApplied,
  onDirty,
  onPending,
  onManual,
  onRefresh,
}) {
  const { t, language } = useLanguage();
  const resource = useResource(({ signal }) => loadReview(document.id, { signal }), [document.id]);
  const [sections, setSections] = useState(null);
  const [selected, setSelected] = useState([]);
  const [ack, setAck] = useState(false);
  const { error, clearError, busy, run, isPending } = useMutation();
  const dirty =
    !!sections &&
    !!resource.data &&
    (JSON.stringify(sections) !== JSON.stringify(resource.data[0].suggestedSections) ||
      JSON.stringify([...selected].sort()) !== JSON.stringify(Object.keys(sections).sort()));
  usePageGuard(false, busy, onDirty, onPending);
  // The native modal isolates navigation; protect closing it and leaving the browser too.
  useUnsaved(dirty && !busy);
  useEffect(() => {
    if (resource.data) {
      const s = resource.data[0].suggestedSections;
      setSections(structuredClone(s));
      setSelected(Object.keys(s));
      setAck(false);
      clearError();
    }
  }, [resource.data, clearError]);
  function discardAllowed() {
    return (
      !isPending() &&
      (!dirty || window.confirm(t('Discard your changes to the extraction suggestions?')))
    );
  }
  function close() {
    if (!discardAllowed()) return;
    onClose();
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
    if (!discardAllowed()) return;
    setSections(null);
    setSelected([]);
    setAck(false);
    clearError();
    resource.refresh();
  }
  function apply(e) {
    e.preventDefault();
    if (
      isPending() ||
      !ack ||
      !selected.length ||
      error?.code === 'REVISION_CONFLICT' ||
      unavailable(error)
    )
      return;
    clearError();
    run(
      () =>
        api.apply(
          document.id,
          resource.data[1].revision,
          Object.fromEntries(selected.map((key) => [key, sections[key]]))
        ),
      onApplied
    );
  }
  const blocked = resource.error || (unavailable(error) ? error : null);
  const recovery = {
    error: blocked,
    retry: reload,
    onManual: manual,
    onRefresh: refreshDocuments,
    onClose: close,
  };
  return (
    <Modal title={t('Review extraction suggestions')} onClose={close}>
      <p className="review-document">
        {t('Reviewing: ')}
        <bdi>{document.fileName}</bdi>
      </p>
      {resource.loading || (!sections && !blocked) ? (
        <Loading />
      ) : blocked ? (
        <ReviewRecovery {...recovery} />
      ) : !Object.keys(sections).length ? (
        <ReviewRecovery {...recovery} empty />
      ) : (
        <form onSubmit={apply}>
          <fieldset className="form-fields" disabled={busy}>
            {!!resource.data[0].warnings.length && (
              <Notice>{resource.data[0].warnings.map((message) => t(message)).join(' ')}</Notice>
            )}
            <p>
              {t('Choose the sections to import. Edit any suggestion below before applying it.')}
            </p>
            <Button variant="text" disabled={busy} onClick={reload}>
              {t('Reload suggestions')}
            </Button>
            <div className="tag-options">
              {Object.keys(sections).map((key) => (
                <label className="tag-option" key={key}>
                  <input
                    type="checkbox"
                    checked={selected.includes(key)}
                    onChange={(e) => {
                      setSelected(
                        e.target.checked ? [...selected, key] : selected.filter((k) => k !== key)
                      );
                      setAck(false);
                    }}
                  />
                  {t(labels[key])}
                </label>
              ))}
            </div>
            <ProfileFields
              content={sections}
              onChange={(value) => {
                setSections(value);
                setAck(false);
              }}
              tags={tags}
              identity={false}
              sections={selected}
            />
            {resource.data[0].uncertainFields.map((f, i) => (
              <p className="help" key={i}>
                {t(labels[f.field])}: {t(f.status.replaceAll('_', ' '))} —{' '}
                {translateDiagnostic(language, f.reason)}
              </p>
            ))}
            <ErrorNotice error={error} />
            <label className="check-label">
              <input type="checkbox" checked={ack} onChange={(e) => setAck(e.target.checked)} />
              {t(
                'I understand that importing replaces the selected sections in my profile and requires a separate confirmation.'
              )}
            </label>
            <div className="actions">
              <Button variant="secondary" disabled={busy} onClick={close}>
                {t('Cancel')}
              </Button>
              <Button
                type="submit"
                disabled={busy || !ack || !selected.length || error?.code === 'REVISION_CONFLICT'}
              >
                {busy ? t('Importing…') : t('Apply reviewed sections')}
              </Button>
            </div>
            {error?.code === 'REVISION_CONFLICT' && (
              <Notice>
                <p>
                  {t(
                    'Your profile changed while this review was open. Your corrections have been kept. Review the latest profile, or reload suggestions and review them again before importing.'
                  )}
                </p>
                <Button variant="text" onClick={manual}>
                  {t('Review latest profile')}
                </Button>
              </Notice>
            )}
          </fieldset>
        </form>
      )}
    </Modal>
  );
}
