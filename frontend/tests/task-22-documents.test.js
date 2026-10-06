import test from 'node:test';
import assert from 'node:assert/strict';
import {
  App,
  React,
  act,
  createMockServer,
  state,
  mount,
  text,
  button,
  click,
  field,
  change,
  checkbox,
  json,
  fixture,
} from './support/app-harness.js';

test('ready document suggestions require acknowledgement and do not auto-confirm imported data', async () => {
  const time = Date.now();
  let now = time;
  state.server = createMockServer({ now: () => now });
  await state.server.dispatch('POST', '/auth/login', {
    email: 'talent@example.test',
    password: 'Demo1234!',
  });
  const form = new FormData();
  form.append('file', new File(['%PDF-test-only'], 'synthetic.pdf', { type: 'application/pdf' }));
  form.append('kind', 'CV');
  await state.server.dispatch('POST', '/me/documents', form);
  now += 2000;
  await mount();
  await click('My documents');
  await click('Review suggestions');
  assert.equal(button('Apply reviewed sections').disabled, true);
  await checkbox('I understand that importing replaces');
  await click('Apply reviewed sections');
  assert.match(text(), /Tell your research story/);
  assert.match(text(), /Needs confirmation/);
  const call = state.requests.find((r) => r.path.endsWith('/apply'));
  assert.deepEqual(Object.keys(call.body.sections).sort(), ['education', 'skills']);
  assert.equal(
    state.requests.some((r) => r.path === '/me/profile/confirmation'),
    false
  );
});

for (const [status, code, message] of [
  [413, 'UPLOAD_TOO_LARGE', 'Choose a file no larger than 10 MiB.'],
  [415, 'UNSUPPORTED_FILE_TYPE', 'Only PDF and DOCX are supported.'],
]) {
  test(`upload rejection ${status} shows the server error and keeps manual entry available`, async () => {
    await mount();
    await click('My documents');
    const input = field('Choose a document');
    const file = new File(['%PDF-test-only'], 'test-only.pdf', { type: 'application/pdf' });
    await act(async () => {
      Object.defineProperty(input, 'files', { configurable: true, value: [file] });
      input.dispatchEvent(new window.Event('change', { bubbles: true }));
    });
    state.intercept = (path, options) =>
      path === '/me/documents' && options.method === 'POST'
        ? json({ error: { code, message } }, status)
        : null;
    // jsdom cannot populate a native file picker; dispatch the actual form submit.
    await act(async () =>
      input
        .closest('form')
        .dispatchEvent(new window.Event('submit', { bubbles: true, cancelable: true }))
    );
    assert.match(
      document.querySelector('[role="alert"]').textContent,
      new RegExp(message.replace(/[.]/g, '\\.'))
    );
    assert.equal(
      state.requests.filter((r) => r.path === '/me/documents' && r.method === 'POST').length,
      1
    );
    assert.equal(document.querySelectorAll('.document-row').length, 0);
    assert.doesNotMatch(text(), /Document received/);
    await click('Enter details manually');
    assert.match(text(), /Tell your research story/);
  });
}
