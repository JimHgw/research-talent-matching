export const fieldConfigs = {
  education: [
    ['institution', 'Institution', 'text', true],
    ['qualification', 'Qualification', 'text', true],
    ['discipline', 'Discipline', 'text'],
    ['startYear', 'Start year', 'number'],
    ['endYear', 'End year', 'number'],
  ],
  courses: [
    ['name', 'Course name', 'text', true],
    ['code', 'Course code', 'text'],
    ['description', 'Description', 'textarea'],
  ],
  researchExperience: [
    ['title', 'Project / role title', 'text', true],
    ['organisation', 'Organisation', 'text'],
    ['description', 'Description', 'textarea'],
  ],
  researchOutputs: [
    ['title', 'Output title', 'text', true],
    ['type', 'Type', 'outputType'],
    ['url', 'Link (optional)', 'url'],
    ['description', 'Description', 'textarea'],
  ],
};

export const profileSections = Object.keys(fieldConfigs).concat([
  'skills',
  'researchInterests',
  'researchInterestText',
  'customInterestTags',
  'resumeDescription',
]);

export function createRecord(section) {
  const row = { id: `record_${crypto.randomUUID()}` };
  for (const [field, , type] of fieldConfigs[section])
    row[field] =
      type === 'number' || field === 'url' || field === 'code'
        ? null
        : type === 'outputType'
          ? 'PROJECT'
          : '';
  return row;
}

export function recordValue(field, type, value) {
  if (type === 'number') return value === '' ? null : Number(value);
  return ['url', 'code'].includes(field) && !value ? null : value;
}
