import React, { useEffect, useState } from 'react';
import { api } from '../../api/client.js';
import { Button, ErrorNotice, Icon, Loading, Notice } from '../../shared/ui.jsx';
import { useResource, useUnsaved } from '../../shared/hooks.js';
import { labels } from '../../shared/profile-labels.js';

export default function PrivacyPage({ onDirty, notify }) {
  const resource = useResource(api.privacy);
  const [value, setValue] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (resource.data) setValue(structuredClone(resource.data));
  }, [resource.data]);
  const dirty = !!value && JSON.stringify(value) !== JSON.stringify(resource.data);
  useEffect(() => {
    onDirty(dirty);
    return () => onDirty(false);
  }, [dirty]);
  useUnsaved(dirty);
  if (resource.loading || (!value && !resource.error)) return <Loading />;
  if (resource.error) return <ErrorNotice error={resource.error} retry={resource.refresh} />;
  async function save() {
    setBusy(true);
    setError(null);
    try {
      await api.savePrivacy({
        expectedRevision: value.revision,
        discoverable: value.discoverable,
        visibleFields: value.visibleFields,
      });
      notify('Privacy settings saved. Future team results use these choices.');
      resource.refresh();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="narrow-content">
      <div className="section-title">
        <div>
          <h2>Your profile. Your choice.</h2>
          <p>Choose whether research teams can discover you and what they can see.</p>
        </div>
      </div>
      <ErrorNotice
        error={error}
        retry={
          error?.code === 'REVISION_CONFLICT'
            ? () => {
                if (window.confirm('Reload and discard your unsaved privacy changes?')) {
                  setError(null);
                  resource.refresh();
                }
              }
            : undefined
        }
      />
      <section className="panel privacy-hero">
        <span className="aside-icon">
          <Icon name="shield" size={28} />
        </span>
        <div>
          <h3>Allow teams to discover me</h3>
          <p>
            Enable discovery to appear in matching talent lists. Your profile must also be
            confirmed.
          </p>
        </div>
        <label className="switch">
          <input
            aria-label="Allow teams to discover me"
            type="checkbox"
            checked={value.discoverable}
            onChange={(e) => setValue({ ...value, discoverable: e.target.checked })}
          />
          <span />
        </label>
      </section>
      <section className="panel">
        <h3>Choose what you share</h3>
        <p className="muted">
          Only selected fields can appear in team results or influence their scores.
        </p>
        <div className="visibility-grid">
          {Object.entries(labels).map(([field, label]) => (
            <label className="visibility-option" key={field}>
              <input
                type="checkbox"
                checked={value.visibleFields.includes(field)}
                onChange={(e) =>
                  setValue({
                    ...value,
                    visibleFields: e.target.checked
                      ? [...value.visibleFields, field]
                      : value.visibleFields.filter((f) => f !== field),
                  })
                }
              />
              <span>{label}</span>
            </label>
          ))}
        </div>
      </section>
      <Notice>
        <strong>Original documents always stay private.</strong>
        <p>
          Teams never receive your uploaded CV, transcript, login email or document source
          information. Your personal recommendations still work when discovery is off.
        </p>
      </Notice>
      <div className="actions">
        <Button disabled={busy || !dirty} onClick={save}>
          {busy ? 'Saving…' : 'Save privacy settings'}
        </Button>
      </div>
    </div>
  );
}
