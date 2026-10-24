import test from 'node:test';
import assert from 'node:assert/strict';
import {
  mount,
  click,
  change,
  field,
  text,
  state,
  json,
  fixture,
  act,
} from './support/app-harness.js';

test('opportunity filters compose, encode literal text, reset pages and recover from empty/error results', async () => {
  const opportunity = await fixture('opportunity-published');
  state.intercept = (path) => {
    if (!path.startsWith('/opportunities?')) return null;
    const query = new URL(path, 'http://test').searchParams;
    if (query.get('q') === 'invalid')
      return json({ error: { code: 'VALIDATION_ERROR', message: 'Invalid filter' } }, 422);
    return json({
      items: query.has('q') ? [] : [opportunity],
      page: Number(query.get('page')),
      pageSize: 1,
      total: query.has('q') ? 0 : 2,
    });
  };
  await mount();
  await click('Opportunities');
  await click('Next');
  await change('Search', 'AI & health');
  await change('University', 'UNSW');
  await act(async () => {
    for (const option of field('Opportunity type').options)
      option.selected = ['PHD', 'MASTERS'].includes(option.value);
    field('Opportunity type').dispatchEvent(new window.Event('change', { bubbles: true }));
  });
  await click('Apply filters');
  const query = new URL(
    state.requests.findLast((r) => r.path.startsWith('/opportunities?')).path,
    'http://test'
  ).searchParams;
  assert.equal(query.get('page'), '1');
  assert.equal(query.get('q'), 'AI & health');
  assert.equal(query.get('university'), 'UNSW');
  assert.deepEqual(query.getAll('opportunityType'), ['PHD', 'MASTERS']);
  assert.match(text(), /No results match these filters/);
  await change('Search', 'invalid');
  await click('Apply filters');
  assert.match(text(), /Invalid filter/);
  assert.equal(field('Search').value, 'invalid');
  await click('Clear filters');
  assert.equal(state.requests.at(-1).path, '/opportunities?scope=published&page=1');
  assert.equal(field('Search').value, '');
  assert.ok(document.querySelector('.opportunity-card'));
});

test('recommendations send filters to the server and clear them without changing confirmation', async () => {
  const profile = await fixture('profile-confirmed');
  const page = await fixture('recommendations');
  state.intercept = (path) => {
    if (path === '/me/profile') return json(profile);
    if (path.startsWith('/me/recommendations?')) return json(page);
    return null;
  };
  await mount();
  await click('Recommended opportunities');
  await change('Search', 'research');
  await change('Deadline from', '2099-01-01T12:00');
  await click('Apply filters');
  const query = new URL(
    state.requests.findLast((r) => r.path.startsWith('/me/recommendations?')).path,
    'http://test'
  ).searchParams;
  assert.equal(query.get('q'), 'research');
  assert.equal(query.get('deadlineFrom'), new Date('2099-01-01T12:00').toISOString());
  await click('Clear filters');
  assert.equal(
    state.requests.findLast((r) => r.path.startsWith('/me/recommendations?')).path,
    '/me/recommendations?page=1'
  );
  assert.ok(!state.requests.some((r) => r.method !== 'GET' && r.path.startsWith('/me/profile')));
});
