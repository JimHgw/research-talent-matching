import { useLanguage } from '../../shared/i18n.jsx';
import React, { useEffect, useState } from 'react';
import { api } from '../../api/client.js';
import { Button, ErrorNotice, Icon, Loading, Notice } from '../../shared/ui.jsx';
import { useResource, usePageGuard } from '../../shared/hooks.js';
import { useMutation } from '../../shared/useMutation.js';
import { labels } from '../../shared/profile-labels.js';
import { privacyFields } from './fields.js';

export default function PrivacyPage({ onDirty, onPending, notify }) {
  const { t } = useLanguage();
  const [value, setValue] = useState(null);
  const { error, clearError, busy, run, isPending } = useMutation();
  const [baseline, setBaseline] = useState(null);
  const dirty = !!value && JSON.stringify(value) !== JSON.stringify(baseline);
  const resource = useResource(api.privacy, [], !dirty && !busy);
  useEffect(() => {
    if (resource.data) {
      setValue(structuredClone(resource.data));
      setBaseline(resource.data);
      clearError();
    }
  }, [resource.data, clearError]);
  usePageGuard(dirty, busy, onDirty, onPending);
  function refresh() {
    if (isPending()) return;
    if (dirty && !window.confirm(t('Reload and discard your unsaved privacy changes?'))) return;
    clearError();
    resource.refresh();
  }
  if (resource.loading || (!value && !resource.error)) return <Loading />;
  if (resource.error) return <ErrorNotice error={resource.error} retry={refresh} />;
  function save() {
    if (isPending() || !dirty) return;
    clearError();
    run(
      () =>
        api.savePrivacy({
          expectedRevision: value.revision,
          discoverable: value.discoverable,
          visibleFields: value.visibleFields,
        }),
      (saved) => {
        setValue(structuredClone(saved));
        setBaseline(saved);
        notify('Privacy settings saved. Future team results use these choices.');
      }
    );
  }
  return (
    <div className="narrow-content">
      <div className="section-title">
        <div>
          <h2>{t('Your profile. Your choice.')}</h2>
          <p>{t('Choose whether research teams can discover you and what they can see.')}</p>
        </div>
        <Button variant="text" disabled={busy} onClick={refresh}>
          {t('Refresh privacy settings')}
        </Button>
      </div>
      <Notice>
        <strong>
          {t('Saved discovery status: {status}', {
            status: t(baseline.discoverable ? 'On' : 'Off'),
          })}
        </strong>
        <p>
          {baseline.discoverable
            ? t(
                'Teams can discover your current confirmed profile using only the saved visible fields.'
              )
            : t(
                'Your profile is excluded from team discovery. Your own recommendations remain available after confirmation.'
              )}
        </p>
      </Notice>
      {dirty && (
        <Notice>
          {t(
            'Unsaved privacy changes do not affect team access. Save privacy settings to apply them.'
          )}
        </Notice>
      )}
      <ErrorNotice
        error={error}
        retry={error?.code === 'REVISION_CONFLICT' ? refresh : undefined}
      />
      <fieldset className="form-fields" disabled={busy}>
        <section className="panel privacy-hero">
          <span className="aside-icon">
            <Icon name="shield" size={28} />
          </span>
          <div>
            <h3>{t('Allow teams to discover me')}</h3>
            <p>
              {t(
                'Enable discovery to appear in matching talent lists. Your profile must also be confirmed.'
              )}
            </p>
          </div>
          <label className="switch">
            <input
              aria-label={t('Allow teams to discover me')}
              type="checkbox"
              checked={value.discoverable}
              onChange={(e) => setValue({ ...value, discoverable: e.target.checked })}
            />
            <span />
          </label>
        </section>
        <section className="panel">
          <h3>{t('Choose what you share')}</h3>
          <p className="muted">
            {t('Only selected fields can appear in team results or influence their scores.')}
          </p>
          <div className="visibility-grid">
            {privacyFields.map((field) => (
              <label className="visibility-option" key={field}>
                <input
                  type="checkbox"
                  value={field}
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
                <span>{t(labels[field])}</span>
              </label>
            ))}
          </div>
          <p className="help">
            {t(
              'Research interests also controls your research interest description and personal interest tags. Your resume description always stays private.'
            )}
          </p>
        </section>
        <Notice>
          <strong>{t('Original documents always stay private.')}</strong>
          <p>
            {t(
              'Teams never receive your uploaded CV, transcript, login email or document source information. Your personal recommendations still work when discovery is off.'
            )}
          </p>
        </Notice>
        <div className="actions">
          <Button disabled={busy || !dirty} onClick={save}>
            {busy ? t('Saving…') : t('Save privacy settings')}
          </Button>
        </div>
      </fieldset>
    </div>
  );
}
