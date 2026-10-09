import React from 'react';
import { labels } from '../../shared/profile-labels.js';
import { profileSections } from './fields.js';
import IdentityFields from './IdentityFields.jsx';
import RecordSection from './RecordSection.jsx';
import SkillsEditor from './SkillsEditor.jsx';
import ResearchInterestsEditor from './ResearchInterestsEditor.jsx';

export default function ProfileFields({
  content,
  onChange,
  tags,
  sections = profileSections,
  identity = true,
}) {
  const set = (key, value) => onChange({ ...content, [key]: value });
  return (
    <div className="profile-fields">
      {identity && (
        <IdentityFields
          content={content}
          onChange={(patch) => onChange({ ...content, ...patch })}
        />
      )}
      {sections.map((section, index) => {
        const value = content[section] || [];
        const props = { value, tags, onChange: (next) => set(section, next) };
        return (
          <section className="panel" key={section}>
            <div className="section-heading">
              <span className="section-number">
                {String(index + (identity ? 2 : 1)).padStart(2, '0')}
              </span>
              <h3>{labels[section]}</h3>
              <span className="muted count">{value.length} entries</span>
            </div>
            {section === 'skills' ? (
              <SkillsEditor {...props} />
            ) : section === 'researchInterests' ? (
              <ResearchInterestsEditor {...props} />
            ) : (
              <RecordSection section={section} {...props} />
            )}
          </section>
        );
      })}
    </div>
  );
}
