import React from 'react';
import { Field } from '../../shared/ui.jsx';

export default function IdentityFields({ content, onChange }) {
  return (
    <section className="panel">
      <div className="section-heading">
        <span className="section-number">01</span>
        <h3>The basics</h3>
      </div>
      <div className="form-grid">
        <Field label="Display name">
          <input
            maxLength={100}
            value={content.displayName}
            onChange={(e) => onChange({ displayName: e.target.value })}
            placeholder="Your name"
          />
        </Field>
        <Field label="Discipline group">
          <select
            value={content.disciplineGroup || ''}
            onChange={(e) => onChange({ disciplineGroup: e.target.value || null })}
          >
            <option value="">Choose a group</option>
            <option value="STEM">STEM</option>
            <option value="BUSINESS">Business</option>
          </select>
        </Field>
      </div>
    </section>
  );
}
