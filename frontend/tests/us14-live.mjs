import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { createApi } from '../src/api/client.js';
import {
  mount,
  login,
  until,
  click,
  change,
  field,
  text,
  cleanup,
  independentBrowserFetch,
  requests,
  act,
} from './support/live-app.js';

const fixture = async (name) =>
  JSON.parse(
    await readFile(new URL(`../../docs/api/examples/${name}.json`, import.meta.url), 'utf8')
  );
const owner = createApi({ fetchImpl: independentBrowserFetch() });
const team = createApi({ fetchImpl: independentBrowserFetch() });

try {
  await owner.session();
  await owner.login('talent@example.test', 'Test-password-123!');
  const profile = await owner.saveProfile(0, {
    ...(await fixture('profile-write')).content,
    education: [
      {
        ...(await fixture('profile-write')).content.education[0],
        institution: 'The University of New South Wales',
      },
    ],
    researchInterestText: 'Rare disease imaging',
  });
  await owner.confirm(profile.revision);
  await owner.savePrivacy({
    expectedRevision: 0,
    discoverable: true,
    visibleFields: ['skills', 'researchInterests', 'education'],
  });
  await team.session();
  await team.login('team@example.test', 'Test-password-123!');
  const content = await fixture('opportunity-create');
  const draft = await team.saveOpportunity(null, null, {
    ...content,
    title: 'Imaging research',
    opportunityType: 'PHD',
    deadlineAt: '2099-01-01T00:00:00Z',
  });
  const opportunity = await team.publish(draft.id, draft.revision);
  const other = await team.saveOpportunity(null, null, { ...content, title: 'Other opportunity' });
  await team.publish(other.id, other.revision);

  await mount();
  await login('talent@example.test');
  await until(() => text().includes('Tell your research story'));
  await click('Opportunities');
  await until(() => document.querySelectorAll('.opportunity-card').length === 2);
  await change('Search', 'imaging');
  await change('Organisation', content.university.toLowerCase());
  await click('Apply filters');
  await until(() => document.querySelectorAll('.opportunity-card').length === 1);
  assert.match(document.querySelector('.opportunity-card').textContent, /Imaging research/);
  await change('Search', 'nothing matches');
  await click('Apply filters');
  await until(() => text().includes('No results match these filters.'));
  await click('Clear filters');
  await until(() => document.querySelectorAll('.opportunity-card').length === 2);
  assert.equal(field('Search').value, '');
  await click('Recommended opportunities');
  await until(() => document.querySelectorAll('.recommendation-card').length === 2);
  await change('Search', 'imaging');
  await click('Apply filters');
  await until(() => document.querySelectorAll('.recommendation-card').length === 1);

  await click('Sign out');
  await login('team@example.test');
  await until(() => text().includes('Your account'));
  await click('Discover talent');
  await until(() => !!document.querySelector('.talent-card'));
  await change('Match talent to this opportunity', opportunity.id);
  await until(() => !!document.querySelector('.talent-card'));
  await change('Search', 'rare disease');
  await change('Skills', 'python');
  await click('University');
  assert.equal(document.querySelectorAll('[role="option"]').length, 8);
  await act(async () =>
    [...document.querySelectorAll('[role="option"]')]
      .find((item) => item.textContent.trim() === 'University of Sydney')
      .click()
  );
  await click('University');
  await act(async () =>
    [...document.querySelectorAll('[role="option"]')]
      .find((item) => item.textContent.trim() === 'UNSW Sydney')
      .click()
  );
  assert.equal(document.querySelector('[role="listbox"]'), null);
  await click('Apply filters');
  await until(() => requests.some((r) => r.url.includes('q=rare+disease')));
  await until(() => !!document.querySelector('.talent-card'));
  assert.equal(
    (
      await team.talents(opportunity.id, 1, {
        q: 'rare disease',
        skill: 'python',
        university: 'UNSW',
      })
    ).total,
    1
  );
  let privacy = await owner.privacy();
  await owner.savePrivacy({
    expectedRevision: privacy.revision,
    discoverable: true,
    visibleFields: ['skills'],
  });
  await click('Refresh talent');
  await until(() => text().includes('No results match these filters.'));
  assert.equal(document.querySelector('.talent-card'), null);
  await click('Clear filters');
  await until(() => !!document.querySelector('.talent-card'));
  privacy = await owner.privacy();
  await owner.savePrivacy({
    expectedRevision: privacy.revision,
    discoverable: false,
    visibleFields: [],
  });
  await click('Refresh talent');
  await until(() => text().includes('No discoverable talent yet'));
  console.log('US-14 real HTTP integration passed');
} finally {
  await cleanup();
}
