import { useLanguage } from '../../shared/i18n.jsx';
import React from 'react';
import { Field } from '../../shared/ui.jsx';

export default function IdentityFields({ content, onChange }) {
  const { t } = useLanguage();
  return (
    <section className="panel">
      <div className="section-heading">
        <span className="section-number">01</span>
        <h3>{t('The basics')}</h3>
      </div>
      <div className="form-grid">
        <Field label={t('Display name')}>
          <input
            maxLength={100}
            value={content.displayName}
            onChange={(e) => onChange({ displayName: e.target.value })}
            placeholder={t('Your name')}
          />
        </Field>
        <Field label={t('Discipline group')}>
          <select
            value={content.disciplineGroup || ''}
            onChange={(e) => onChange({ disciplineGroup: e.target.value || null })}
          >
            <option value="">{t('Choose a group')}</option>
            <option value="STEM">{t('STEM')}</option>
            <option value="BUSINESS">{t('Business')}</option>
          </select>
        </Field>
      </div>
    </section>
  );
}
