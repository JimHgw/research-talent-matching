import { ApiError } from './errors.js';
export { ApiError } from './errors.js';

// The application always uses HTTP. Tests inject fetch without changing runtime mode.
export function createApi({
  baseUrl = '/api/v1',
  fetchImpl = (...args) => globalThis.fetch(...args),
} = {}) {
  const base = baseUrl.replace(/\/$/, '');
  let csrfToken = '';
  let pendingSession = null;
  let sessionVersion = 0;
  function searchQuery(filters = {}) {
    const query = new URLSearchParams();
    for (const [key, value] of Object.entries(filters)) {
      for (const item of Array.isArray(value) ? value : [value]) {
        if (item !== '' && item != null) query.append(key, item);
      }
    }
    return query.size ? `&${query}` : '';
  }
  function changedSession() {
    sessionVersion++;
    pendingSession = null;
  }
  async function request(path, { method = 'GET', body, signal, binary = false } = {}) {
    const startedVersion = sessionVersion;
    const changesSession =
      method === 'POST' &&
      ['/auth/login', '/auth/register', '/auth/logout', '/auth/login/reset'].includes(path);
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
      if (changesSession) changedSession();
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
    if (changesSession) changedSession();
    if (
      typeof payload?.csrfToken === 'string' &&
      (changesSession || startedVersion === sessionVersion)
    )
      csrfToken = payload.csrfToken;
    return payload;
  }
  return {
    // StrictMode can start two effects before the first anonymous cookie arrives.
    // Share only the in-flight bootstrap so cookie and CSRF state stay paired.
    session: () => {
      if (!pendingSession) {
        const bootstrap = request('/auth/session').finally(() => {
          if (pendingSession === bootstrap) pendingSession = null;
        });
        pendingSession = bootstrap;
      }
      return pendingSession;
    },
    login: (identifier, password) =>
      request('/auth/login', {
        method: 'POST',
        body: identifier.includes('@') ? { email: identifier, password } : { identifier, password },
      }),
    requestRegistrationCode: (email) =>
      request('/auth/register/code', { method: 'POST', body: { email } }),
    register: (body) => request('/auth/register', { method: 'POST', body }),
    requestPasswordResetCode: (email) =>
      request('/auth/login/reset/code', { method: 'POST', body: { email } }),
    verifyPasswordResetCode: (email, code) =>
      request('/auth/login/reset/verify', { method: 'POST', body: { email, code } }),
    resetPassword: (body) => request('/auth/login/reset', { method: 'POST', body }),
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
    opportunities: (scope = 'published', page = 1, filters = {}) =>
      request(
        `/opportunities?scope=${encodeURIComponent(scope)}&page=${page}${searchQuery(filters)}`
      ),
    opportunity: (id) => request(`/opportunities/${encodeURIComponent(id)}`),
    saveOpportunity: (id, expectedRevision, content, reopen = false) =>
      request(id ? `/opportunities/${encodeURIComponent(id)}` : '/opportunities', {
        method: id ? 'PUT' : 'POST',
        body: id ? { expectedRevision, content, ...(reopen ? { reopen: true } : {}) } : content,
      }),
    publish: (id, expectedRevision) =>
      request(`/opportunities/${encodeURIComponent(id)}/publish`, {
        method: 'POST',
        body: { expectedRevision },
      }),
    savedOpportunities: (page = 1) => request(`/me/saved-opportunities?page=${page}`),
    collectionState: (opportunityId, talentId) =>
      request(
        talentId
          ? `/opportunities/${encodeURIComponent(opportunityId)}/shortlist/${encodeURIComponent(talentId)}`
          : `/me/saved-opportunities/${encodeURIComponent(opportunityId)}`
      ),
    setCollection: (opportunityId, talentId, saved) =>
      request(
        talentId
          ? `/opportunities/${encodeURIComponent(opportunityId)}/shortlist/${encodeURIComponent(talentId)}`
          : `/me/saved-opportunities/${encodeURIComponent(opportunityId)}`,
        { method: saved ? 'PUT' : 'DELETE' }
      ),
    shortlist: (id, page = 1) =>
      request(`/opportunities/${encodeURIComponent(id)}/shortlist?page=${page}`),
    recommendations: (page = 1, filters = {}) =>
      request(`/me/recommendations?page=${page}${searchQuery(filters)}`),
    match: (id) => request(`/me/opportunity-matches/${encodeURIComponent(id)}`),
    talents: (id, page = 1, filters = {}) =>
      request(
        `/opportunities/${encodeURIComponent(id)}/talent-matches?page=${page}${searchQuery(filters)}`
      ),
    talentMatch: (id, talentId) =>
      request(
        `/opportunities/${encodeURIComponent(id)}/talent-matches/${encodeURIComponent(talentId)}`
      ),
  };
}

export const api = createApi({ baseUrl: import.meta.env?.VITE_API_BASE_URL || '/api/v1' });
