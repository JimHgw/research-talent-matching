import test from 'node:test';
import assert from 'node:assert/strict';
import {
  mount,
  click,
  change,
  checkbox,
  button,
  text,
  state,
  json,
} from './support/app-harness.js';
import { coreWorkspaceConfiguration } from '../src/app/core-workspace-config.jsx';

test('tasks 18/21/22 run without task 19/20 navigation or API requests', async () => {
  await mount('talent@example.test', coreWorkspaceConfiguration);
  assert.match(text(), /Tell your research story/);
  const navigation = document.querySelector('nav').textContent;
  assert.doesNotMatch(navigation, /Opportunities|Discover talent/);
  assert.doesNotMatch(text(), /See recommendations/);
  await click('My documents');
  assert.match(text(), /Add your CV or transcript/);
  await click('Privacy & visibility');
  assert.match(text(), /Your profile. Your choice/);
  assert.equal(
    state.requests.some((r) => /recommendations|opportunities|talent-matches/.test(r.path)),
    false
  );
});

test('the isolated profile flow saves, explicitly confirms and invalidates confirmation after editing', async () => {
  await mount('talent@example.test', coreWorkspaceConfiguration);
  await change('Display name', 'Reviewed talent');
  await click('Save changes');
  assert.match(text(), /Needs confirmation/);
  assert.equal(button('Confirm profile').disabled, true);
  assert.equal(
    state.requests.some((r) => r.path.endsWith('/confirmation')),
    false
  );
  await checkbox('I have reviewed my saved profile');
  await click('Confirm profile');
  assert.match(text(), /This version is confirmed/);
  const saved = state.requests.find((r) => r.method === 'PUT' && r.path === '/me/profile');
  const confirmed = state.requests.find((r) => r.path.endsWith('/confirmation'));
  assert.equal(confirmed.body.expectedRevision, saved.body.expectedRevision + 1);
  await change('Display name', 'Another draft');
  assert.equal(button('Confirm profile').disabled, true);
});

test('the isolated shell signs in a team without loading another task implementation', async () => {
  await mount('team@example.test', coreWorkspaceConfiguration);
  assert.match(text(), /Your account/);
  assert.equal(
    state.requests.some((r) => /opportunities|talent-matches|tags/.test(r.path)),
    false
  );
  await click('Sign out');
  assert.match(text(), /Welcome to Banana/);
});

test('a tag service outage affects editors but does not block privacy or sign out', async () => {
  state.intercept = (path) =>
    path === '/tags'
      ? json({ error: { code: 'SERVICE_UNAVAILABLE', message: 'Tags unavailable.' } }, 503)
      : null;
  await mount('talent@example.test', coreWorkspaceConfiguration);
  assert.match(text(), /Tags unavailable/);
  await click('Privacy & visibility');
  assert.match(text(), /Your profile. Your choice/);
  assert.equal(document.querySelector('[role="alert"]'), null);
  await click('Sign out');
  assert.match(text(), /Welcome to Banana/);
});
