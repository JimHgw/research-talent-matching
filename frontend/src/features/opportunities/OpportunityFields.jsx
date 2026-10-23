import { useLanguage } from '../../shared/i18n.jsx';
import React from 'react';
import { Field, Notice } from '../../shared/ui.jsx';
import { opportunityFields } from './fields.js';
import RequirementEditor from './RequirementEditor.jsx';

export default function OpportunityFields({
  content,
  onChange,
  tags,
  status,
  requiredLabels = false,
}) {
  const { t } = useLanguage();
  const set = (key, value) => onChange({ ...content, [key]: value });
  return (
    <>
      <section className="panel">
        <h3>{t('Opportunity details')}</h3>
        <div className="opportunity-fields">
          {opportunityFields.map(({ key, label, maxLength, multiline }) => (
            <div key={key} className={multiline ? 'opportunity-wide' : undefined}>
              <Field label={t(label) + (requiredLabels ? ' *' : '')}>
                {multiline ? (
                  <textarea
                    required
                    rows={6}
                    maxLength={maxLength}
                    value={content[key]}
                    onChange={(e) => set(key, e.target.value)}
                  />
                ) : (
                  <input
                    required
                    maxLength={maxLength}
                    value={content[key]}
                    onChange={(e) => set(key, e.target.value)}
                  />
                )}
              </Field>
            </div>
          ))}
          <Field label={t('Discipline group')}>
            <select
              value={t(content.disciplineGroup)}
              onChange={(e) => set('disciplineGroup', e.target.value)}
            >
              <option value="STEM">{t('STEM')}</option>
              <option value="BUSINESS">{t('Business')}</option>
            </select>
          </Field>
        </div>
      </section>
      <section className="panel">
        <RequirementEditor
          value={content.requirements}
          tags={tags}
          onChange={(requirements) => set('requirements', requirements)}
          numberedLabels={!requiredLabels}
        />
      </section>
      <Notice>
        {status === 'PUBLISHED'
          ? t(
              'Saved changes will be visible immediately. Published opportunities must keep at least one requirement.'
            )
          : t('Drafts are visible only to your team. Save your changes before publishing.')}
      </Notice>
    </>
  );
}
