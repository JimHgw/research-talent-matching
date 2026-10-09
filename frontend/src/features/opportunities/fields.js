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

export function validateOpportunity(content, tags, status) {
  for (const { key, maxLength } of opportunityFields) {
    if (!content[key].trim()) return 'Complete all required fields with non-blank text.';
    if (content[key].length > maxLength) return `Shorten ${key} to ${maxLength} characters.`;
  }
  if (content.requirements.length > limits.requirements)
    return `Use at most ${limits.requirements} requirements.`;
  for (const [index, requirement] of content.requirements.entries()) {
    if (
      !requirement.label.trim() ||
      requirement.label.length > limits.requirementLabel ||
      !requirement.tagIds.length ||
      requirement.tagIds.length > limits.tags ||
      new Set(requirement.tagIds).size !== requirement.tagIds.length ||
      requirement.tagIds.some(
        (id) => !tags.some((tag) => tag.id === id && tag.kind === requirement.kind)
      )
    )
      return `Requirement ${index + 1} needs a label and 1-${limits.tags} valid tags.`;
  }
  if (status === 'PUBLISHED' && !content.requirements.length)
    return 'Published opportunities need at least one requirement.';
  return null;
}
