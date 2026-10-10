import React from 'react';
import { Button, Field, Icon } from '../../shared/ui.jsx';

export default function SkillsEditor({ value, onChange, tags }) {
  const skills = tags.filter((tag) => tag.kind === 'SKILL');
  const available = skills.find((tag) => !value.some((skill) => skill.tagId === tag.id));
  const update = (index, patch) =>
    onChange(value.map((skill, i) => (i === index ? { ...skill, ...patch } : skill)));
  return (
    <>
      <p className="help">
        Add skills you can support. Only use “Not yet” when you explicitly know you do not have that
        skill.
      </p>
      {value.map((skill, index) => (
        <div className="record" key={index}>
          <div className="form-grid skill-grid">
            <Field label="Skill">
              <select
                value={skill.tagId}
                onChange={(e) => update(index, { tagId: e.target.value })}
              >
                {skills.map((tag) => (
                  <option
                    key={tag.id}
                    value={tag.id}
                    disabled={value.some((other, i) => i !== index && other.tagId === tag.id)}
                  >
                    {tag.label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Your experience">
              <select
                value={skill.claim}
                onChange={(e) => update(index, { claim: e.target.value })}
              >
                <option value="HAS">I have this skill</option>
                <option value="DOES_NOT_HAVE">Not yet — explicit gap</option>
              </select>
            </Field>
            <Button
              variant="icon"
              aria-label={`Remove skill ${index + 1}`}
              onClick={() => onChange(value.filter((_, i) => i !== index))}
            >
              <Icon name="close" />
            </Button>
          </div>
          <Field label="Supporting evidence">
            <textarea
              rows={2}
              maxLength={2000}
              placeholder="A project, course, or experience that supports your statement"
              value={skill.evidenceText}
              onChange={(e) => update(index, { evidenceText: e.target.value })}
            />
          </Field>
        </div>
      ))}
      <Button
        variant="secondary"
        disabled={!available || value.length >= 100}
        onClick={() =>
          onChange([...value, { tagId: available.id, claim: 'HAS', evidenceText: '' }])
        }
      >
        <Icon name="plus" size={16} />
        Add skill
      </Button>
    </>
  );
}
