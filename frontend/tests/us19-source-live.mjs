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
  button,
  independentBrowserFetch,
} from './support/live-app.js';
import { createApi } from '../src/api/client.js';

const input = 'Source URL (optional)';
const first = 'https://example.org/research?q=AI#overview';
const updated = 'https://example.org/updated';
const final = 'https://example.org/added-again';
try {
  await mount();
  await login('team@example.test');
  await until(() => text().includes('Your account'));
  await click('My opportunities');
  await until(() => button('New opportunity'));
  await click('New opportunity');
  for (const [label, value] of Object.entries({
    'Opportunity title *': 'Source URL HTTP regression',
    'Organisation *': 'UNSW',
    'Discipline *': 'Computing',
    'Research area *': 'AI',
    'Description *': 'Source link test opportunity.',
    [input]: first,
  }))
    await change(label, value);
  await click('Add requirement');
  await change('Requirement label *', 'Python');
  await change('Skill names for requirement 1', 'Python');
  await click('Save draft');
  await until(() => !document.querySelector('dialog') && button('Publish'));
  const api = createApi();
  await api.session();
  const draft = (await api.opportunities('mine')).items.find(
    (item) => item.content.title === 'Source URL HTTP regression'
  );
  assert.equal(draft.content.sourceUrl, first);
  await click('Publish');
  // The badge now stays mounted through refresh. Read its updated class directly:
  // jsdom 27 can cache a negative compound selector across this class mutation.
  await until(
    () =>
      document.querySelector('.team-opportunity .badge')?.classList.contains('published') &&
      button('Edit')
  );

  for (const value of [updated, '', final]) {
    await click('Edit');
    await change(input, value);
    await click('Save opportunity');
    await until(() => !document.querySelector('dialog'));
    const saved = await api.opportunity(draft.id);
    if (value) assert.equal(saved.content.sourceUrl, value);
    else assert.equal(Object.hasOwn(saved.content, 'sourceUrl'), false);
    // Remount discards editor state: the empty record must still offer the input.
    await remount();
    await until(() => text().includes('Your account'));
    await click('My opportunities');
    await until(() => button('Edit'));
    await click('Edit');
    assert.equal(field(input).value, value);
    await click('Cancel');
  }

  const other = createApi({ fetchImpl: independentBrowserFetch() });
  await other.session();
  await other.login('team2@example.test', 'Test-password-123!');
  const saved = await api.opportunity(draft.id);
  await assert.rejects(
    other.saveOpportunity(saved.id, saved.revision, { ...saved.content, sourceUrl: updated }),
    (error) => error.status === 404
  );
  assert.equal((await api.opportunity(saved.id)).content.sourceUrl, final);

  await click('Sign out');
  await login('talent@example.test');
  await until(() => text().includes('Tell your research story'));
  await click('Opportunities');
  await until(() => button('View details'));
  await click('View details');
  await until(() => document.querySelector(`a[href="${final}"]`));
  const link = document.querySelector(`a[href="${final}"]`);
  assert.equal(link.target, '_blank');
  assert.match(link.rel, /noopener/);
  assert.match(link.rel, /noreferrer/);
  assert.equal(button('Save opportunity'), undefined);
  console.log('US-19-source real HTTP integration passed');
} finally {
  await cleanup();
}
