import test from 'node:test';
import assert from 'node:assert/strict';
import {
  act,
  state,
  mount,
  click,
  change,
  field,
  text,
  json,
  fixture,
  createMockServer,
} from './support/app-harness.js';

const focus = () => act(async () => window.dispatchEvent(new window.Event('focus')));
const failure = (status, code) =>
  json({ error: { code, message: 'Read no longer permitted.' } }, status);

test('team editor survives a temporary list failure but closes when access is revoked', async () => {
  await mount('team@example.test');
  await click('My opportunities');
  await click('Edit');
  await change('Opportunity title *', 'Keep my local edits');
  state.intercept = (path) =>
    path.startsWith('/opportunities?scope=mine') ? failure(503, 'SERVICE_UNAVAILABLE') : null;
  await focus();
  assert.equal(field('Opportunity title *').value, 'Keep my local edits');
  state.intercept = (path) =>
    path.startsWith('/opportunities?scope=mine') ? failure(403, 'FORBIDDEN') : null;
  await focus();
  assert.equal(document.querySelector('dialog'), null);
  assert.equal(document.querySelector('.team-opportunity'), null);
  state.intercept = null;
  await focus();
  assert.ok(document.querySelector('.team-opportunity'));
  assert.equal(document.querySelector('dialog'), null);
});

test('returning to talent discovery closes private evidence while retaining its list', async () => {
  await mount('team@example.test');
  await click('Discover talent');
  await click('View evidence');
  assert.ok(document.querySelector('dialog'));
  let finish;
  const responses = [];
  state.intercept = (path) =>
    path.includes('/talent-matches?')
      ? new Promise((resolve) => {
          finish = resolve;
          responses.push(path);
        })
      : null;
  await focus();
  assert.ok(document.querySelector('.talent-card'));
  assert.equal(document.querySelector('dialog'), null);
  assert.equal(responses.length, 1);
  await act(async () => finish(failure(403, 'FORBIDDEN')));
  assert.equal(document.querySelector('.talent-card'), null);
});

test('recommendations retain cards during a slow refresh and transient failure, then recover', async () => {
  await mount();
  await click('Recommended opportunities');
  const title = document.querySelector('.recommendation-card h3').textContent;
  let finish;
  state.intercept = (path) =>
    path.startsWith('/me/recommendations?')
      ? new Promise((resolve) => {
          finish = resolve;
        })
      : null;
  await focus();
  assert.equal(document.querySelector('.recommendation-card h3').textContent, title);
  assert.match(text(), /Refreshing…/);
  await act(async () =>
    finish(json({ error: { code: 'SERVICE_UNAVAILABLE', message: 'Service unavailable.' } }, 503))
  );
  assert.equal(document.querySelector('.recommendation-card h3').textContent, title);
  assert.match(text(), /Service unavailable/);
  state.intercept = null;
  await click('Reload latest data');
  assert.equal(document.querySelector('[role="alert"]'), null);
});

for (const [status, code] of [
  [401, 'UNAUTHENTICATED'],
  [403, 'FORBIDDEN'],
  [404, 'NOT_FOUND'],
  [409, 'PROFILE_UNCONFIRMED'],
]) {
  test(`recommendation ${code} clears cards and the open dialog without resurrecting it on recovery`, async () => {
    await mount();
    await click('Recommended opportunities');
    await click('Why this match?');
    assert.ok(document.querySelector('.evidence-row'));
    state.intercept = (path) =>
      path.startsWith('/me/recommendations?') ? failure(status, code) : null;
    await focus();
    assert.equal(document.querySelector('.recommendation-card'), null);
    assert.equal(document.querySelector('dialog'), null);
    state.intercept = null;
    await focus();
    assert.ok(document.querySelector('.recommendation-card'));
    assert.equal(document.querySelector('dialog'), null);
  });
}

test('saved opportunity details close when a successful refresh removes that opportunity', async () => {
  const detail = await fixture('opportunity-published');
  let items = [detail];
  state.intercept = (path) =>
    path.startsWith('/me/saved-opportunities?')
      ? json({ items, page: 1, pageSize: 20, total: items.length })
      : null;
  await mount();
  await click('Saved opportunities');
  await click('View opportunity');
  assert.ok(document.querySelector('dialog'));
  items = [];
  await click('Refresh saved');
  assert.equal(document.querySelector('dialog'), null);
  assert.match(text(), /No saved opportunities here/);
  items = [detail];
  await click('Refresh saved');
  assert.equal(document.querySelector('dialog'), null);
});

test('a confirmed account switch cancels outstanding private reads and ignores their late results', async () => {
  await mount();
  await click('My documents');
  let finish, signal;
  state.intercept = (path, options) =>
    path.startsWith('/me/documents?')
      ? new Promise((resolve) => {
          finish = resolve;
          signal = options.signal;
        })
      : null;
  await click('Refresh status');
  await state.server.dispatch('POST', '/auth/logout');
  await state.server.dispatch('POST', '/auth/login', {
    email: 'team@example.test',
    password: 'Demo1234!',
  });
  await focus();
  assert.equal(signal.aborted, true);
  await act(async () =>
    finish(json({ items: [{ fileName: 'previous-account-secret.pdf' }], total: 1 }))
  );
  assert.doesNotMatch(text(), /previous-account-secret|Your documents/);
  assert.match(text(), /Research team/);
});

test('document polling preserves a dirty review draft without reloading its profile baseline', async (t) => {
  const now = Date.now();
  state.server = createMockServer({ now: () => now });
  await state.server.dispatch('POST', '/auth/login', {
    email: 'talent@example.test',
    password: 'Demo1234!',
  });
  const body = new FormData();
  body.append('file', new File(['%PDF-test'], 'review.pdf', { type: 'application/pdf' }));
  body.append('kind', 'CV');
  await state.server.dispatch('POST', '/me/documents', body);
  const listing = await fixture('document-page');
  const ready = await fixture('document-ready');
  // The mock extraction endpoint supplies review sections for any document in its store.
  const actual = await state.server.dispatch('GET', '/me/documents?page=1');
  const id = actual.items[0].id;
  const extraction = await fixture('extraction-ready');
  state.intercept = (path) => {
    if (path.startsWith('/me/documents?'))
      return json({
        ...listing,
        items: [
          { ...ready, id },
          { ...ready, id: 'pending', status: 'PROCESSING' },
        ],
      });
    if (path.endsWith('/extraction')) return json({ ...extraction, documentId: id });
    return null;
  };
  t.mock.timers.enable({ apis: ['Date', 'setTimeout'], now });
  await mount();
  await click('My documents');
  await click('Review suggestions');
  await change('Institution *', 'Keep my review edits');
  const profileReads = state.requests.filter((r) => r.path === '/me/profile').length;
  await act(async () => t.mock.timers.tick(2000));
  assert.equal(field('Institution *').value, 'Keep my review edits');
  assert.equal(state.requests.filter((r) => r.path === '/me/profile').length, profileReads);
  assert.equal(state.requests.filter((r) => r.path.endsWith('/apply')).length, 0);
});

test('a successful new upload restarts checks after the processing budget expires', async (t) => {
  t.mock.timers.enable({ apis: ['Date', 'setTimeout'], now: Date.now() });
  const pending = await fixture('document-processing');
  state.intercept = (path) =>
    path.startsWith('/me/documents?')
      ? json({ items: [pending], page: 1, pageSize: 20, total: 1 })
      : null;
  await mount();
  await click('My documents');
  await act(async () => t.mock.timers.tick(60000));
  assert.match(text(), /Automatic checks paused/);
  const input = field('Choose a document');
  await act(async () => {
    Object.defineProperty(input, 'files', {
      configurable: true,
      value: [new File(['%PDF-test'], 'new.pdf', { type: 'application/pdf' })],
    });
    input.dispatchEvent(new window.Event('change', { bubbles: true }));
  });
  await act(async () =>
    input
      .closest('form')
      .dispatchEvent(new window.Event('submit', { bubbles: true, cancelable: true }))
  );
  assert.doesNotMatch(text(), /Automatic checks paused/);
  const count = state.requests.filter((r) => r.path.startsWith('/me/documents?')).length;
  await act(async () => t.mock.timers.tick(2000));
  assert.equal(state.requests.filter((r) => r.path.startsWith('/me/documents?')).length, count + 1);
  await click('Enter details manually');
  assert.match(text(), /Tell your research story/);
});
