import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { CookieJar } from 'jsdom';
import { createApi } from '../src/api/client.js';

// Keep an independent talent session to change consent while the team page is open.
const nativeFetch = globalThis.fetch;
const ownerCookies = new CookieJar();
const owner = createApi({
  fetchImpl: async (url, options) => {
    const origin = 'http://127.0.0.1:5173';
    const headers = new Headers(options.headers);
    headers.set('Cookie', await ownerCookies.getCookieString(origin));
    if (options.method !== 'GET') headers.set('Origin', origin);
    const response = await nativeFetch(process.env.TEST_API_BASE_URL + url, {
      ...options,
      headers,
    });
    for (const cookie of response.headers.getSetCookie())
      await ownerCookies.setCookie(cookie, origin);
    return response;
  },
});
const { mount, cleanup, until, text, click, login, checkbox, act, remount } = await import(
  './support/live-app.js'
);
const fixture = async (name) =>
  JSON.parse(await readFile(new URL(`../../docs/api/examples/${name}.json`, import.meta.url)));

try {
  await mount();
  await login('talent@example.test');
  await until(() => text().includes('Tell your research story'));
  const api = createApi();
  await api.session();
  const profile = await api.saveProfile(0, (await fixture('profile-write')).content);
  await api.confirm(profile.revision);
  await click('Privacy & visibility');
  await until(() => text().includes('Your profile. Your choice.'));
  await act(async () =>
    document.querySelector('input[aria-label="Allow teams to discover me"]').click()
  );
  await checkbox('Display name');
  await checkbox('Skills');
  await click('Save privacy settings');
  await until(() => text().includes('Privacy settings saved.'));
  assert.equal((await api.profile()).confirmation.status, 'CONFIRMED');
  await click('Sign out');

  await owner.session();
  await owner.login('talent@example.test', 'Test-password-123!');
  async function share(fields, discoverable = true) {
    const privacy = await owner.privacy();
    await owner.savePrivacy({
      expectedRevision: privacy.revision,
      discoverable,
      visibleFields: fields,
    });
  }

  await login('team@example.test');
  await until(() => text().includes('Your account'));
  await api.session();
  await click('Discover talent');
  await until(() => text().includes('Publish an opportunity first'));
  const content = await fixture('opportunity-create');
  const opportunity = await api.saveOpportunity(null, null, content);
  await api.publish(opportunity.id, opportunity.revision);
  await api.saveOpportunity(null, null, { ...content, title: 'Draft stays out of discovery' });
  await click('Refresh talent');
  await until(() => !!document.querySelector('.talent-card'));
  assert.equal(document.querySelectorAll('.opportunity-select option').length, 1);
  assert.match(document.querySelector('.talent-card').textContent, /Demo Talent A/);
  await until(() => text().includes('Add to Shortlist'));
  await click('Add to Shortlist');
  await until(() => text().includes('Remove from Shortlist'));
  assert.equal((await api.shortlist(opportunity.id)).total, 1);
  await click('Shortlisted candidates');
  await until(() => text().includes('Remove from Shortlist'));
  await click('Remove from Shortlist');
  await until(() => text().includes('No currently discoverable shortlisted candidates'));
  assert.equal((await api.shortlist(opportunity.id)).total, 0);
  await click('Discover talent');
  await until(() => text().includes('Add to Shortlist'));
  await click('Add to Shortlist');
  await until(() => text().includes('Remove from Shortlist'));
  await click('View evidence');
  await until(() => document.querySelectorAll('.evidence-row').length === 4);
  assert.deepEqual(
    [...document.querySelectorAll('.evidence-row .badge')].map((e) => e.textContent),
    ['MATCHED', 'PARTIAL', 'GAP', 'UNKNOWN']
  );
  assert.deepEqual(
    [...document.querySelectorAll('.shared-profile strong')].map((e) => e.textContent),
    ['Display name', 'Skills']
  );

  await share(['displayName']);
  await click('Close dialog');
  await click('Refresh talent');
  await until(() => document.querySelector('.score-chip')?.textContent === '0/100');
  await click('View evidence');
  await until(() => document.querySelectorAll('.evidence-row').length === 4);
  assert.equal(document.querySelectorAll('.evidence-box').length, 0);
  assert.ok(
    [...document.querySelectorAll('.evidence-row .badge')].every((e) => e.textContent === 'UNKNOWN')
  );
  assert.doesNotMatch(document.querySelector('.shared-profile').textContent, /Skills/);

  await share([]);
  await act(async () => window.dispatchEvent(new window.Event('focus')));
  await until(() =>
    document.querySelector('.talent-card')?.textContent.includes('Anonymous talent')
  );
  assert.equal(document.querySelector('dialog'), null);
  await click('View evidence');
  await until(() => !!document.querySelector('.shared-profile'));
  assert.match(text(), /has not shared any profile fields/);
  assert.deepEqual((await api.shortlist(opportunity.id)).items[0].talent.fields, {});
  await share([], false);
  await act(async () => window.dispatchEvent(new window.Event('focus')));
  await until(() => text().includes('No discoverable talent yet'));
  assert.equal(document.querySelector('.shared-profile'), null);
  assert.equal(document.querySelector('dialog'), null);
  assert.equal((await api.shortlist(opportunity.id)).total, 0);
  await assert.rejects(
    api.collectionState(opportunity.id, profile.talentId),
    (e) => e.status === 404
  );
  await assert.rejects(api.talentMatch(opportunity.id, profile.talentId), (e) => e.status === 404);

  await share(['displayName']);
  await click('Refresh talent');
  await until(() => !!document.querySelector('.talent-card'));
  await owner.saveProfile(profile.revision, {
    ...profile.content,
    displayName: 'Needs reconfirmation',
  });
  await click('Refresh talent');
  await until(() => text().includes('No discoverable talent yet'));
  assert.doesNotMatch(text(), /Demo Talent A|Needs reconfirmation/);
  // Hold the real anonymous response after logout to exercise the CSRF race deterministically.
  const previousFetch = globalThis.fetch;
  let releaseSession;
  let sessionStarted = false;
  const sessionGate = new Promise((resolve) => {
    releaseSession = resolve;
  });
  globalThis.fetch = async (url, options) => {
    const response = await previousFetch(url, options);
    if (url.endsWith('/auth/session')) {
      sessionStarted = true;
      await sessionGate;
    }
    return response;
  };
  try {
    await click('Sign out');
    await until(() => sessionStarted);
    assert.doesNotMatch(text(), /Welcome to Banana|No discoverable talent yet/);
    assert.equal(document.querySelector('input[autocomplete="current-password"]'), null);
  } finally {
    globalThis.fetch = previousFetch;
    await act(async () => releaseSession());
  }
  await login('other@example.test');
  await until(() => text().includes('Tell your research story'));
  assert.equal(document.querySelector('.talent-card'), null);
  await click('Sign out');
  await login('talent@example.test');
  await until(() => text().includes('Tell your research story'));
  await api.session();
  const latest = await api.profile();
  await api.confirm(latest.revision);
  await click('Recommended opportunities');
  await until(() => text().includes('Save Opportunity'));
  await click('Save Opportunity');
  await until(() => text().includes('Remove from Saved'));
  assert.equal((await api.savedOpportunities()).total, 1);
  await click('Saved opportunities');
  await until(() => text().includes('Remove from Saved'));
  await remount();
  await until(() => text().includes('Tell your research story'));
  await click('Saved opportunities');
  await until(() => text().includes('Remove from Saved'));
  await click('Sign out');
  await login('talent@example.test');
  await until(() => text().includes('Tell your research story'));
  await click('Saved opportunities');
  await until(() => text().includes('Remove from Saved'));
  await click('Remove from Saved');
  await until(() => text().includes('No saved opportunities here'));
  await api.session();
  assert.equal((await api.savedOpportunities()).total, 0);
  console.log('US-05 real HTTP integration passed');
} finally {
  await cleanup();
}
