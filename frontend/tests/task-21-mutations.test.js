import test from 'node:test';
import assert from 'node:assert/strict';
import {
  act,
  state,
  mount,
  click,
  field,
  change,
  checkbox,
  button,
  text,
} from './support/app-harness.js';
import { deferMutation } from './support/deferred-mutation.js';

test('profile saving freezes the submitted form and prevents duplicate writes', async () => {
  await mount();
  await change('Display name', 'Submitted name');
  const finish = deferMutation((path) => path === '/me/profile');
  await click('Save changes');
  assert.equal(field('Display name').matches(':disabled'), true);
  await change('Display name', 'Input during submission');
  await act(async () =>
    document
      .querySelector('form')
      .dispatchEvent(new window.Event('submit', { bubbles: true, cancelable: true }))
  );
  assert.equal(state.requests.filter((r) => r.method === 'PUT').length, 1);
  await act(finish);
  assert.equal(field('Display name').value, 'Submitted name');
  assert.equal(field('Display name').matches(':disabled'), false);
  await change('Display name', 'Next edit');
  assert.equal(button('Save changes').disabled, false);
});

test('privacy saving freezes visibility choices until the saved revision is received', async () => {
  await mount();
  await click('Privacy & visibility');
  await checkbox('Display name');
  const finish = deferMutation((path) => path === '/me/privacy');
  await click('Save privacy settings');
  const skills = [...document.querySelectorAll('label')]
    .find((l) => l.textContent.trim() === 'Skills')
    .querySelector('input');
  assert.equal(skills.matches(':disabled'), true);
  await checkbox('Skills');
  assert.equal(skills.checked, false);
  await act(finish);
  assert.equal(button('Save privacy settings').disabled, true);
  await checkbox('Skills');
  await click('Save privacy settings');
  await act(finish);
  const writes = state.requests.filter((r) => r.method === 'PUT');
  assert.deepEqual(writes[1].body.visibleFields, ['displayName', 'skills']);
  assert.equal(writes[1].body.expectedRevision, writes[0].body.expectedRevision + 1);
});

test('pending profile writes cannot be discarded through navigation or sign out', async () => {
  await mount();
  await change('Display name', 'Protected submission');
  const finish = deferMutation((path) => path === '/me/profile');
  await click('Save changes');
  await click('Sign out');
  assert.match(text(), /operation to finish/);
  assert.equal(button('Discard changes').disabled, true);
  await click('Discard changes');
  assert.equal(
    state.requests.some((r) => r.path === '/auth/logout'),
    false
  );
  await click('Keep editing');
  await act(finish);
  await click('Privacy & visibility');
  assert.match(text(), /Your profile. Your choice/);
});
