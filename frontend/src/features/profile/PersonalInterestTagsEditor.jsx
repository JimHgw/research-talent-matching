import { useLanguage } from '../../shared/i18n.jsx';
import React from 'react';
import { Button, Field } from '../../shared/ui.jsx';

export default function PersonalInterestTagsEditor({ value, onChange }) {
  const { t } = useLanguage();
  const update = (index, patch) =>
    onChange(value.map((tag, i) => (i === index ? { ...tag, ...patch } : tag)));
  return (
    <div className="record-list">
      {value.map((tag, index) => (
        <div className="record" key={tag.id || index}>
          <Field label={t('Personal interest label')}>
            <input
              value={tag.label}
              maxLength={100}
              required
              onChange={(event) => update(index, { label: event.target.value })}
            />
          </Field>
          <Field label={t('Personal interest description')}>
            {/* Existing and extracted entries may omit descriptions. */}
            <textarea
              value={tag.description || ''}
              maxLength={5000}
              rows={3}
              required={!tag.id && Object.hasOwn(tag, 'description')}
              onChange={(event) => update(index, { description: event.target.value })}
            />
          </Field>
          <Button variant="text" onClick={() => onChange(value.filter((_, i) => i !== index))}>
            {t('Remove personal interest')}
          </Button>
        </div>
      ))}
      <Button
        variant="secondary"
        disabled={value.length >= 100}
        onClick={() => onChange([...value, { label: '', description: '' }])}
      >
        {t('Add personal interest')}
      </Button>
    </div>
  );
}
