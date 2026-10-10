import React from 'react';
import { Button, Field } from '../../shared/ui.jsx';
import { limits, newRequirement } from './fields.js';

export default function RequirementEditor({ value, onChange, tags, numberedLabels = true }) {
  function update(id, patch) {
    onChange(value.map((row) => (row.id === id ? { ...row, ...patch } : row)));
  }
  return (
    <section className="opportunity-requirements">
      <h3>Requirements</h3>
      <p className="muted">
        Each requirement uses all its selected tags. Add at least one requirement before publishing.
      </p>
      {value.map((row, index) => (
        <fieldset className="requirement-card" key={row.id}>
          <legend>Requirement {index + 1}</legend>
          <Field label={numberedLabels ? `Requirement ${index + 1} label` : 'Requirement label *'}>
            <input
              required
              maxLength={limits.requirementLabel}
              value={row.label}
              onChange={(e) => update(row.id, { label: e.target.value })}
            />
          </Field>
          <div className="opportunity-fields">
            <Field label={numberedLabels ? `Requirement ${index + 1} kind` : 'Kind'}>
              <select
                value={row.kind}
                onChange={(e) => update(row.id, { kind: e.target.value, tagIds: [] })}
              >
                <option value="SKILL">Skill</option>
                <option value="INTEREST">Research interest</option>
              </select>
            </Field>
            <Field label={numberedLabels ? `Requirement ${index + 1} importance` : 'Importance'}>
              <select
                value={row.importance}
                onChange={(e) => update(row.id, { importance: e.target.value })}
              >
                <option value="REQUIRED">Required</option>
                <option value="PREFERRED">Preferred</option>
              </select>
            </Field>
          </div>
          <fieldset className="requirement-tags">
            <legend>
              Tags for requirement {index + 1} ({row.tagIds.length}/{limits.tags})
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
            {!tags.some((tag) => tag.kind === row.kind) && <p>No tags available for this kind.</p>}
          </fieldset>
          <div className="actions">
            <Button
              variant="text"
              aria-label={`Remove requirement ${index + 1}`}
              onClick={() => onChange(value.filter((item) => item.id !== row.id))}
            >
              Remove requirement {index + 1}
            </Button>
          </div>
        </fieldset>
      ))}
      <Button
        variant="secondary"
        disabled={value.length >= limits.requirements}
        onClick={() => onChange([...value, newRequirement()])}
      >
        Add requirement
      </Button>
    </section>
  );
}
