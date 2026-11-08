import { isObject, isRevision, requireSnapshot } from '../../shared/editor-state.js';

export function validateOpportunitySnapshot(snapshot, { previous, operation } = {}) {
  requireSnapshot(
    isObject(snapshot) &&
      typeof snapshot.id === 'string' &&
      snapshot.id.length > 0 &&
      isRevision(snapshot.revision) &&
      ['DRAFT', 'PUBLISHED'].includes(snapshot.status)
  );
  const content = snapshot.content;
  requireSnapshot(
    isObject(content) &&
      ['title', 'university', 'discipline', 'researchArea', 'description'].every(
        (key) => typeof content[key] === 'string'
      ) &&
      ['STEM', 'BUSINESS'].includes(content.disciplineGroup) &&
      Array.isArray(content.requirements) &&
      content.requirements.every(
        (row) =>
          isObject(row) &&
          typeof row.id === 'string' &&
          typeof row.label === 'string' &&
          ['SKILL', 'INTEREST', 'EDUCATION', 'RESEARCH_EXPERIENCE', 'RESEARCH_OUTPUT'].includes(
            row.kind
          ) &&
          ['REQUIRED', 'PREFERRED'].includes(row.importance)
      )
  );
  requireSnapshot(
    snapshot.availabilityStatus === undefined ||
      ['DRAFT', 'ACTIVE', 'EXPIRED'].includes(snapshot.availabilityStatus)
  );
  if (previous)
    requireSnapshot(snapshot.id === previous.id && snapshot.revision >= previous.revision);
  if (operation === 'publish') requireSnapshot(snapshot.status === 'PUBLISHED');
  if (operation === 'reopen')
    requireSnapshot(snapshot.status === 'PUBLISHED' && snapshot.availabilityStatus === 'ACTIVE');
  if (operation === 'save') {
    requireSnapshot(snapshot.status === (previous?.status || 'DRAFT'));
    if (previous?.availabilityStatus === 'EXPIRED')
      requireSnapshot(snapshot.availabilityStatus === 'EXPIRED');
  }
  return snapshot;
}
