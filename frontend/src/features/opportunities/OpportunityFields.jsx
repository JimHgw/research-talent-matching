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
  const set = (key, value) => onChange({ ...content, [key]: value });
  return (
    <>
      <section className="panel">
        <h3>Opportunity details</h3>
        <div className="opportunity-fields">
          {opportunityFields.map(({ key, label, maxLength, multiline }) => (
            <div key={key} className={multiline ? 'opportunity-wide' : undefined}>
              <Field label={label + (requiredLabels ? ' *' : '')}>
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
          <Field label="Discipline group">
            <select
              value={content.disciplineGroup}
              onChange={(e) => set('disciplineGroup', e.target.value)}
            >
              <option value="STEM">STEM</option>
              <option value="BUSINESS">Business</option>
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
          ? 'Saved changes will be visible immediately. Published opportunities must keep at least one requirement.'
          : 'Drafts are visible only to your team. Save your changes before publishing.'}
      </Notice>
    </>
  );
}
