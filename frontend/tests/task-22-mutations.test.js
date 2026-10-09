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
} from './support/app-harness.js';
import { deferMutation } from './support/deferred-mutation.js';

async function readyReview() {
  let now = Date.now();
  state.server = createMockServer({ now: () => now });
  await state.server.dispatch('POST', '/auth/login', {
    email: 'talent@example.test',
    password: 'Demo1234!',
  });
  const form = new FormData();
  form.append('file', new File(['%PDF-test-only'], 'review.pdf', { type: 'application/pdf' }));
  form.append('kind', 'CV');
  await state.server.dispatch('POST', '/me/documents', form);
  now += 2000;
  await mount();
  await click('My documents');
  await click('Review suggestions');
  await checkbox('I understand that importing replaces');
}

test('pending extraction imports block Cancel, close, Escape and duplicate submissions', async () => {
  await readyReview();
  const finish = deferMutation((path) => path.endsWith('/apply'));
  await click('Apply reviewed sections');
  assert.equal(button('Cancel').disabled, true);
  for (const action of ['Cancel', 'Close dialog']) await click(action);
  const dialog = document.querySelector('dialog');
  await act(async () => dialog.dispatchEvent(new window.Event('cancel', { cancelable: true })));
  assert.equal(document.querySelector('dialog'), dialog);
  await act(async () =>
    dialog
      .querySelector('form')
      .dispatchEvent(new window.Event('submit', { bubbles: true, cancelable: true }))
  );
  assert.equal(state.requests.filter((r) => r.path.endsWith('/apply')).length, 1);
  await act(finish);
  assert.equal(document.querySelector('dialog'), null);
  assert.match(text(), /Tell your research story/);
  await click('Privacy & visibility');
  assert.match(text(), /Your profile. Your choice/);
});

test('pending uploads freeze file controls and protect navigation until completion', async () => {
  await mount();
  await click('My documents');
  const input = field('Choose a document');
  await act(async () => {
    Object.defineProperty(input, 'files', {
      configurable: true,
      value: [new File(['%PDF-test-only'], 'upload.pdf', { type: 'application/pdf' })],
    });
    input.dispatchEvent(new window.Event('change', { bubbles: true }));
  });
  const finish = deferMutation((path) => path === '/me/documents');
  const submit = () =>
    input
      .closest('form')
      .dispatchEvent(new window.Event('submit', { bubbles: true, cancelable: true }));
  await act(async () => submit());
  assert.equal(input.matches(':disabled'), true);
  await act(async () => submit());
  assert.equal(
    state.requests.filter((r) => r.method === 'POST' && r.path === '/me/documents').length,
    1
  );
  await click('Enter details manually');
  assert.equal(button('Discard changes').disabled, true);
  await click('Keep editing');
  await act(finish);
  assert.match(text(), /Document received/);
  await click('Enter details manually');
  assert.match(text(), /Tell your research story/);
});
