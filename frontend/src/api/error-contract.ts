import {
  arrayOf,
  isObject,
  objectOf,
  revision,
  string,
  type Validated,
} from './contract-validation.ts';

const isFieldError = objectOf({ field: string, message: string });
export type ApiErrorDetail = {
  message?: string;
  code?: string;
  fieldErrors: Validated<typeof isFieldError>[];
  currentRevision?: number;
};

export function readApiError(payload: unknown): ApiErrorDetail {
  const error = isObject(payload) && isObject(payload.error) ? payload.error : {};
  return {
    message: string(error.message) ? error.message : undefined,
    code: string(error.code) ? error.code : undefined,
    fieldErrors: arrayOf(isFieldError)(error.fieldErrors) ? error.fieldErrors : [],
    currentRevision: revision(error.currentRevision) ? error.currentRevision : undefined,
  };
}
