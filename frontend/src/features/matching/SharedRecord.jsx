import React from 'react';
import { useLanguage } from '../../shared/i18n.jsx';

// Display only structured fields in the permitted team projection. Never follow
// a document reference or fetch the owner's full profile to fill missing fields.
const recordFields = {
  education: [
    ['qualification', 'Qualification'],
    ['institution', 'Institution'],
    ['discipline', 'Discipline'],
    ['startYear', 'Start year'],
    ['endYear', 'End year'],
  ],
  courses: [
    ['name', 'Course name'],
    ['code', 'Course code'],
    ['description', 'Description'],
  ],
  researchExperience: [
    ['title', 'Project / role title'],
    ['organisation', 'Organisation'],
    ['description', 'Description'],
  ],
  researchOutputs: [
    ['title', 'Output title'],
    ['type', 'Type'],
    ['description', 'Description'],
  ],
  skills: [
    ['title', 'Skill'],
    ['evidenceText', 'Supporting evidence'],
  ],
};

export function supportingRecord(talent, evidence) {
  const rows = talent?.fields?.[evidence.field];
  if (!recordFields[evidence.field] || !Array.isArray(rows)) return null;
  return rows.find((row) => row.id === evidence.recordId) || null;
}

export default function SharedRecord({ record, field }) {
  const { t } = useLanguage();
  return (
    <dl className="shared-record">
      {(recordFields[field] || [])
        .filter(([key]) => record[key] != null && record[key] !== '')
        .map(([key, label]) => (
          <div key={key}>
            <dt>{t(label)}</dt>
            <dd>{key === 'type' ? t(record[key]) : String(record[key])}</dd>
          </div>
        ))}
    </dl>
  );
}

export const sharedRecordFields = Object.keys(recordFields);
