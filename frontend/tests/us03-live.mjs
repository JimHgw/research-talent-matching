import assert from 'node:assert/strict';
import {
  mount,
  cleanup,
  until,
  text,
  field,
  change,
  click,
  login,
  checkbox,
  button,
} from './support/live-app.js';
import { createApi } from '../src/api/client.js';

try {
  await mount();
  await login('talent@example.test');
  await until(() => text().includes('Tell your research story'));
  await checkbox('I have reviewed my saved profile and confirm it reflects my information.');
  await click('Confirm profile');
  await until(() => !!document.querySelector('[role="alert"]'));
  assert.match(text(), /Needs confirmation/);

  await change('Display name', 'Reviewed HTTP talent');
  await click('Add education');
  await change('Institution *', 'UNSW');
  await change('Qualification *', 'Master of IT');
  await click('Save changes');
  await until(() => !!button('Save changes') && !field('Display name').matches(':disabled'));
  assert.equal(button('Confirm profile').disabled, true);
  await checkbox('I have reviewed my saved profile and confirm it reflects my information.');
  await click('Confirm profile');
  await until(() => text().includes('This version is confirmed.'));
  const api = createApi();
  await api.session();
  const confirmed = await api.profile();
  assert.equal(confirmed.confirmation.confirmedRevision, confirmed.revision);

  await change('Display name', 'Updated HTTP talent');
  await click('Save changes');
  await until(
    () => text().includes('Needs confirmation') && !field('Display name').matches(':disabled')
  );
  const edited = await api.profile();
  assert.equal(edited.confirmation.status, 'UNCONFIRMED');
  assert.equal(edited.confirmation.confirmedRevision, null);
  assert.equal(edited.content.education[0].id, confirmed.content.education[0].id);

  await api.saveProfile(edited.revision, {
    ...edited.content,
    displayName: 'Saved in another tab',
  });
  await checkbox('I have reviewed my saved profile and confirm it reflects my information.');
  await click('Confirm profile');
  await until(() => text().includes('Your profile changed.'));
  assert.equal(field('Display name').value, 'Updated HTTP talent');
  await click('Reload latest data');
  await until(() => document.querySelector('input')?.value === 'Saved in another tab');
  await checkbox('I have reviewed my saved profile and confirm it reflects my information.');
  await click('Confirm profile');
  await until(() => text().includes('This version is confirmed.'));
  const latest = await api.profile();
  assert.equal(latest.confirmation.confirmedRevision, latest.revision);
  console.log('US-03 real HTTP integration passed');
} finally {
  await cleanup();
}
