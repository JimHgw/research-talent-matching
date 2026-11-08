import test from 'node:test';
import assert from 'node:assert/strict';
import { React, act, state } from './support/app-harness.js';
import { useResource } from '../src/shared/hooks.js';
import { createApi, ApiError } from '../src/api/client.js';

function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => {
    resolve = yes;
    reject = no;
  });
  return { promise, resolve, reject };
}
function harness(retainData = true) {
  const reads = [],
    renders = [];
  let current;
  function Probe({ context = 'first' }) {
    current = useResource(
      ({ signal }) => {
        const read = { ...deferred(), signal, context };
        reads.push(read);
        return read.promise;
      },
      [context],
      true,
      { retainData }
    );
    renders.push(current);
    return React.createElement('p', null, current.data);
  }
  return {
    reads,
    renders,
    get current() {
      return current;
    },
    render: (context, strict = false) =>
      act(async () =>
        state.root.render(
          strict
            ? React.createElement(React.StrictMode, null, React.createElement(Probe, { context }))
            : React.createElement(Probe, { context })
        )
      ),
  };
}

test('same-context refresh retains the authorised result, status and a recoverable refresh error', async () => {
  const h = harness();
  await h.render('page-1');
  assert.equal(h.current.initialLoading, true);
  await act(async () => h.reads[0].resolve('previous result'));
  const refresh = h.current.refresh;
  await act(async () => refresh());
  assert.equal(h.current.loading, true);
  assert.equal(h.current.initialLoading, false);
  assert.equal(h.current.refreshing, true);
  assert.equal(h.current.data, 'previous result');
  const error = new ApiError(503, {
    error: { code: 'SERVICE_UNAVAILABLE', message: 'Try later.' },
  });
  await act(async () => h.reads[1].reject(error));
  assert.equal(h.current.data, 'previous result');
  assert.equal(h.current.error, null);
  assert.equal(h.current.refreshError, error);
  assert.equal(h.current.refresh, refresh);
  await act(async () => refresh());
  await act(async () => h.reads[2].resolve('new result'));
  assert.equal(h.current.data, 'new result');
  assert.equal(h.current.refreshError, null);
});

for (const [status, code] of [
  [401, 'UNAUTHENTICATED'],
  [403, 'FORBIDDEN'],
  [404, 'NOT_FOUND'],
  [409, 'PROFILE_UNCONFIRMED'],
  [502, 'INVALID_RESPONSE'],
]) {
  test(`${code} clears a previous protected result instead of retaining it`, async () => {
    const h = harness();
    await h.render();
    await act(async () => h.reads[0].resolve('private evidence'));
    await act(async () => h.current.refresh());
    await act(async () => h.reads[1].reject(new ApiError(status, { error: { code } })));
    assert.equal(h.current.data, null);
    assert.equal(h.current.error.code, code);
    assert.equal(h.current.refreshError, null);
    assert.equal(document.body.textContent.includes('private evidence'), false);
  });
}

test('context changes synchronously hide old data and ignore late success/failure even without abort support', async () => {
  const h = harness();
  await h.render('account-A/page-1');
  await act(async () => h.reads[0].resolve('account A private'));
  await act(async () => h.current.refresh());
  const offset = h.renders.length;
  await h.render('account-B/page-2');
  assert.ok(h.renders.slice(offset).every((result) => result.data === null));
  assert.equal(h.reads[1].signal.aborted, true);
  await act(async () => h.reads[2].resolve('account B private'));
  await act(async () => h.reads[1].resolve('late account A'));
  assert.equal(h.current.data, 'account B private');
  await act(async () => h.current.refresh());
  await h.render('new-filter');
  await act(async () => h.reads[4].resolve('filtered result'));
  await act(async () => h.reads[3].reject(new ApiError(403, {})));
  assert.equal(h.current.data, 'filtered result');
  assert.equal(h.current.error, null);
});

test('a refreshed request cannot win the race before effect cleanup; unmount aborts reads', async () => {
  const h = harness();
  await h.render();
  await act(async () => {
    h.current.refresh();
    h.reads[0].resolve('obsolete');
  });
  assert.equal(h.reads[0].signal.aborted, true);
  assert.equal(h.current.data, null);
  await act(async () => state.root.render(null));
  assert.equal(h.reads[1].signal.aborted, true);
  await act(async () => h.reads[1].resolve('after unmount'));
  assert.equal(document.body.textContent, '');
});

test('StrictMode leaves one active focus subscription and cancellation is not a network error', async () => {
  const h = harness();
  await h.render('strict', true);
  assert.equal(h.reads.length, 1);
  await act(async () => h.reads[0].resolve('authorised'));
  await act(async () => window.dispatchEvent(new window.Event('focus')));
  assert.equal(h.reads.length, 2);
  await act(async () => h.reads[1].reject(new DOMException('Cancelled', 'AbortError')));
  assert.equal(h.current.data, 'authorised');
  assert.equal(h.current.error, null);
  await act(async () => state.root.render(null));
  await act(async () => window.dispatchEvent(new window.Event('focus')));
  assert.equal(h.reads.length, 2);
});

test('legacy editor refresh explicitly retains the previous loading/clear semantics', async () => {
  const h = harness(false);
  await h.render();
  await act(async () => h.reads[0].resolve('saved baseline'));
  await act(async () => h.current.refresh());
  assert.equal(h.current.loading, true);
  assert.equal(h.current.data, null);
  assert.equal(h.current.refreshing, false);
});

test('public reads forward AbortSignal without changing URLs or session bootstrap ownership', async () => {
  const calls = [];
  const api = createApi({
    fetchImpl: async (url, options) => {
      calls.push({ url, ...options });
      return new Response(JSON.stringify({ csrfToken: 'paired' }));
    },
  });
  const controller = new AbortController();
  const options = { signal: controller.signal };
  const reads = [
    ['tags', []],
    ['profile', []],
    ['privacy', []],
    ['documents', [2]],
    ['document', ['a/b']],
    ['extraction', ['a/b']],
    ['download', ['a/b']],
    ['opportunities', ['published', 2, { search: 'test' }]],
    ['opportunity', ['a/b']],
    ['savedOpportunities', [2]],
    ['collectionState', ['a/b', 'talent']],
    ['shortlist', ['a/b', 2]],
    ['recommendations', [2, {}]],
    ['match', ['a/b']],
    ['talents', ['a/b', 2, {}]],
    ['talentMatch', ['a/b', 'talent']],
  ];
  for (const [method, args] of reads) {
    await api[method](...args, options);
    assert.equal(calls.at(-1).signal, options.signal, method);
    assert.equal(calls.at(-1).credentials, 'include');
    assert.equal(calls.at(-1).method, 'GET');
  }
  const first = api.session(options),
    second = api.session();
  assert.equal(first, second);
  await first;
  assert.equal(calls.at(-1).signal, undefined);
  await api.confirm(2);
  assert.equal(calls.at(-1).signal, undefined);
  assert.equal(calls.at(-1).headers['X-CSRF-Token'], 'paired');
});

test('an aborted HTTP read remains an AbortError, not NETWORK_ERROR', async () => {
  const api = createApi({
    fetchImpl: async (_, { signal }) => {
      signal.throwIfAborted();
    },
  });
  const controller = new AbortController();
  controller.abort();
  await assert.rejects(api.profile({ signal: controller.signal }), { name: 'AbortError' });
});

test('cancellation during JSON body reading remains an AbortError, not INVALID_RESPONSE', async () => {
  const api = createApi({
    fetchImpl: async () => ({
      status: 200,
      ok: true,
      json: async () => {
        throw new DOMException('Cancelled', 'AbortError');
      },
    }),
  });
  await assert.rejects(api.profile(), { name: 'AbortError' });
});
