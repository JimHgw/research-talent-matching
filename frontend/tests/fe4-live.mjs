import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { createApi } from '../src/api/client.js';
import {
  act,
  mount,
  cleanup,
  login,
  until,
  text,
  field,
  change,
  click,
  checkbox,
  button,
  independentBrowserFetch,
} from './support/live-app.js';

const browserApi = createApi();
const collaborator = createApi({ fetchImpl: independentBrowserFetch() });
const fixture = async (name) =>
  JSON.parse(
    await readFile(new URL(`../../docs/api/examples/${name}.json`, import.meta.url), 'utf8')
  );
const nativeBrowserFetch = globalThis.fetch;
const writes = [];
let fault, release;
globalThis.fetch = async (url, options) => {
  if (options.method !== 'GET')
    writes.push({
      url,
      method: options.method,
      body: options.body && typeof options.body === 'string' ? JSON.parse(options.body) : null,
    });
  const response = await nativeBrowserFetch(url, options);
  if (!fault || fault.used || url !== '/api/v1' + fault.path || options.method !== fault.method)
    return response;
  fault.used = true;
  // The request and transaction are real. Only delivery of the committed response is disturbed.
  if (fault.mode === 'lost') throw new TypeError('Response delivery lost after commit');
  if (fault.mode === 'unreadable')
    return new Response('unreadable committed response', { status: 200 });
  return new Promise((resolve) => {
    release = () => resolve(response);
  });
};
const count = (path) => writes.filter((r) => r.url === '/api/v1' + path).length;
async function dialogClick(label) {
  const element = [...document.querySelectorAll('dialog button')].find(
    (node) => node.textContent.trim() === label
  );
  assert.ok(element && !element.disabled, `Missing active dialog button: ${label}`);
  await act(async () => element.click());
}

try {
  await mount();
  await login('talent@example.test');
  await until(() => !!button('Save changes'));
  await change('Display name', 'FE4 synthetic talent');
  await click('Add education');
  await change('Institution *', 'Synthetic university');
  await change('Qualification *', 'Synthetic degree');
  fault = { path: '/me/profile', method: 'PUT', mode: 'lost' };
  await click('Save changes');
  await until(() => text().includes('The request may have succeeded'));
  assert.equal(button('Save changes').disabled, true);
  assert.equal(field('Display name').value, 'FE4 synthetic talent');
  await browserApi.session();
  assert.equal((await browserApi.profile()).revision, 1);
  assert.equal(count('/me/profile'), 1);
  await click('Compare before continuing');
  await until(() => text().includes('Latest saved version'));
  await click('Use latest version');
  assert.equal(button('Save changes').disabled, true);
  assert.equal(button('Confirm profile').disabled, true);
  await checkbox('I have reviewed my saved profile and confirm it reflects my information.');
  await click('Confirm profile');
  await until(() => text().includes('This version is confirmed.'));
  assert.equal((await browserApi.profile()).confirmation.confirmedRevision, 1);

  // A different real session edits the same profile; no response fixture supplies its revision.
  await collaborator.session();
  await collaborator.login('talent@example.test', 'Test-password-123!');
  const before = await collaborator.profile();
  const canonical = await collaborator.saveProfile(before.revision, {
    ...before.content,
    displayName: 'Concurrent saved profile',
  });
  await change('Display name', 'Preserved local reconciliation');
  await click('Save changes');
  await until(() => text().includes('Your profile changed.'));
  assert.equal(field('Display name').value, 'Preserved local reconciliation');
  const beforeCompare = count('/me/profile');
  await click('Compare before continuing');
  await until(() => text().includes('Latest saved version'));
  assert.equal(count('/me/profile'), beforeCompare);
  await click('Continue editing my version');
  await click('Save changes');
  await until(() => !field('Display name').matches(':disabled') && button('Save changes').disabled);
  assert.equal(
    writes.filter((r) => r.url === '/api/v1/me/profile').at(-1).body.expectedRevision,
    canonical.revision
  );
  assert.equal((await browserApi.profile()).confirmation.status, 'UNCONFIRMED');
  await checkbox('I have reviewed my saved profile and confirm it reflects my information.');
  await click('Confirm profile');
  await until(() => text().includes('This version is confirmed.'));

  await click('Privacy & visibility');
  await until(() => !!button('Save privacy settings'));
  await act(async () =>
    document.querySelector('[aria-label="Allow teams to discover me"]').click()
  );
  await checkbox('Display name');
  await checkbox('Skills');
  fault = { path: '/me/privacy', method: 'PUT', mode: 'unreadable' };
  const confirmations = count('/me/profile/confirmation');
  await click('Save privacy settings');
  await until(() => text().includes('The request may have succeeded'));
  assert.match(text(), /Saved discovery status: Off/);
  assert.equal((await browserApi.privacy()).discoverable, true);
  assert.equal(button('Save privacy settings').disabled, true);
  await click('Compare before continuing');
  await until(() => text().includes('Latest saved version'));
  await click('Use latest version');
  assert.match(text(), /Saved discovery status: On/);
  assert.equal(count('/me/profile/confirmation'), confirmations);
  await act(async () =>
    document.querySelector('[aria-label="Allow teams to discover me"]').click()
  );
  await click('Save privacy settings');
  await until(
    () => text().includes('Saved discovery status: Off') && button('Save privacy settings').disabled
  );

  await click('Sign out');
  await login('team@example.test');
  await until(() => text().includes('Your account'));
  await browserApi.session();
  await click('My opportunities');
  await until(() => !!button('Edit'));
  const id = process.env.TEST_FE4_EXPIRED_OPPORTUNITY;
  const expired = await browserApi.opportunity(id);
  assert.equal(expired.availabilityStatus, 'EXPIRED');
  await click('Edit');
  await change('Deadline', '2099-01-01T12:00');
  await click('Save opportunity');
  await until(() => !document.querySelector('dialog'));
  const saved = await browserApi.opportunity(id);
  assert.equal(saved.availabilityStatus, 'EXPIRED');
  assert.equal(
    writes.filter((r) => r.url === `/api/v1/opportunities/${id}`).at(-1).body.reopen,
    undefined
  );
  await click('Edit');
  fault = { path: `/opportunities/${id}`, method: 'PUT', mode: 'lost' };
  await click('Reopen opportunity');
  await until(() => text().includes('The request may have succeeded'));
  assert.equal(button('Reopen opportunity').disabled, true);
  assert.equal((await browserApi.opportunity(id)).availabilityStatus, 'ACTIVE');
  await dialogClick('Reload latest data');
  await until(() => text().includes('Latest saved version'));
  await click('Use latest version');
  assert.equal(button('Reopen opportunity'), undefined);
  await click('Cancel');
  await until(() => !document.querySelector('dialog'));
  await click('Discover talent');
  await until(() => text().includes('No discoverable talent yet'));

  const draft = await browserApi.saveOpportunity(null, null, {
    ...(await fixture('opportunity-create')),
    title: 'FE4 publication recovery',
  });
  await click('My opportunities');
  await until(() => text().includes(draft.content.title));
  fault = { path: `/opportunities/${draft.id}/publish`, method: 'POST', mode: 'lost' };
  const card = [...document.querySelectorAll('.team-opportunity')].find(
    (node) => node.querySelector('h3')?.textContent === draft.content.title
  );
  await act(async () =>
    [...card.querySelectorAll('button')]
      .find((node) => node.textContent.trim() === 'Publish')
      .click()
  );
  await until(() => !!button('Reload latest data'));
  assert.equal((await browserApi.opportunity(draft.id)).status, 'PUBLISHED');
  await click('Reload latest data');
  await until(() => !!document.querySelector('dialog'));
  await dialogClick('Reload latest data');
  await until(() => text().includes('Latest saved version'));
  await click('Use latest version');
  assert.equal(count(`/opportunities/${draft.id}/publish`), 1);
  await click('Cancel');
  await click('Sign out');
  await login('talent@example.test');
  await until(() => !!button('Save changes'));
  await browserApi.session();
  await click('Privacy & visibility');
  await until(() => !!button('Save privacy settings'));
  await checkbox('Education');
  fault = { path: '/me/privacy', method: 'PUT', mode: 'hold' };
  await click('Save privacy settings');
  await until(() => !!release);
  // Switch the actual browser's session, bypassing the elective navigation guard as a second tab can.
  await browserApi.login('other@example.test', 'Test-password-123!');
  await act(async () => window.dispatchEvent(new window.Event('focus')));
  await until(() => !!button('Save changes'));
  await act(async () => release());
  assert.equal(field('Display name').value, '');
  assert.doesNotMatch(text(), /Preserved local reconciliation|Privacy settings saved\./);
  console.log('FE-4 real HTTP recovery and account isolation passed');
} finally {
  release?.();
  globalThis.fetch = nativeBrowserFetch;
  await cleanup();
}
