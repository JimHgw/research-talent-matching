import { useLanguage } from '../../shared/i18n.jsx';
import React from 'react';
import { Button, ErrorNotice, Icon, Loading, Notice } from '../../shared/ui.jsx';
import { usePrivacyEditor } from './usePrivacyEditor.js';
import PrivacySummary from './PrivacySummary.jsx';
import EditorRecovery from '../../shared/EditorRecovery.jsx';
import { labels } from '../../shared/profile-labels.js';
import { privacyFields } from './fields.js';

export default function PrivacyPage({ onDirty, onPending, notify }) {
  const { t } = useLanguage();
  const editor = usePrivacyEditor({
    onDirty,
    onPending,
    notify,
    confirmDiscard: () => window.confirm(t('Reload and discard your unsaved privacy changes?')),
  });
  const {
    content: value,
    change: setValue,
    saved: baseline,
    busy,
    dirty,
    refresh,
    save,
    needsReview,
  } = editor;
  if (editor.loading) return <Loading />;
  if (editor.unavailable || !value)
    return <ErrorNotice error={editor.unavailable || editor.readError} retry={refresh} />;
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
      <EditorRecovery
        editor={editor}
        renderVersion={(snapshot) => <PrivacySummary value={snapshot} />}
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
          <Button disabled={busy || !dirty || needsReview} onClick={save}>
            {busy ? t('Saving…') : t('Save privacy settings')}
          </Button>
        </div>
      </fieldset>
    </div>
  );
}
