import { useLanguage } from '../../shared/i18n.jsx';
import React from 'react';
import { Button, Field, Icon } from '../../shared/ui.jsx';
import { labels } from '../../shared/profile-labels.js';
import { fieldConfigs, createRecord, recordValue } from './fields.js';

export default function RecordSection({ section, value, onChange }) {
  const { t } = useLanguage();
  const update = (id, field, next) =>
    onChange(value.map((row) => (row.id === id ? { ...row, [field]: next } : row)));
  return (
    <>
      {value.map((row, index) => (
        <div className="record" key={row.id}>
          <div className="record-heading">
            <strong>{t('Record {number}', { number: index + 1 })}</strong>
            <Button
              variant="icon"
              aria-label={t('Remove {section} record {number}', {
                section: t(labels[section]),
                number: index + 1,
              })}
              onClick={() => onChange(value.filter((item) => item.id !== row.id))}
            >
              <Icon name="close" size={17} />
            </Button>
          </div>
          <div className="form-grid">
            {fieldConfigs[section].map(([field, label, type, required]) => (
              <Field key={field} label={t(label) + (required ? ' *' : '')}>
                {type === 'outputType' ? (
                  <select
                    value={row[field]}
                    onChange={(e) => update(row.id, field, e.target.value)}
                  >
                    <option value="PUBLICATION">{t('Publication')}</option>
                    <option value="PROJECT">{t('Project')}</option>
                    <option value="OTHER">{t('Other')}</option>
                  </select>
                ) : (
                  React.createElement(type === 'textarea' ? 'textarea' : 'input', {
                    type: type === 'textarea' ? undefined : type,
                    rows: type === 'textarea' ? 3 : undefined,
                    required,
                    maxLength:
                      field === 'url'
                        ? undefined
                        : type === 'textarea'
                          ? 5000
                          : field === 'title' && section === 'researchOutputs'
                            ? 300
                            : 200,
                    min: type === 'number' ? 1900 : undefined,
                    max: type === 'number' ? 2200 : undefined,
                    value: row[field] ?? '',
                    onChange: (e) =>
                      update(row.id, field, recordValue(field, type, e.target.value)),
                  })
                )}
              </Field>
            ))}
          </div>
        </div>
      ))}
      <Button
        variant="secondary"
        disabled={value.length >= 100}
        onClick={() => onChange([...value, createRecord(section)])}
      >
        <Icon name="plus" size={16} />
        {t('Add {section}', { section: t(labels[section]).toLowerCase() })}
      </Button>
    </>
  );
}
