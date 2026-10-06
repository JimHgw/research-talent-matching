export class ApiError extends Error {
  constructor(status, payload) {
    super(payload.error?.message || 'The request could not be completed.');
    this.status = status;
    this.code = payload.error?.code;
    this.fields = payload.error?.fieldErrors || [];
    this.currentRevision = payload.error?.currentRevision;
  }
}
