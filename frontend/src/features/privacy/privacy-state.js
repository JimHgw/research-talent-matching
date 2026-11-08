import { isObject, isRevision, requireSnapshot } from '../../shared/editor-state.js';
import { privacyFields } from './fields.js';

export const privacyValues = (saved) => ({
  discoverable: saved.discoverable,
  visibleFields: [...saved.visibleFields].sort(),
});
export function validatePrivacy(saved, { previous } = {}) {
  requireSnapshot(
    isObject(saved) &&
      isRevision(saved.revision) &&
      typeof saved.discoverable === 'boolean' &&
      Array.isArray(saved.visibleFields) &&
      saved.visibleFields.every((field) => privacyFields.includes(field)) &&
      new Set(saved.visibleFields).size === saved.visibleFields.length
  );
  if (previous) requireSnapshot(saved.revision >= previous.revision);
  return saved;
}
