import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createApi, ApiError } from '../src/api/client.js';

const fixture = (name) =>
  JSON.parse(
    readFileSync(new URL(`../../docs/api/examples/${name}.json`, import.meta.url), 'utf8')
  );
const contract = JSON.parse(
  readFileSync(new URL('../../docs/api/openapi.json', import.meta.url), 'utf8')
);
const content = fixture('profile-confirmed').content;
const opportunity = fixture('opportunity-published').content;
function harness(responder = () => new Response(JSON.stringify({ csrfToken: 'csrf-test' }))) {
  const calls = [];
  const api = createApi({
    fetchImpl: async (url, options) => {
      calls.push({ url, ...options });
      return responder(calls.at(-1));
    },
  });
  return { api, calls };
}
const cases = [
  ['session', [], 'GET', '/auth/session'],
  [
    'login',
    ['talent@example.test', 'test-password'],
    'POST',
    '/auth/login',
    { email: 'talent@example.test', password: 'test-password' },
  ],
  ['logout', [], 'POST', '/auth/logout'],
  [
    'login',
    ['user_demo_001', 'test-password'],
    'POST',
    '/auth/login',
    { identifier: 'user_demo_001', password: 'test-password' },
  ],
  [
    'requestRegistrationCode',
    ['new-talent@example.test'],
    'POST',
    '/auth/register/code',
    { email: 'new-talent@example.test' },
  ],
  [
    'register',
    [fixture('register-request')],
    'POST',
    '/auth/register',
    fixture('register-request'),
  ],
  ['tags', [], 'GET', '/tags'],
  [
    'requestPasswordResetCode',
    ['talent@example.test'],
    'POST',
    '/auth/login/reset/code',
    { email: 'talent@example.test' },
  ],
  [
    'verifyPasswordResetCode',
    ['talent@example.test', '012345'],
    'POST',
    '/auth/login/reset/verify',
    { email: 'talent@example.test', code: '012345' },
  ],
  [
    'resetPassword',
    [fixture('reset-password-request')],
    'POST',
    '/auth/login/reset',
    fixture('reset-password-request'),
  ],
  [
    'resetPassword',
    [fixture('reset-email-request')],
    'POST',
    '/auth/login/reset',
    fixture('reset-email-request'),
  ],
  ['profile', [], 'GET', '/me/profile'],
  ['saveProfile', [3, content], 'PUT', '/me/profile', { expectedRevision: 3, content }],
  ['confirm', [3], 'POST', '/me/profile/confirmation', { expectedRevision: 3 }],
  ['privacy', [], 'GET', '/me/privacy'],
  [
    'savePrivacy',
    [{ expectedRevision: 2, discoverable: false, visibleFields: [] }],
    'PUT',
    '/me/privacy',
    { expectedRevision: 2, discoverable: false, visibleFields: [] },
  ],
  ['documents', [2], 'GET', '/me/documents?page=2'],
  [
    'upload',
    [new File(['%PDF-test'], 'synthetic.pdf', { type: 'application/pdf' }), 'CV'],
    'POST',
    '/me/documents',
    'multipart',
  ],
  ['document', ['doc_1'], 'GET', '/me/documents/doc_1'],
  ['extraction', ['doc_1'], 'GET', '/me/documents/doc_1/extraction'],
  [
    'apply',
    ['doc_1', 3, { skills: [] }],
    'POST',
    '/me/documents/doc_1/apply',
    { expectedProfileRevision: 3, sections: { skills: [] } },
  ],
  ['download', ['doc_1'], 'GET', '/me/documents/doc_1/file'],
  ['opportunities', ['mine', 2], 'GET', '/opportunities?scope=mine&page=2'],
  ['opportunity', ['opp_1'], 'GET', '/opportunities/opp_1'],
  ['saveOpportunity', [null, null, opportunity], 'POST', '/opportunities', opportunity],
  [
    'saveOpportunity',
    ['opp_1', 2, opportunity],
    'PUT',
    '/opportunities/opp_1',
    { expectedRevision: 2, content: opportunity },
  ],
  ['publish', ['opp_1', 2], 'POST', '/opportunities/opp_1/publish', { expectedRevision: 2 }],
  ['recommendations', [2], 'GET', '/me/recommendations?page=2'],
  ['match', ['opp_1'], 'GET', '/me/opportunity-matches/opp_1'],
  ['talents', ['opp_1', 2], 'GET', '/opportunities/opp_1/talent-matches?page=2'],
  ['talentMatch', ['opp_1', 'talent_1'], 'GET', '/opportunities/opp_1/talent-matches/talent_1'],
  ['savedOpportunities', [2], 'GET', '/me/saved-opportunities?page=2'],
  ['collectionState', ['opp_1'], 'GET', '/me/saved-opportunities/opp_1'],
  ['setCollection', ['opp_1', undefined, true], 'PUT', '/me/saved-opportunities/opp_1'],
  ['setCollection', ['opp_1', undefined, false], 'DELETE', '/me/saved-opportunities/opp_1'],
  ['shortlist', ['opp_1', 2], 'GET', '/opportunities/opp_1/shortlist?page=2'],
  ['collectionState', ['opp_1', 'talent_1'], 'GET', '/opportunities/opp_1/shortlist/talent_1'],
  ['setCollection', ['opp_1', 'talent_1', true], 'PUT', '/opportunities/opp_1/shortlist/talent_1'],
  ['setCollection', ['opp_1', 'talent_1', false], 'DELETE', '/opportunities/opp_1/shortlist/talent_1'],
];
for (const [name, args, method, path, body] of cases) {
  test(`${method} ${path}: request matches API contract`, async () => {
    const { api, calls } = harness();
    await api[name](...args);
    assert.equal(calls.length, 1, 'Do not duplicate mutations');
    const call = calls[0];
    assert.equal(call.url, '/api/v1' + path);
    assert.equal(call.method, method);
    assert.equal(call.credentials, 'include');
    if (body === 'multipart') {
      assert.ok(call.body instanceof FormData);
      assert.equal(call.body.get('kind'), 'CV');
      assert.equal(call.body.get('file').name, 'synthetic.pdf');
      assert.equal(
        call.headers['Content-Type'],
        undefined,
        'Browser must supply multipart boundary'
      );
    } else if (body !== undefined) {
      assert.deepEqual(JSON.parse(call.body), body);
      assert.equal(call.headers['Content-Type'], 'application/json');
    } else assert.equal(call.body, undefined);
  });
}
test('all OpenAPI operations have a request case', () => {
  for (const [path, operations] of Object.entries(contract.paths)) {
    const regex = new RegExp('^' + path.replace(/\{[^}]+\}/g, '[^/]+') + '$');
    for (const method of Object.keys(operations).filter((m) =>
      ['get', 'post', 'put', 'delete', 'patch'].includes(m)
    )) {
      assert.ok(
        cases.some(
          ([, , verb, actual]) => verb.toLowerCase() === method && regex.test(actual.split('?')[0])
        ),
        `${method} ${path} has no request test`
      );
    }
  }
});
test('session CSRF token is sent on login and rotated for subsequent writes', async () => {
  const { api, calls } = harness(
    (call) =>
      new Response(
        JSON.stringify({
          csrfToken: call.url.endsWith('/session') ? 'anonymous-token' : 'signed-in-token',
        })
      )
  );
  await api.session();
  await api.login('talent@example.test', 'test-only');
  await api.confirm(3);
  assert.equal(calls[0].headers['X-CSRF-Token'], undefined);
  assert.equal(calls[1].headers['X-CSRF-Token'], 'anonymous-token');
  assert.equal(calls[2].headers['X-CSRF-Token'], 'signed-in-token');
});
test('logout accepts 204 and clears the old CSRF token', async () => {
  const { api, calls } = harness((call) =>
    call.url.endsWith('/logout')
      ? new Response(null, { status: 204 })
      : new Response(JSON.stringify({ csrfToken: 'test-token' }))
  );
  await api.session();
  assert.equal(await api.logout(), undefined);
  await api.login('x', 'y');
  assert.equal(calls[1].headers['X-CSRF-Token'], 'test-token');
  assert.equal(calls[2].headers['X-CSRF-Token'], '');
});
test('separate API clients do not share session tokens', async () => {
  const first = harness(),
    second = harness();
  await first.api.session();
  await second.api.confirm(0);
  assert.equal(second.calls[0].headers['X-CSRF-Token'], '');
});

test('concurrent session bootstraps share one request and later refreshes fetch again', async () => {
  let release;
  let calls = 0;
  const api = createApi({
    fetchImpl: () => {
      calls++;
      return new Promise((resolve) => {
        release = () => resolve(new Response(JSON.stringify({ user: null, csrfToken: 'paired' })));
      });
    },
  });
  const first = api.session();
  const second = api.session();
  assert.equal(calls, 1);
  release();
  assert.deepEqual(await first, await second);
  const refresh = api.session();
  assert.equal(calls, 2);
  release();
  await refresh;
});
test('revision conflicts preserve server error fields and are never retried automatically', async () => {
  const payload = fixture('error-revision-conflict');
  const { api, calls } = harness(() => new Response(JSON.stringify(payload), { status: 409 }));
  await assert.rejects(
    api.saveProfile(0, content),
    (error) =>
      error instanceof ApiError &&
      error.code === 'REVISION_CONFLICT' &&
      error.status === 409 &&
      error.currentRevision === payload.error.currentRevision
  );
  assert.equal(calls.length, 1);
});
test('validation errors expose field messages to forms', async () => {
  const payload = fixture('error-validation');
  const { api } = harness(() => new Response(JSON.stringify(payload), { status: 422 }));
  await assert.rejects(api.confirm(0), (error) => {
    assert.deepEqual(error.fields, payload.error.fieldErrors);
    return true;
  });
});
test('authentication failure is surfaced instead of returning synthetic data', async () => {
  const { api } = harness(
    () =>
      new Response(
        JSON.stringify({ error: { code: 'UNAUTHENTICATED', message: 'Sign in again.' } }),
        { status: 401 }
      )
  );
  await assert.rejects(
    api.profile(),
    (error) => error.status === 401 && error.code === 'UNAUTHENTICATED'
  );
});
test('network failure is actionable and does not fall back to a mock response', async () => {
  const { api, calls } = harness(() => {
    throw new TypeError('fetch failed');
  });
  await assert.rejects(
    api.profile(),
    (error) => error.code === 'NETWORK_ERROR' && error.status === 0
  );
  assert.equal(calls.length, 1);
});
test('non-JSON success is rejected rather than being treated as valid application data', async () => {
  const { api } = harness(() => new Response('<html>Login redirect</html>'));
  await assert.rejects(api.session(), (error) => error.code === 'INVALID_RESPONSE');
});
test('binary download returns original bytes', async () => {
  const { api } = harness(
    () => new Response('%PDF-synthetic-bytes', { headers: { 'Content-Type': 'application/pdf' } })
  );
  assert.equal(await (await api.download('doc_test')).text(), '%PDF-synthetic-bytes');
});
test('download errors still use structured API errors', async () => {
  const { api } = harness(
    () =>
      new Response(JSON.stringify({ error: { code: 'NOT_FOUND', message: 'Unavailable.' } }), {
        status: 404,
      })
  );
  await assert.rejects(api.download('doc_missing'), (error) => error.code === 'NOT_FOUND');
});
test('custom base URL and encoded identifiers stay inside the intended resource path', async () => {
  let requested;
  const api = createApi({
    baseUrl: 'https://api.example.test/api/v1/',
    fetchImpl: async (url) => {
      requested = url;
      return new Response('{}');
    },
  });
  await api.talentMatch('opp/a', 'talent?b');
  assert.equal(
    requested,
    'https://api.example.test/api/v1/opportunities/opp%2Fa/talent-matches/talent%3Fb'
  );
});
