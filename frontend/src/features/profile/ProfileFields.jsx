import { useLanguage } from '../../shared/i18n.jsx';
import React from 'react';
import { labels } from '../../shared/profile-labels.js';
import { profileSections } from './fields.js';
import IdentityFields from './IdentityFields.jsx';
import RecordSection from './RecordSection.jsx';
import SkillsEditor from './SkillsEditor.jsx';
import ResearchInterestsEditor from './ResearchInterestsEditor.jsx';
import PersonalInterestTagsEditor from './PersonalInterestTagsEditor.jsx';

export default function ProfileFields({
  content,
  onChange,
  tags,
  sections = profileSections,
  identity = true,
}) {
  const { t } = useLanguage();
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
        const isText = ['researchInterestText', 'resumeDescription'].includes(section);
        const value = content[section] || (isText ? '' : []);
        const props = { value, tags, onChange: (next) => set(section, next) };
        return (
          <section className="panel" key={section}>
            <div className="section-heading">
              <span className="section-number">
                {String(index + (identity ? 2 : 1)).padStart(2, '0')}
              </span>
              <h3>{t(labels[section])}</h3>
              <span className="muted count">
                {t(isText ? '{count} characters' : '{count} entries', { count: value.length })}
              </span>
            </div>
            {isText ? (
              <label>
                <span>{t(labels[section])}</span>
                <textarea
                  value={value}
                  maxLength={section === 'resumeDescription' ? 20000 : 5000}
                  rows={5}
                  onChange={(event) => set(section, event.target.value)}
                />
                {section === 'resumeDescription' && <small>{t('Visible only to you.')}</small>}
              </label>
            ) : section === 'customInterestTags' ? (
              <PersonalInterestTagsEditor {...props} />
            ) : section === 'skills' ? (
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
