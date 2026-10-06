import { ApiError } from './errors.js';
export { ApiError } from './errors.js';

// The application always uses HTTP. Tests inject fetch without changing runtime mode.
export function createApi({
  baseUrl = '/api/v1',
  fetchImpl = (...args) => globalThis.fetch(...args),
} = {}) {
  const base = baseUrl.replace(/\/$/, '');
  let csrfToken = '';
  async function request(path, { method = 'GET', body, signal, binary = false } = {}) {
    const multipart = body instanceof FormData;
    const headers = { Accept: binary ? '*/*' : 'application/json' };
    if (body !== undefined && !multipart) headers['Content-Type'] = 'application/json';
    if (method !== 'GET') headers['X-CSRF-Token'] = csrfToken;
    let response;
    try {
      response = await fetchImpl(`${base}${path}`, {
        method,
        headers,
        credentials: 'include',
        signal,
        body: multipart ? body : body !== undefined ? JSON.stringify(body) : undefined,
      });
    } catch (error) {
      if (error.name === 'AbortError') throw error;
      throw new ApiError(0, {
        error: {
          code: 'NETWORK_ERROR',
          message: 'Cannot connect to the service. Check your connection and try again.',
        },
      });
    }
    if (response.status === 204) {
      if (path === '/auth/logout') csrfToken = '';
      return undefined;
    }
    if (binary && response.ok) return response.blob();
    let payload;
    try {
      payload = await response.json();
    } catch {
      throw new ApiError(response.status, {
        error: {
          code: 'INVALID_RESPONSE',
          message: 'The service returned an unreadable response. Please try again shortly.',
        },
      });
    }
    if (!response.ok) throw new ApiError(response.status, payload);
    if (typeof payload?.csrfToken === 'string') csrfToken = payload.csrfToken;
    return payload;
  }
  return {
    session: () => request('/auth/session'),
    login: (email, password) =>
      request('/auth/login', { method: 'POST', body: { email, password } }),
    logout: () => request('/auth/logout', { method: 'POST' }),
    tags: () => request('/tags'),
    profile: () => request('/me/profile'),
    saveProfile: (expectedRevision, content) =>
      request('/me/profile', { method: 'PUT', body: { expectedRevision, content } }),
    confirm: (expectedRevision) =>
      request('/me/profile/confirmation', { method: 'POST', body: { expectedRevision } }),
    privacy: () => request('/me/privacy'),
    savePrivacy: (body) => request('/me/privacy', { method: 'PUT', body }),
    documents: (page = 1) => request(`/me/documents?page=${page}`),
    upload: (file, kind) => {
      const body = new FormData();
      body.append('file', file);
      body.append('kind', kind);
      return request('/me/documents', { method: 'POST', body });
    },
    document: (id) => request(`/me/documents/${encodeURIComponent(id)}`),
    extraction: (id) => request(`/me/documents/${encodeURIComponent(id)}/extraction`),
    apply: (id, expectedProfileRevision, sections) =>
      request(`/me/documents/${encodeURIComponent(id)}/apply`, {
        method: 'POST',
        body: { expectedProfileRevision, sections },
      }),
    download: (id) => request(`/me/documents/${encodeURIComponent(id)}/file`, { binary: true }),
    opportunities: (scope = 'published', page = 1) =>
      request(`/opportunities?scope=${scope}&page=${page}`),
    opportunity: (id) => request(`/opportunities/${encodeURIComponent(id)}`),
    saveOpportunity: (id, expectedRevision, content) =>
      request(id ? `/opportunities/${encodeURIComponent(id)}` : '/opportunities', {
        method: id ? 'PUT' : 'POST',
        body: id ? { expectedRevision, content } : content,
      }),
    publish: (id, expectedRevision) =>
      request(`/opportunities/${encodeURIComponent(id)}/publish`, {
        method: 'POST',
        body: { expectedRevision },
      }),
    recommendations: (page = 1) => request(`/me/recommendations?page=${page}`),
    match: (id) => request(`/me/opportunity-matches/${encodeURIComponent(id)}`),
    talents: (id, page = 1) =>
      request(`/opportunities/${encodeURIComponent(id)}/talent-matches?page=${page}`),
    talentMatch: (id, talentId) =>
      request(
        `/opportunities/${encodeURIComponent(id)}/talent-matches/${encodeURIComponent(talentId)}`
      ),
  };
}

export const api = createApi({ baseUrl: import.meta.env?.VITE_API_BASE_URL || '/api/v1' });
