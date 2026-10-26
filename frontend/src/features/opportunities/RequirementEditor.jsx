import { academicFields, requirementKinds, outputTypes } from './academic.js';
import { useLanguage } from '../../shared/i18n.jsx';
import React from 'react';
import { Button, Field } from '../../shared/ui.jsx';
import { limits, newRequirement } from './fields.js';

export default function RequirementEditor({ value, onChange, tags, numberedLabels = true }) {
  const { t } = useLanguage();
  function update(id, patch) {
    onChange(value.map((row) => (row.id === id ? { ...row, ...patch } : row)));
  }
  return (
    <section className="opportunity-requirements">
      <h3>{t('Requirements')}</h3>
      <p className="muted">
        {t(
          'Enter skill names, one per line. Research interests use shared tags. Add at least one requirement before publishing.'
        )}
      </p>
      {value.map((row, index) => (
        <fieldset className="requirement-card" key={row.id}>
          <legend>{t('Requirement {number}', { number: index + 1 })}</legend>
          <Field
            label={
              numberedLabels
                ? t('Requirement {number} label', { number: index + 1 })
                : t('Requirement label *')
            }
          >
            <input
              required
              maxLength={limits.requirementLabel}
              value={row.label}
              onChange={(e) => update(row.id, { label: e.target.value })}
            />
          </Field>
          <div className="opportunity-fields">
            <Field
              label={
                numberedLabels ? t('Requirement {number} kind', { number: index + 1 }) : t('Kind')
              }
            >
              <select
                value={row.kind}
                onChange={(e) => {
                  const { skillTitles, criteria, ...rest } = row;
                  onChange(
                    value.map((item) =>
                      item.id === row.id
                        ? {
                            ...rest,
                            kind: e.target.value,
                            tagIds: [],
                            ...(e.target.value === 'SKILL' ? { skillTitles: [] } : {}),
                            ...(academicFields[e.target.value] ? { criteria: {} } : {}),
                          }
                        : item
                    )
                  );
                }}
              >
                {Object.entries(requirementKinds).map(([kind, label]) => (
                  <option key={kind} value={kind}>
                    {t(label)}
                  </option>
                ))}
              </select>
            </Field>
            <Field
              label={
                numberedLabels
                  ? t('Requirement {number} importance', { number: index + 1 })
                  : t('Importance')
              }
            >
              <select
                value={row.importance}
                onChange={(e) => update(row.id, { importance: e.target.value })}
              >
                <option value="REQUIRED">{t('Required')}</option>
                <option value="PREFERRED">{t('Preferred')}</option>
              </select>
            </Field>
          </div>
          {academicFields[row.kind] ? (
            <div className="opportunity-fields">
              {academicFields[row.kind].map((field) => {
                const value = row.criteria?.[field.key] || '';
                function setCriterion(next) {
                  const criteria = { ...row.criteria };
                  if (next === '') delete criteria[field.key];
                  else criteria[field.key] = next;
                  update(row.id, { criteria });
                }
                return (
                  <Field key={field.key} label={t(field.label)}>
                    {field.options ? (
                      <select value={value} onChange={(e) => setCriterion(e.target.value)}>
                        <option value="">—</option>
                        {field.options.map((option) => (
                          <option key={option} value={option}>
                            {t(outputTypes[option])}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <input
                        maxLength={field.maxLength}
                        value={value}
                        onChange={(e) => setCriterion(e.target.value)}
                      />
                    )}
                  </Field>
                );
              })}
              <p className="muted">
                {t('Complete at least one criterion. Matches use the exact text.')}
              </p>
            </div>
          ) : row.kind === 'SKILL' ? (
            <Field label={t('Skill names for requirement {number}', { number: index + 1 })}>
              <textarea
                required
                rows={3}
                placeholder={t('Python\nFinancial modelling')}
                value={(
                  row.skillTitles ||
                  row.tagIds.map((id) => tags.find((tag) => tag.id === id)?.label || id)
                ).join('\n')}
                onChange={(e) =>
                  update(row.id, { skillTitles: e.target.value.split('\n'), tagIds: [] })
                }
              />
            </Field>
          ) : (
            <fieldset className="requirement-tags">
              <legend>
                {t('Tags for requirement {number} ({count}/{limit})', {
                  number: index + 1,
                  count: row.tagIds.length,
                  limit: limits.tags,
                })}
              </legend>
              <div className="opportunity-tag-options">
                {tags
                  .filter((tag) => tag.kind === row.kind)
                  .map((tag) => (
                    <label key={tag.id}>
                      <input
                        type="checkbox"
                        checked={row.tagIds.includes(tag.id)}
                        disabled={!row.tagIds.includes(tag.id) && row.tagIds.length >= limits.tags}
                        onChange={(e) =>
                          update(row.id, {
                            tagIds: e.target.checked
                              ? [...row.tagIds, tag.id]
                              : row.tagIds.filter((id) => id !== tag.id),
                          })
                        }
                      />
                      <span>{tag.label}</span>
                    </label>
                  ))}
              </div>
              {!tags.some((tag) => tag.kind === row.kind) && (
                <p>{t('No tags available for this kind.')}</p>
              )}
            </fieldset>
          )}
          <div className="actions">
            <Button
              variant="text"
              aria-label={t('Remove requirement {number}', { number: index + 1 })}
              onClick={() => onChange(value.filter((item) => item.id !== row.id))}
            >
              {t('Remove requirement {number}', { number: index + 1 })}
            </Button>
          </div>
        </fieldset>
      ))}
      <Button
        variant="secondary"
        disabled={value.length >= limits.requirements}
        onClick={() => onChange([...value, newRequirement()])}
      >
        {t('Add requirement')}
      </Button>
    </section>
  );
}
