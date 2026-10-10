import test from 'node:test';
import assert from 'node:assert/strict';
import {
  act,
  state,
  createMockServer,
  mount,
  click,
  checkbox,
  button,
  field,
  text,
  json,
} from './support/app-harness.js';
import { deferMutation } from './support/deferred-mutation.js';

async function readyDocuments() {
  let now = Date.now();
  state.server = createMockServer({ now: () => now });
  await state.server.dispatch('POST', '/auth/login', {
    email: 'talent@example.test',
    password: 'Demo1234!',
  });
  const form = new FormData();
  form.append('file', new File(['%PDF-test-only'], 'ready.pdf', { type: 'application/pdf' }));
  form.append('kind', 'CV');
  await state.server.dispatch('POST', '/me/documents', form);
  now += 2000;
  await mount();
  await click('My documents');
}

async function startUpload() {
  const input = field('Choose a document');
  await act(async () => {
    Object.defineProperty(input, 'files', {
      configurable: true,
      value: [new File(['%PDF-test-only'], 'pending.pdf', { type: 'application/pdf' })],
    });
    input.dispatchEvent(new window.Event('change', { bubbles: true }));
    input
      .closest('form')
      .dispatchEvent(new window.Event('submit', { bubbles: true, cancelable: true }));
  });
  assert.equal(input.matches(':disabled'), true);
  return input;
}

async function assertNavigationBlocked(action) {
  await click(action);
  assert.match(text(), /Wait for the current operation to finish/);
  assert.equal(button('Discard changes').disabled, true);
  assert.equal(
    state.requests.some((request) => request.path === '/auth/logout'),
    false
  );
  await click('Keep editing');
}

test('opening and closing an idle extraction review cannot release a pending upload', async () => {
  await readyDocuments();
  const finish = deferMutation((path) => path === '/me/documents');
  const input = await startUpload();
  try {
    await assertNavigationBlocked('Enter details manually');
    await click('Review suggestions');
    await click('Cancel');
    assert.equal(input.matches(':disabled'), true);
    await assertNavigationBlocked('Enter details manually');
    await assertNavigationBlocked('Sign out');
  } finally {
    await act(finish);
  }
  assert.match(text(), /Document received/);
  await click('Enter details manually');
  assert.match(text(), /Tell your research story/);
  assert.equal(document.querySelector('dialog'), null);
});

test('a completed extraction import cannot navigate away from another pending upload', async () => {
  await readyDocuments();
  const pending = new Map();
  state.intercept = (path, options, body) => {
    if (options.method === 'POST' && (path === '/me/documents' || path.endsWith('/apply'))) {
      return new Promise((resolve) => {
        pending.set(path, async () =>
          resolve(json(await state.server.dispatch(options.method, path, body)))
        );
      });
    }
    return null;
  };
  const input = await startUpload();
  await click('Review suggestions');
  await checkbox('I understand that importing replaces');
  await click('Apply reviewed sections');
  const applyPath = [...pending.keys()].find((path) => path.endsWith('/apply'));
  assert.ok(applyPath);
  try {
    await act(pending.get(applyPath));
    assert.equal(input.matches(':disabled'), true);
    assert.doesNotMatch(text(), /Tell your research story/);
    assert.match(text(), /Wait for the current operation to finish/);
    assert.equal(button('Discard changes').disabled, true);
    await click('Keep editing');
    await assertNavigationBlocked('Enter details manually');
  } finally {
    await act(pending.get('/me/documents'));
  }
  await click('Enter details manually');
  assert.match(text(), /Tell your research story/);
  assert.equal(document.querySelector('dialog'), null);
});

test('a failed upload releases its guard after an idle extraction review closes', async () => {
  await readyDocuments();
  let finish;
  state.intercept = (path, options) => {
    if (path !== '/me/documents' || options.method !== 'POST') return null;
    return new Promise((resolve) => {
      finish = () =>
        resolve(
          json(
            { error: { code: 'INTERNAL_ERROR', message: 'Upload temporarily unavailable.' } },
            503
          )
        );
    });
  };
  const input = await startUpload();
  try {
    await click('Review suggestions');
    await click('Cancel');
    await assertNavigationBlocked('Enter details manually');
  } finally {
    await act(finish);
  }
  assert.match(text(), /Upload temporarily unavailable/);
  assert.equal(input.matches(':disabled'), false);
  await click('Enter details manually');
  assert.match(text(), /Tell your research story/);
  assert.equal(document.querySelector('dialog'), null);
});
