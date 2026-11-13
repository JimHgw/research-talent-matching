import { readApiError } from './error-contract.ts';

export class ApiError extends Error {
  constructor(status, payload) {
    const error = readApiError(payload);
    super(error.message || 'The request could not be completed.');
    this.status = status;
    this.code = error.code;
    this.fields = error.fieldErrors;
    this.currentRevision = error.currentRevision;
  }
}

export function invalidApiResponse(
  message = 'The service returned an unreadable response. Please try again shortly.'
) {
  return new ApiError(502, { error: { code: 'INVALID_RESPONSE', message } });
}
