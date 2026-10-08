// Form metadata stays in one place; the API contract is authoritative on the server.
export const opportunityFields = [
  { key: 'title', label: 'Opportunity title', maxLength: 200 },
  { key: 'university', label: 'University', maxLength: 200 },
  { key: 'discipline', label: 'Discipline', maxLength: 200 },
  { key: 'researchArea', label: 'Research area', maxLength: 300 },
  { key: 'description', label: 'Description', maxLength: 10000, multiline: true },
];
export const limits = { requirements: 50, tags: 20, requirementLabel: 300 };
export const emptyContent = () => ({
  title: '',
  university: '',
  disciplineGroup: 'STEM',
  discipline: '',
  researchArea: '',
  description: '',
  requirements: [],
});
export const newRequirement = () => ({
  id: `req_${crypto.randomUUID().replaceAll('-', '')}`,
  label: '',
  kind: 'SKILL',
  importance: 'REQUIRED',
  tagIds: [],
});
