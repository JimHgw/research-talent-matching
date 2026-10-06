import React, { useEffect, useState } from 'react';
import { api } from '../../api/client.js';
import { Badge, Button, ErrorNotice, Icon, Loading, Notice } from '../../shared/ui.jsx';
import { useResource, useUnsaved } from '../../shared/hooks.js';
import ProfileFields from '../profile/ProfileFields.jsx';

export default function ProfilePage({ tags, onDirty, notify, navigate, canRecommend = true }) {
  const resource = useResource(api.profile);
  const [profile, setProfile] = useState(null);
  const [content, setContent] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [reviewed, setReviewed] = useState(false);
  useEffect(() => {
    if (resource.data) {
      setProfile(resource.data);
      setContent(structuredClone(resource.data.content));
      setReviewed(false);
    }
  }, [resource.data]);
  const dirty = !!profile && JSON.stringify(profile.content) !== JSON.stringify(content);
  useEffect(() => {
    onDirty(dirty);
    return () => onDirty(false);
  }, [dirty]);
  useUnsaved(dirty);
  async function save(e) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const next = await api.saveProfile(profile.revision, content);
      setProfile(next);
      setContent(structuredClone(next.content));
      setReviewed(false);
      notify('Profile saved. Review and confirm to use the latest information.');
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  async function confirm() {
    setBusy(true);
    setError(null);
    try {
      const next = await api.confirm(profile.revision);
      setProfile(next);
      notify('Profile confirmed. Your recommendations are ready.');
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  if (resource.loading || (!content && !resource.error)) return <Loading />;
  if (resource.error) return <ErrorNotice error={resource.error} retry={resource.refresh} />;
  const confirmed = profile.confirmation.status === 'CONFIRMED';
  return (
    <form onSubmit={save}>
      <div className="section-title">
        <div>
          <h2>Tell your research story</h2>
          <p>Your background, interests and evidence, all in one place.</p>
        </div>
        <Badge status={dirty ? 'UNCONFIRMED' : profile.confirmation.status}>
          {dirty ? 'Unsaved changes' : confirmed ? 'Confirmed' : 'Needs confirmation'}
        </Badge>
      </div>
      <ErrorNotice
        error={error}
        retry={
          error?.code === 'REVISION_CONFLICT'
            ? () => {
                if (!dirty || window.confirm('Reload and discard your unsaved edits?')) {
                  setError(null);
                  resource.refresh();
                }
              }
            : undefined
        }
      />
      <div className="editor-layout">
        <ProfileFields content={content} onChange={setContent} tags={tags} />
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
                    disabled={dirty}
                    onChange={(e) => setReviewed(e.target.checked)}
                  />
                  I have reviewed my saved profile and confirm it reflects my information.
                </label>
                <Button
                  className="full"
                  variant="secondary"
                  disabled={busy || dirty || !reviewed}
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
      </div>
    </form>
  );
}
