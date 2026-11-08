export const isObject = (value) =>
  value !== null && typeof value === 'object' && !Array.isArray(value);
export const isRevision = (value) => Number.isSafeInteger(value) && value >= 0;
export const accessLost = (error) => [401, 403, 404].includes(error?.status);
export const uncertainWrite = (error) =>
  ['NETWORK_ERROR', 'INVALID_RESPONSE'].includes(error?.code) ||
  error?.status === 0 ||
  error?.status >= 500;
export const requiresReconciliation = (error) =>
  error?.code === 'REVISION_CONFLICT' || uncertainWrite(error);

export function requireSnapshot(condition) {
  if (!condition)
    throw Object.assign(
      new Error('The service returned an unreadable response. Please try again shortly.'),
      {
        status: 502,
        code: 'INVALID_RESPONSE',
        fields: [],
      }
    );
}
