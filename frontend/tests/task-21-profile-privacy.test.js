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

test('unsaved navigation can be cancelled or explicitly discarded', async () => {
  await mount();
  await click('My profile');
  await change('Display name', 'Unsaved name');
  await click('Privacy & visibility');
  assert.match(text(), /Leave without saving/);
  await click('Keep editing');
  assert.equal(field('Display name').value, 'Unsaved name');
  await click('Privacy & visibility');
  await click('Discard changes');
  assert.match(text(), /Your profile. Your choice/);
  assert.equal(
    state.requests.some((r) => r.method === 'PUT'),
    false
  );
});

test('revision conflict retains edits and does not automatically retry or confirm', async () => {
  await mount();
  await click('My profile');
  await change('Display name', 'Keep this draft');
  state.intercept = (path, options) =>
    path === '/me/profile' && options.method === 'PUT'
      ? new Response(
          JSON.stringify({
            error: {
              code: 'REVISION_CONFLICT',
              message: 'This record changed. Reload latest data.',
              currentRevision: 99,
            },
          }),
          { status: 409 }
        )
      : null;
  await click('Save changes');
  assert.equal(field('Display name').value, 'Keep this draft');
  assert.match(document.querySelector('[role="alert"]').textContent, /record changed/);
  assert.equal(state.requests.filter((r) => r.method === 'PUT').length, 1);
  assert.equal(button('Confirm profile').disabled, true);
});

test('privacy defaults are displayed and saving visibility does not submit a profile edit', async () => {
  await mount();
  await click('Privacy & visibility');
  const discover = document.querySelector('[aria-label="Allow teams to discover me"]');
  assert.equal(discover.checked, false);
  await act(async () => discover.click());
  await checkbox('Display name');
  await click('Save privacy settings');
  const mutation = state.requests.find((r) => r.method === 'PUT');
  assert.equal(mutation.path, '/me/privacy');
  assert.deepEqual(mutation.body.visibleFields, ['displayName']);
  assert.equal(mutation.body.discoverable, true);
  assert.equal(
    state.requests.some((r) => r.method === 'PUT' && r.path === '/me/profile'),
    false
  );
});

test('rejected profile confirmation leaves the saved revision unconfirmed', async () => {
  await mount('new@example.test');
  await click('My profile');
  await checkbox('I have reviewed my saved profile');
  state.intercept = (path) =>
    path === '/me/profile/confirmation'
      ? json(
          {
            error: {
              code: 'VALIDATION_ERROR',
              message: 'Add academic information before confirmation.',
            },
          },
          422
        )
      : null;
  await click('Confirm profile');
  assert.match(document.querySelector('[role="alert"]').textContent, /Add academic information/);
  assert.match(text(), /Needs confirmation/);
  assert.doesNotMatch(text(), /This version is confirmed|Profile confirmed/);
  assert.equal(state.requests.filter((r) => r.path === '/me/profile/confirmation').length, 1);
});

test('privacy conflict preserves selections and cancelling reload preserves the draft', async () => {
  await mount();
  await click('Privacy & visibility');
  await checkbox('Display name');
  state.intercept = (path, options) =>
    path === '/me/privacy' && options.method === 'PUT'
      ? json(
          {
            error: {
              code: 'REVISION_CONFLICT',
              message: 'Privacy changed in another tab.',
              currentRevision: 3,
            },
          },
          409
        )
      : null;
  await click('Save privacy settings');
  const readCount = state.requests.filter(
    (r) => r.method === 'GET' && r.path === '/me/privacy'
  ).length;
  await click('Reload latest data');
  assert.equal(
    state.requests.filter((r) => r.method === 'GET' && r.path === '/me/privacy').length,
    readCount
  );
  assert.ok(
    [...document.querySelectorAll('.visibility-option')]
      .find((l) => l.textContent === 'Display name')
      .querySelector('input').checked
  );
  assert.doesNotMatch(text(), /Privacy settings saved/);
  window.confirm = () => true;
  await click('Reload latest data');
  assert.equal(button('Save privacy settings').disabled, true);
  assert.equal(document.querySelector('[role="alert"]'), null);
});
