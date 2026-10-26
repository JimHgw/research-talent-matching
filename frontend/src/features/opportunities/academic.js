export const outputTypes = { PUBLICATION: 'Publication', PROJECT: 'Project', OTHER: 'Other' };

export const requirementKinds = {
  SKILL: 'Skill',
  INTEREST: 'Research interest',
  EDUCATION: 'Education',
  RESEARCH_EXPERIENCE: 'Research experience',
  RESEARCH_OUTPUT: 'Research outputs',
};

export const academicFields = {
  EDUCATION: [
    { key: 'qualification', label: 'Qualification', maxLength: 200 },
    { key: 'discipline', label: 'Discipline', maxLength: 200 },
  ],
  RESEARCH_EXPERIENCE: [
    { key: 'title', label: 'Project / role title', maxLength: 200 },
    { key: 'organisation', label: 'Organisation', maxLength: 200 },
  ],
  RESEARCH_OUTPUT: [
    { key: 'type', label: 'Type', options: ['PUBLICATION', 'PROJECT', 'OTHER'] },
    { key: 'title', label: 'Output title', maxLength: 300 },
  ],
};

export function validAcademicRequirement(row) {
  const fields = academicFields[row.kind];
  const criteria = row.criteria;
  return (
    !!fields &&
    Array.isArray(row.tagIds) &&
    !row.tagIds.length &&
    !Object.hasOwn(row, 'skillTitles') &&
    !!criteria &&
    typeof criteria === 'object' &&
    !Array.isArray(criteria) &&
    Object.keys(criteria).length > 0 &&
    Object.entries(criteria).every(([key, value]) => {
      const field = fields.find((item) => item.key === key);
      return (
        field &&
        typeof value === 'string' &&
        value.trim().length > 0 &&
        (field.options ? field.options.includes(value) : value.length <= field.maxLength)
      );
    })
  );
}
