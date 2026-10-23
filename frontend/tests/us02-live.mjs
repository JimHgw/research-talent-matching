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
  await click('Opportunities');
  await until(() => text().includes('Create your first opportunity'));
  await click('Create opportunity');
  for (const [label, value] of Object.entries({
    'Opportunity title': 'Real HTTP opportunity',
    University: 'UNSW',
    Discipline: 'Computer Science',
    'Research area': 'Data analysis',
    Description: 'Created by the real React editor.',
  }))
    await change(label, value);
  await click('Save draft');
  await until(() => !!button('Publish opportunity'));
  assert.equal(button('Publish opportunity').disabled, true);
  const api = createApi();
  await api.session();
  const draft = (await api.opportunities('mine')).items[0];
  assert.equal(draft.revision, 1);
  assert.equal(draft.status, 'DRAFT');
  assert.equal((await api.opportunities()).total, 0);

  await click('Add requirement');
  await change('Requirement 1 label', 'Python and SQL');
  await change('Skill names for requirement 1', 'Python\nSQL');
  await click('Save changes');
  await until(() => button('Publish opportunity') && !button('Publish opportunity').disabled);
  const withRequirements = await api.opportunity(draft.id);
  assert.equal(withRequirements.revision, 2);
  assert.deepEqual(withRequirements.content.requirements[0].skillTitles, ['Python', 'SQL']);

  // Recreate the React tree and restore the authenticated session from its cookie.
  await remount();
  await until(() => text().includes('Your account'));
  await click('Opportunities');
  await until(() => !!button('View and edit'));
  await click('View and edit');
  await until(() => !!button('Publish opportunity'));
  assert.equal(field('Opportunity title').value, draft.content.title);
  assert.equal(field('Requirement 1 label').value, 'Python and SQL');
  await click('Publish opportunity');
  await until(() => text().includes('Opportunity published.'));
  const published = await api.opportunity(draft.id);
  assert.equal(published.status, 'PUBLISHED');
  assert.equal(published.revision, 3);

  await api.saveOpportunity(draft.id, 3, { ...published.content, title: 'Saved in another tab' });
  await change('Opportunity title', 'My unsaved opportunity');
  await click('Save changes');
  await until(() => text().includes('This opportunity changed.'));
  assert.equal(field('Opportunity title').value, 'My unsaved opportunity');
  await click('Reload latest data');
  await until(() => text().includes('Latest saved version'));
  assert.equal(field('Opportunity title').value, 'My unsaved opportunity');
  assert.match(text(), /Saved in another tab/);
  await click('Continue editing my version');
  await change('Description', 'Manually merged after comparing the versions.');
  await click('Save changes');
  await until(() => button('Save changes')?.disabled && !text().includes('Working…'));
  const edited = await api.opportunity(draft.id);
  assert.equal(edited.revision, 5);
  assert.equal(edited.status, 'PUBLISHED');
  assert.equal(edited.content.title, 'My unsaved opportunity');
  assert.equal(edited.content.requirements[0].id, withRequirements.content.requirements[0].id);
  await click('Sign out');

  await login('talent@example.test');
  await until(() => text().includes('Tell your research story'));
  await click('Opportunities');
  await until(() => !!button('View details'));
  assert.equal(button('Create opportunity'), undefined);
  await click('View details');
  await until(() => text().includes('Manually merged after comparing'));
  assert.match(text(), /Python \+ SQL/);
  assert.equal(button('Save changes'), undefined);
  await api.session();
  await assert.rejects(api.opportunities('mine'), (error) => error.status === 403);
  await click('Sign out');

  await login('team2@example.test');
  await until(() => text().includes('Your account'));
  await click('Opportunities');
  await until(() => text().includes('Create your first opportunity'));
  await click('Published opportunities');
  await until(() => !!button('View details'));
  await click('View details');
  await until(() => text().includes('My unsaved opportunity'));
  assert.equal(button('Save changes'), undefined);
  await api.session();
  await assert.rejects(
    api.saveOpportunity(draft.id, 5, edited.content),
    (error) => error.status === 404
  );
  await assert.rejects(api.publish(draft.id, 5), (error) => error.status === 404);
  await click('Sign out');
  await until(() => text().includes('Welcome to Banana'));
  console.log('US-02 real HTTP integration passed');
} finally {
  await cleanup();
}
