import { useLanguage } from '../../shared/i18n.jsx';
import React from 'react';
import { Button, Field, Icon } from '../../shared/ui.jsx';

export default function SkillsEditor({ value, onChange }) {
  const { t } = useLanguage();
  const update = (index, patch) =>
    onChange(value.map((skill, i) => (i === index ? { ...skill, ...patch } : skill)));
  return (
    <>
      <p className="help">
        {t('Give each skill a title and describe the experience that supports it.')}
      </p>
      {value.map((skill, index) => (
        <div className="record" key={skill.id}>
          <div className="form-grid skill-grid">
            <Field label={t('Skill title')}>
              <input
                type="text"
                required
                maxLength={350}
                value={skill.title}
                onChange={(e) => update(index, { title: e.target.value })}
              />
            </Field>
            <Button
              variant="icon"
              aria-label={t('Remove skill {number}', { number: index + 1 })}
              onClick={() => onChange(value.filter((_, i) => i !== index))}
            >
              <Icon name="close" />
            </Button>
          </div>
          <Field label={t('Supporting evidence')}>
            <textarea
              rows={2}
              maxLength={2000}
              placeholder={t('A project, course, or experience that supports your statement')}
              value={skill.evidenceText}
              onChange={(e) => update(index, { evidenceText: e.target.value })}
            />
          </Field>
        </div>
      ))}
      <Button
        variant="secondary"
        disabled={value.length >= 100}
        onClick={() =>
          onChange([...value, { id: `record_${crypto.randomUUID()}`, title: '', evidenceText: '' }])
        }
      >
        <Icon name="plus" size={16} />
        {t('Add skill')}
      </Button>
    </>
  );
}
