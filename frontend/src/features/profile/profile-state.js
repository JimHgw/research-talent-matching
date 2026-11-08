import { isObject, isRevision, requireSnapshot } from '../../shared/editor-state.js';

export const profileValues = (profile) => profile.content;
export function validateProfile(profile, { previous, operation } = {}) {
  requireSnapshot(
    isObject(profile) && typeof profile.talentId === 'string' && isRevision(profile.revision)
  );
  const content = profile.content;
  requireSnapshot(
    isObject(content) &&
      typeof content.displayName === 'string' &&
      [null, 'STEM', 'BUSINESS'].includes(content.disciplineGroup)
  );
  for (const field of ['education', 'courses', 'researchExperience', 'skills', 'researchOutputs']) {
    requireSnapshot(
      Array.isArray(content[field]) &&
        content[field].every(
          (row) =>
            isObject(row) &&
            typeof row.id === 'string' &&
            Object.entries(row).every(
              ([key, value]) =>
                value == null ||
                typeof value === 'string' ||
                (['startYear', 'endYear'].includes(key) && Number.isInteger(value))
            )
        )
    );
  }
  requireSnapshot(
    Array.isArray(content.researchInterests) &&
      content.researchInterests.every((id) => typeof id === 'string')
  );
  requireSnapshot(
    content.customInterestTags === undefined ||
      (Array.isArray(content.customInterestTags) &&
        content.customInterestTags.every(
          (tag) => isObject(tag) && typeof tag.id === 'string' && typeof tag.label === 'string'
        ))
  );
  for (const field of ['researchInterestText', 'resumeDescription'])
    requireSnapshot(content[field] === undefined || typeof content[field] === 'string');
  const confirmation = profile.confirmation;
  requireSnapshot(
    isObject(confirmation) &&
      ['CONFIRMED', 'UNCONFIRMED'].includes(confirmation.status) &&
      (confirmation.confirmedRevision === null || isRevision(confirmation.confirmedRevision))
  );
  if (previous)
    requireSnapshot(
      profile.talentId === previous.talentId && profile.revision >= previous.revision
    );
  if (operation === 'confirm')
    requireSnapshot(
      profile.revision === previous.revision &&
        confirmation.status === 'CONFIRMED' &&
        confirmation.confirmedRevision === profile.revision
    );
  if (operation === 'save' && profile.revision > previous.revision)
    requireSnapshot(confirmation.status === 'UNCONFIRMED');
  return profile;
}
