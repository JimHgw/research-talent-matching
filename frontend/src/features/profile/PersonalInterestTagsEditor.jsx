import { useLanguage } from '../../shared/i18n.jsx';
import React from 'react';
import { Button } from '../../shared/ui.jsx';

export default function PersonalInterestTagsEditor({ value, onChange }) {
  const { t } = useLanguage();
  return (
    <div className="record-list">
      {value.map((tag, index) => (
        <div className="record" key={tag.id || index}>
          <label>
            <span>{t('Personal interest label')}</span>
            <input
              value={tag.label}
              maxLength={100}
              required
              onChange={(event) =>
                onChange(
                  value.map((item, i) =>
                    i === index ? { ...item, label: event.target.value } : item
                  )
                )
              }
            />
          </label>
          <Button variant="text" onClick={() => onChange(value.filter((_, i) => i !== index))}>
            {t('Remove personal interest')}
          </Button>
        </div>
      ))}
      <Button
        variant="secondary"
        disabled={value.length >= 100}
        onClick={() => onChange([...value, { label: '' }])}
      >
        {t('Add personal interest')}
      </Button>
    </div>
  );
}
