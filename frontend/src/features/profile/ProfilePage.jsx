import React, { useEffect, useState } from 'react';
import { api } from '../../api/client.js';
import { Badge, Button, ErrorNotice, Icon, Loading, Notice } from '../../shared/ui.jsx';
import { useResource, usePageGuard } from '../../shared/hooks.js';
import { useMutation } from '../../shared/useMutation.js';
import ProfileFields from '../profile/ProfileFields.jsx';

export default function ProfilePage({
  tags,
  onDirty,
  onPending,
  notify,
  navigate,
  canRecommend = true,
}) {
  const [profile, setProfile] = useState(null);
  const [content, setContent] = useState(null);
  const { error, clearError, busy, run, isPending } = useMutation();
  const [reviewed, setReviewed] = useState(false);
  const dirty = !!profile && JSON.stringify(profile.content) !== JSON.stringify(content);
  const resource = useResource(api.profile, [], !dirty && !busy);
  const conflict = error?.code === 'REVISION_CONFLICT';
  useEffect(() => {
    if (resource.data) {
      setProfile(resource.data);
      setContent(structuredClone(resource.data.content));
      setReviewed(false);
      clearError();
    }
  }, [resource.data, clearError]);
  usePageGuard(dirty, busy, onDirty, onPending);
  function refresh() {
    if (isPending()) return;
    if (dirty && !window.confirm('Reload and discard your unsaved edits?')) return;
    clearError();
    resource.refresh();
  }
  function save(e) {
    e.preventDefault();
    if (isPending() || !dirty) return;
    clearError();
    run(
      () => api.saveProfile(profile.revision, content),
      (next) => {
        setProfile(next);
        setContent(structuredClone(next.content));
        setReviewed(false);
        notify('Profile saved. Review and confirm to use the latest information.');
      }
    );
  }
  function confirm() {
    if (isPending() || dirty || !reviewed || conflict) return;
    clearError();
    run(
      () => api.confirm(profile.revision),
      (next) => {
        setProfile(next);
        notify('Profile confirmed. Your recommendations are ready.');
      }
    );
  }
  if (resource.loading || (!content && !resource.error)) return <Loading />;
  if (resource.error) return <ErrorNotice error={resource.error} retry={refresh} />;
  const confirmed =
    profile.confirmation.status === 'CONFIRMED' &&
    profile.confirmation.confirmedRevision === profile.revision;
  return (
    <form onSubmit={save}>
      <div className="section-title">
        <div>
          <h2>Tell your research story</h2>
          <p>Your background, interests and evidence, all in one place.</p>
        </div>
        <div className="profile-status">
          <Badge status={!dirty && confirmed ? 'CONFIRMED' : 'UNCONFIRMED'}>
            {dirty ? 'Unsaved changes' : confirmed ? 'Confirmed' : 'Needs confirmation'}
          </Badge>
          <small className="muted">Saved profile revision {profile.revision}</small>
          <Button variant="text" disabled={busy} onClick={refresh}>
            Refresh profile
          </Button>
        </div>
      </div>
      <ErrorNotice error={error} retry={conflict ? refresh : undefined} />
      {dirty && (
        <Notice>
          Unsaved profile changes are not used for matching. Save, review and confirm the updated
          profile.
        </Notice>
      )}
      {conflict && (
        <Notice>
          Refresh the latest saved profile before confirming. Your local edits have been kept.
        </Notice>
      )}
      <fieldset className="form-fields editor-layout" disabled={busy}>
        <ProfileFields
          content={content}
          onChange={(next) => {
            if (!isPending()) setContent(next);
          }}
          tags={tags}
        />
        <aside className="editor-aside">
          <div className="panel sticky-panel">
            <span className="aside-icon">
              <Icon name="shield" size={26} />
            </span>
            <h3>Reviewed by you.</h3>
            <p className="muted">
              Only the current confirmed version is used for matching. Editing your profile means
              reviewing it again.
            </p>
            <Button type="submit" className="full" disabled={busy || !dirty}>
              {busy ? 'Saving…' : 'Save changes'}
            </Button>
            <div className="review-divider" />
            {confirmed && !dirty ? (
              <Notice tone="success">This version is confirmed.</Notice>
            ) : (
              <>
                <label className="check-label">
                  <input
                    type="checkbox"
                    checked={reviewed}
                    disabled={dirty || conflict}
                    onChange={(e) => setReviewed(e.target.checked)}
                  />
                  I have reviewed my saved profile and confirm it reflects my information.
                </label>
                <Button
                  className="full"
                  variant="secondary"
                  disabled={busy || dirty || !reviewed || conflict}
                  onClick={confirm}
                >
                  Confirm profile
                </Button>
              </>
            )}
            {canRecommend && (
              <Button variant="text" className="full" onClick={() => navigate('recommendations')}>
                See recommendations
                <Icon name="arrow" size={16} />
              </Button>
            )}
            <small className="muted">
              Confirmation records your review. It does not verify academic credentials.
            </small>
          </div>
        </aside>
      </fieldset>
    </form>
  );
}
