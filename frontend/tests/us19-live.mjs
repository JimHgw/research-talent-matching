import assert from 'node:assert/strict';
import {
  mount,
  remount,
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
  await login('team@example.test');
  await until(() => text().includes('Your account'));
  await click('My opportunities');
  await until(() => text().includes('Your next project starts here'));
  await click('New opportunity');
  for (const [label, value] of Object.entries({
    'Opportunity title *': 'FE19 HTTP integration',
    'University *': 'UNSW',
    'Discipline *': 'Computer Science',
    'Research area *': 'Data systems',
    'Description *': 'Created using the team opportunity editor.',
  })) {
    await change(label, value);
  }
  await click('Add requirement');
  await change('Requirement label *', 'Python experience');
  await checkbox('Python');
  await click('Save draft');
  await until(() => !document.querySelector('dialog') && !!button('Publish'));

  const api = createApi();
  await api.session();
  const draft = (await api.opportunities('mine')).items[0];
  assert.equal(draft.status, 'DRAFT');
  assert.deepEqual(draft.content.requirements[0].tagIds, ['skill_python']);

  await click('Publish');
  await until(() => text().includes('Opportunity published.'));
  assert.equal((await api.opportunity(draft.id)).status, 'PUBLISHED');
  await click('Edit');
  await change('Opportunity title *', 'Local title after conflict');
  const published = await api.opportunity(draft.id);
  await api.saveOpportunity(draft.id, published.revision, {
    ...published.content,
    title: 'Changed by another teammate',
  });
  await click('Save opportunity');
  await until(() => text().includes('This opportunity changed.'));
  assert.equal(field('Opportunity title *').value, 'Local title after conflict');
  await click('Reload latest data');
  await click('Discard and reload');
  await until(() => field('Opportunity title *').value === 'Changed by another teammate');
  await change('Opportunity title *', 'Merged FE19 opportunity');
  await click('Save opportunity');
  await until(() => !document.querySelector('dialog'));
  const saved = await api.opportunity(draft.id);
  assert.equal(saved.content.title, 'Merged FE19 opportunity');
  assert.equal(saved.content.requirements[0].id, draft.content.requirements[0].id);

  await remount();
  await until(() => text().includes('Your account'));
  await click('My opportunities');
  await until(() => text().includes('Merged FE19 opportunity'));
  await click('Sign out');
  await login('talent@example.test');
  await until(() => text().includes('Tell your research story'));
  await click('Opportunities');
  await until(() => !!button('View details'));
  await click('View details');
  await until(() => text().includes('Merged FE19 opportunity'));
  assert.equal(button('Save opportunity'), undefined);
  console.log('US-19 real HTTP integration passed');
} finally {
  await cleanup();
}
