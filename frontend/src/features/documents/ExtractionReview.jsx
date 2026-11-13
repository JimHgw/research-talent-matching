import { useLanguage, translateDiagnostic } from '../../shared/i18n.jsx';
import React from 'react';
import { Button, ErrorNotice, Loading, Modal, Notice } from '../../shared/ui.jsx';
import { labels } from '../../shared/profile-labels.js';
import ProfileFields from '../profile/ProfileFields.jsx';
import ReviewRecovery from './ReviewRecovery.jsx';
import { useExtractionReviewViewModel } from './useExtractionReviewViewModel.js';

export default function ExtractionReview({ document, tags, ...actions }) {
  const { t, language } = useLanguage();
  const review = useExtractionReviewViewModel({
    ...actions,
    documentId: document.id,
    confirmDiscard: () => window.confirm(t('Discard your changes to the extraction suggestions?')),
  });
  const { sections, selected, busy, error, blocked, uncertain, close, manual, reload } = review;
  const recovery = {
    error: blocked,
    retry: reload,
    onManual: manual,
    onRefresh: review.refreshDocuments,
    onClose: close,
  };
  return (
    <Modal title={t('Review extraction suggestions')} onClose={close}>
      <p className="review-document">
        {t('Reviewing: ')}
        <bdi>{document.fileName}</bdi>
      </p>
      {review.loading ? (
        <Loading />
      ) : blocked ? (
        <ReviewRecovery {...recovery} />
      ) : !Object.keys(sections).length ? (
        <ReviewRecovery {...recovery} empty />
      ) : (
        <form
          onSubmit={(event) => {
            event.preventDefault();
            review.apply();
          }}
        >
          <fieldset className="form-fields" disabled={busy}>
            {!!review.warnings.length && (
              <Notice>{review.warnings.map((message) => t(message)).join(' ')}</Notice>
            )}
            <p>
              {t('Choose the sections to import. Edit any suggestion below before applying it.')}
            </p>
            <Button variant="text" disabled={busy || uncertain} onClick={reload}>
              {t('Reload suggestions')}
            </Button>
            <div className="tag-options">
              {Object.keys(sections).map((key) => (
                <label className="tag-option" key={key}>
                  <input
                    type="checkbox"
                    checked={selected.includes(key)}
                    onChange={(e) => review.select(key, e.target.checked)}
                  />
                  {t(labels[key])}
                </label>
              ))}
            </div>
            <ProfileFields
              content={sections}
              onChange={review.edit}
              tags={tags}
              identity={false}
              sections={selected}
            />
            {review.uncertainFields.map((f, i) => (
              <p className="help" key={i}>
                {t(labels[f.field])}: {t(f.status.replaceAll('_', ' '))} —{' '}
                {translateDiagnostic(language, f.reason)}
              </p>
            ))}
            <ErrorNotice error={error} />
            <label className="check-label">
              <input
                type="checkbox"
                checked={review.acknowledged}
                onChange={(e) => review.acknowledge(e.target.checked)}
              />
              {t(
                'I understand that importing replaces the selected sections in my profile and requires a separate confirmation.'
              )}
            </label>
            <div className="actions">
              <Button variant="secondary" disabled={busy} onClick={close}>
                {t('Cancel')}
              </Button>
              <Button type="submit" disabled={!review.canApply}>
                {busy ? t('Importing…') : t('Apply reviewed sections')}
              </Button>
            </div>
            {(uncertain || error?.code === 'REVISION_CONFLICT') && (
              <Notice>
                <p>
                  {uncertain
                    ? t(
                        'The request may have succeeded. Reload the latest data and check it before trying again.'
                      )
                    : t(
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
