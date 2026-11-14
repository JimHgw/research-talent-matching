import { isOwnerProfile } from '../../api/review-contract.ts';
import { requireSnapshot } from '../../shared/editor-state.js';

export const profileValues = (profile) => profile.content;
export function validateProfile(profile, { previous, operation } = {}) {
  requireSnapshot(isOwnerProfile(profile));
  const confirmation = profile.confirmation;
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
