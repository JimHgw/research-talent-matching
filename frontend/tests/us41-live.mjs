import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import {
  act,
  mount,
  remount,
  cleanup,
  until,
  text,
  field,
  change,
  click,
  checkbox,
  button,
  login,
  independentBrowserFetch,
} from './support/live-app.js';
import { createApi } from '../src/api/client.js';

const api = createApi();
const owner = createApi({ fetchImpl: independentBrowserFetch() });
const team = createApi({ fetchImpl: independentBrowserFetch() });
const other = createApi({ fetchImpl: independentBrowserFetch() });
const focus = () => act(async () => window.dispatchEvent(new window.Event('focus')));
const documentId = process.env.TEST_REVIEW_DOCUMENT_ID;
assert.ok(documentId, 'Use the pytest task 41 fixture to supply a processed, private document.');
const fixture = async (name) =>
  JSON.parse(
    await readFile(new URL(`../../docs/api/examples/${name}.json`, import.meta.url), 'utf8')
  );

try {
  await mount();
  await login('talent@example.test');
  await until(() => text().includes('Tell your research story'));
  await api.session();
  assert.deepEqual((await api.privacy()).visibleFields, []);
  assert.equal((await api.privacy()).discoverable, false);
  await change('Display name', 'Task 41 synthetic talent');
  await click('Add education');
  await change('Institution *', 'Synthetic university');
  await change('Qualification *', 'Synthetic degree');
  await click('Save changes');
  await until(() => !field('Display name').matches(':disabled'));
  await click('Recommended opportunities');
  await until(() => text().includes('Your profile needs a review'));
  await click('Review my profile');
  await until(() => !!button('Confirm profile'));
  await checkbox('I have reviewed my saved profile and confirm it reflects my information.');
  await click('Confirm profile');
  await until(() => text().includes('This version is confirmed.'));

  await owner.session();
  await owner.login('talent@example.test', 'Test-password-123!');
  let current = await owner.profile();
  await owner.saveProfile(current.revision, {
    ...current.content,
    displayName: 'Changed in another tab',
    researchInterestText: 'Reviewed research interest description',
    customInterestTags: [{ label: 'Synthetic personal interest' }],
    resumeDescription: 'Private whole-resume description',
  });
  await focus();
  await until(
    () => document.querySelector('.profile-fields input')?.value === 'Changed in another tab'
  );
  assert.equal(button('Confirm profile').disabled, true);
  await checkbox('I have reviewed my saved profile and confirm it reflects my information.');
  await click('Confirm profile');
  await until(() => text().includes('This version is confirmed.'));

  // Reuse the real processed-document fixture. Import is reviewed data, never confirmation.
  current = await api.profile();
  const extraction = await api.extraction(documentId);
  assert.ok(extraction.suggestedSections.skills.length);
  const imported = await api.apply(documentId, current.revision, {
    skills: extraction.suggestedSections.skills,
  });
  await focus();
  await until(() => text().includes(`Saved profile revision ${imported.revision}`));
  assert.match(text(), /Needs confirmation/);
  assert.equal(button('Confirm profile').disabled, true);
  await assert.rejects(api.recommendations(), (e) => e.code === 'PROFILE_UNCONFIRMED');
  assert.ok((await api.download(documentId)).size > 0);
  await checkbox('I have reviewed my saved profile and confirm it reflects my information.');
  await click('Confirm profile');
  await until(() => text().includes('This version is confirmed.'));

  await click('Privacy & visibility');
  await until(() => text().includes('Saved discovery status: Off'));
  const contract = JSON.parse(
    await readFile(new URL('../../docs/api/openapi.json', import.meta.url), 'utf8')
  );
  const allowed = contract.components.schemas.ProfileField.enum;
  const options = [...document.querySelectorAll('.visibility-option input')];
  assert.deepEqual(options.map((input) => input.value).sort(), [...allowed].sort());
  for (const option of options) await act(async () => option.click());
  await click('Save privacy settings');
  await until(() => text().includes('Privacy settings saved.'));
  assert.deepEqual((await api.privacy()).visibleFields, [...allowed].sort());
  const afterPrivacy = await api.profile();
  assert.equal(afterPrivacy.content.resumeDescription, 'Private whole-resume description');
  assert.equal(afterPrivacy.content.researchInterestText, 'Reviewed research interest description');
  assert.equal(afterPrivacy.content.customInterestTags[0].label, 'Synthetic personal interest');
  assert.equal(afterPrivacy.confirmation.status, 'CONFIRMED');
  for (const option of document.querySelectorAll('.visibility-option input')) {
    await act(async () => option.click());
  }
  await act(async () =>
    document.querySelector('[aria-label="Allow teams to discover me"]').click()
  );
  await checkbox('Display name');
  await checkbox('Skills');
  assert.match(text(), /Unsaved privacy changes/);
  await click('Save privacy settings');
  await until(() => text().includes('Saved discovery status: On'));
  await remount();
  await until(() => text().includes('Tell your research story'));
  await click('Privacy & visibility');
  await until(() => text().includes('Saved discovery status: On'));
  const savedPrivacy = await api.privacy();
  assert.deepEqual([...savedPrivacy.visibleFields].sort(), ['displayName', 'skills']);

  await team.session();
  await team.login('team@example.test', 'Test-password-123!');
  const opportunity = await team.saveOpportunity(null, null, await fixture('opportunity-create'));
  await team.publish(opportunity.id, opportunity.revision);
  assert.equal((await team.talents(opportunity.id)).total, 1);
  await assert.rejects(team.download(documentId), (e) => e.status === 403);
  await other.session();
  await other.login('other@example.test', 'Test-password-123!');
  await assert.rejects(other.download(documentId), (e) => e.status === 404);
  await assert.rejects(other.extraction(documentId), (e) => e.status === 404);

  await click('Sign out');
  await login('team@example.test');
  await until(() => text().includes('Your account'));
  await click('Discover talent');
  await until(() => !!document.querySelector('.talent-card'));
  await click('View evidence');
  await until(() => !!document.querySelector('.shared-profile'));
  assert.deepEqual(
    [...document.querySelectorAll('.shared-profile strong')].map((e) => e.textContent),
    ['Display name', 'Skills']
  );
  assert.doesNotMatch(
    document.querySelector('dialog').textContent,
    /talent@example.test|review-cv|\/me\/documents/
  );

  let privacy = await owner.privacy();
  await owner.savePrivacy({
    expectedRevision: privacy.revision,
    discoverable: true,
    visibleFields: ['displayName'],
  });
  await focus();
  await until(() => document.querySelector('dialog') === null);
  await until(() => !!document.querySelector('.talent-card'));
  await click('View evidence');
  await until(() => !!document.querySelector('.shared-profile'));
  assert.deepEqual(
    [...document.querySelectorAll('.shared-profile strong')].map((e) => e.textContent),
    ['Display name']
  );
  assert.equal(document.querySelector('.evidence-box'), null);
  privacy = await owner.privacy();
  await owner.savePrivacy({
    expectedRevision: privacy.revision,
    discoverable: false,
    visibleFields: privacy.visibleFields,
  });
  await click('Close dialog');
  await click('Refresh talent');
  await until(() => text().includes('No discoverable talent yet'));
  assert.equal(document.querySelector('.shared-profile'), null);
  assert.equal(document.querySelector('.talent-card'), null);
  await assert.rejects(team.talentMatch(opportunity.id, current.talentId), (e) => e.status === 404);

  await click('Sign out');
  await login('other@example.test');
  await until(() => text().includes('Tell your research story'));
  assert.equal(field('Display name').value, '');
  assert.equal(document.querySelector('.talent-card'), null);
  await click('Sign out');
  await login('talent@example.test');
  await until(() => text().includes('Tell your research story'));
  await click('Privacy & visibility');
  await until(() => text().includes('Saved discovery status: Off'));
  assert.equal(document.querySelector('[aria-label="Allow teams to discover me"]').checked, false);
  console.log('US-41 real HTTP integration passed');
} finally {
  await cleanup();
}
