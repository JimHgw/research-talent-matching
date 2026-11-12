import React from 'react';
import { useLanguage } from '../../shared/i18n.jsx';
import { labels } from '../../shared/profile-labels.js';
import { fieldConfigs } from './fields.js';

export default function ProfileSummary({ content, tags }) {
  const { t } = useLanguage();
  const sections = {
    ...fieldConfigs,
    skills: [
      ['title', 'Skill title'],
      ['evidenceText', 'Supporting evidence'],
    ],
  };
  return (
    <div>
      <dl>
        <dt>{t('Display name')}</dt>
        <dd>{content.displayName}</dd>
        <dt>{t('Discipline group')}</dt>
        <dd>{content.disciplineGroup && t(content.disciplineGroup)}</dd>
      </dl>
      {Object.entries(sections).map(([section, fields]) => (
        <section key={section}>
          <h5>{t(labels[section])}</h5>
          {content[section].map((record) => (
            <dl key={record.id}>
              {fields
                .filter(([key]) => record[key] != null && record[key] !== '')
                .map(([key, label]) => (
                  <div key={key}>
                    <dt>{t(label)}</dt>
                    <dd>{key === 'type' ? t(record[key]) : String(record[key])}</dd>
                  </div>
                ))}
            </dl>
          ))}
        </section>
      ))}
      <h5>{t('Research interests')}</h5>
      <p>
        {content.researchInterests
          .map((id) => tags.find((tag) => tag.id === id)?.label || t('Not available'))
          .join(', ')}
      </p>
      <p>{content.researchInterestText}</p>
      <h5>{t('Personal interest tags')}</h5>
      {content.customInterestTags?.map((tag) => (
        <div key={tag.id}>
          <strong>{tag.label}</strong>
          {tag.description && <p>{tag.description}</p>}
        </div>
      ))}
      <h5>{t('Resume description')}</h5>
      <p>{content.resumeDescription}</p>
    </div>
  );
}
