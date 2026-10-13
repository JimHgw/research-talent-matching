import assert from 'node:assert/strict';
import test from 'node:test';
import { createApi } from '../src/api/client.js';

test('collections use owner-scoped URLs, session cookies and CSRF-protected writes', async () => {
  const calls = [];
  const api = createApi({
    fetchImpl: async (url, options) => {
      calls.push({ url, ...options });
      return new Response(JSON.stringify({ csrfToken: 'test-csrf', saved: true }));
    },
  });
  await api.session();
  await api.savedOpportunities(2);
  await api.collectionState('opp/one');
  await api.setCollection('opp/one', undefined, true);
  await api.setCollection('opp/one', undefined, false);
  await api.shortlist('opp/one', 3);
  await api.collectionState('opp/one', 'talent/one');
  await api.setCollection('opp/one', 'talent/one', true);
  await api.setCollection('opp/one', 'talent/one', false);
  assert.deepEqual(
    calls.slice(1).map(({ url, method }) => [url, method]),
    [
      ['/api/v1/me/saved-opportunities?page=2', 'GET'],
      ['/api/v1/me/saved-opportunities/opp%2Fone', 'GET'],
      ['/api/v1/me/saved-opportunities/opp%2Fone', 'PUT'],
      ['/api/v1/me/saved-opportunities/opp%2Fone', 'DELETE'],
      ['/api/v1/opportunities/opp%2Fone/shortlist?page=3', 'GET'],
      ['/api/v1/opportunities/opp%2Fone/shortlist/talent%2Fone', 'GET'],
      ['/api/v1/opportunities/opp%2Fone/shortlist/talent%2Fone', 'PUT'],
      ['/api/v1/opportunities/opp%2Fone/shortlist/talent%2Fone', 'DELETE'],
    ]
  );
  for (const call of calls) {
    assert.equal(call.credentials, 'include');
    if (call.method !== 'GET') assert.equal(call.headers['X-CSRF-Token'], 'test-csrf');
  }
});

test('collection failures are surfaced instead of reported as successful saves', async () => {
  const api = createApi({
    fetchImpl: async () =>
      new Response(
        JSON.stringify({
          error: { code: 'NOT_FOUND', message: 'Talent profile not found.' },
        }),
        { status: 404 }
      ),
  });
  await assert.rejects(api.setCollection('opp', 'talent', true), (e) => e.status === 404);
});
