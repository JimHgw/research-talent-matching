import { useLanguage } from '../../shared/i18n.jsx';
import React from 'react';
import { Badge, Button, ErrorNotice, Icon, Loading, Notice } from '../../shared/ui.jsx';
import EditorRecovery from '../../shared/EditorRecovery.jsx';
import { useProfileEditor } from './useProfileEditor.js';
import ProfileSummary from './ProfileSummary.jsx';
import ProfileFields from '../profile/ProfileFields.jsx';

export default function ProfilePage({
  tags,
  onDirty,
  onPending,
  notify,
  navigate,
  canRecommend = true,
}) {
  const { t } = useLanguage();
  const editor = useProfileEditor({
    onDirty,
    onPending,
    notify,
    confirmDiscard: () => window.confirm(t('Reload and discard your unsaved edits?')),
  });
  const {
    profile,
    content,
    error,
    busy,
    dirty,
    reviewed,
    confirmed,
    refresh,
    save,
    confirm,
    needsReview,
  } = editor;
  const conflict = error?.code === 'REVISION_CONFLICT';
  if (editor.loading) return <Loading />;
  if (editor.unavailable || !content)
    return <ErrorNotice error={editor.unavailable || editor.readError} retry={refresh} />;
  return (
    <form onSubmit={save}>
      <div className="section-title">
        <div>
          <h2>{t('Tell your research story')}</h2>
          <p>{t('Your background, interests and evidence, all in one place.')}</p>
        </div>
        <div className="profile-status">
          <Badge status={!dirty && confirmed ? 'CONFIRMED' : 'UNCONFIRMED'}>
            {dirty ? t('Unsaved changes') : confirmed ? t('Confirmed') : t('Needs confirmation')}
          </Badge>
          <small className="muted">
            {t('Saved profile revision {revision}', { revision: profile.revision })}
          </small>
          <Button variant="text" disabled={busy} onClick={refresh}>
            {t('Refresh profile')}
          </Button>
        </div>
      </div>
      <EditorRecovery
        editor={editor}
        renderVersion={(value) => <ProfileSummary content={value} tags={tags} />}
      />
      {dirty && (
        <Notice>
          {t(
            'Unsaved profile changes are not used for matching. Save, review and confirm the updated profile.'
          )}
        </Notice>
      )}
      {conflict && (
        <Notice>
          {t(
            'Refresh the latest saved profile before confirming. Your local edits have been kept.'
          )}
        </Notice>
      )}
      <fieldset className="form-fields editor-layout" disabled={busy}>
        <ProfileFields content={content} onChange={editor.change} tags={tags} />
        <aside className="editor-aside">
          <div className="panel sticky-panel">
            <span className="aside-icon">
              <Icon name="shield" size={26} />
            </span>
            <h3>{t('Reviewed by you.')}</h3>
            <p className="muted">
              {t(
                'Only the current confirmed version is used for matching. Editing your profile means reviewing it again.'
              )}
            </p>
            <Button type="submit" className="full" disabled={busy || !dirty || needsReview}>
              {busy ? t('Saving…') : t('Save changes')}
            </Button>
            <div className="review-divider" />
            {confirmed && !dirty ? (
              <Notice tone="success">{t('This version is confirmed.')}</Notice>
            ) : (
              <>
                <label className="check-label">
                  <input
                    type="checkbox"
                    checked={reviewed}
                    disabled={dirty || needsReview}
                    onChange={(e) => editor.setReviewed(e.target.checked)}
                  />
                  {t('I have reviewed my saved profile and confirm it reflects my information.')}
                </label>
                <Button
                  className="full"
                  variant="secondary"
                  disabled={busy || dirty || !reviewed || needsReview}
                  onClick={confirm}
                >
                  {t('Confirm profile')}
                </Button>
              </>
            )}
            {canRecommend && (
              <Button variant="text" className="full" onClick={() => navigate('recommendations')}>
                {t('See recommendations')}
                <Icon name="arrow" size={16} />
              </Button>
            )}
            <small className="muted">
              {t('Confirmation records your review. It does not verify academic credentials.')}
            </small>
          </div>
        </aside>
      </fieldset>
    </form>
  );
}
