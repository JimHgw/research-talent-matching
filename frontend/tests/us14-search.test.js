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
  button,
} from './support/app-harness.js';

async function selectFilter(label, option) {
  await click(label);
  const target = [...document.querySelectorAll('[role="option"]')].find(
    (item) => item.querySelector('span:last-child').textContent === option
  );
  assert.ok(target, `Missing option: ${option}`);
  await act(async () => target.click());
  assert.equal(button(label).getAttribute('aria-expanded'), 'false');
  assert.equal(document.querySelector('[role="listbox"]'), null);
}

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
  await change('Organisation', 'UNSW');
  await selectFilter('Opportunity type', 'PhD');
  await selectFilter('Opportunity type', 'Masters');
  assert.equal(button('Opportunity type').textContent, 'PhDMasters');
  assert.ok(!button('Opportunity type').textContent.includes('Postdoctoral'));
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

test('team school filter replaces the previous school and sends only one value', async () => {
  const opportunity = await fixture('opportunity-published');
  const talentPage = await fixture('team-talent-page');
  state.intercept = (path) => {
    if (path.startsWith('/opportunities?'))
      return json({ items: [opportunity], page: 1, pageSize: 20, total: 1 });
    if (path.includes('/talent-matches?')) return json(talentPage);
    return null;
  };
  await mount('team@example.test');
  await click('Discover talent');
  assert.equal(field('Skills').tagName, 'INPUT');
  assert.equal(document.querySelector('.search-filters select'), null);
  assert.ok(!document.querySelector('.search-filters').textContent.includes('Research interests'));
  await change('Skills', 'Quantum sensor calibration');
  await click('University');
  assert.equal(document.querySelectorAll('[role="option"]').length, 8);
  assert.equal(
    document.querySelector('[role="listbox"]').getAttribute('aria-multiselectable'),
    'false'
  );
  await act(async () =>
    document.body.dispatchEvent(new window.Event('pointerdown', { bubbles: true }))
  );
  assert.equal(document.querySelector('[role="listbox"]'), null);
  await selectFilter('University', 'UNSW Sydney');
  await selectFilter('University', 'University of Sydney');
  assert.equal(button('University').textContent, 'University of Sydney');
  await click('University');
  assert.equal(document.querySelectorAll('[role="option"][aria-selected="true"]').length, 1);
  const selectedSchool = document.querySelector('[role="option"][aria-selected="true"]');
  await act(async () => selectedSchool.click());
  assert.equal(button('University').textContent, 'University of Sydney');
  await click('Apply filters');
  const query = new URL(
    state.requests.findLast((r) => r.path.includes('/talent-matches?')).path,
    'http://test'
  ).searchParams;
  assert.equal(query.get('skill'), 'Quantum sensor calibration');
  assert.deepEqual(query.getAll('university'), ['USYD']);
  assert.equal(query.has('skillTagId'), false);
  assert.equal(query.has('interestTagId'), false);
  await click('Clear filters');
  assert.equal(field('Skills').value, '');
  assert.equal(button('University').textContent, 'Not specified');
  assert.equal(
    state.requests.findLast((r) => r.path.includes('/talent-matches?')).path,
    `/opportunities/${opportunity.id}/talent-matches?page=1`
  );
});

test('collapsed multi-select toggles options and supports keyboard, Escape and outside focus', async () => {
  await mount();
  await click('Opportunities');
  const trigger = button('Discipline group');
  await act(async () => {
    trigger.focus();
    trigger.dispatchEvent(new window.KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }));
  });
  assert.equal(trigger.getAttribute('aria-expanded'), 'true');
  assert.equal(document.activeElement.getAttribute('role'), 'option');
  await act(async () =>
    document.activeElement.dispatchEvent(
      new window.KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true })
    )
  );
  await act(async () => document.activeElement.click());
  assert.equal(trigger.textContent, 'BUSINESS');
  assert.equal(document.activeElement, trigger);
  await selectFilter('Discipline group', 'STEM');
  assert.equal(trigger.textContent, 'STEMBUSINESS');
  await selectFilter('Discipline group', 'BUSINESS');
  assert.equal(trigger.textContent, 'STEM');
  await click('Discipline group');
  await act(async () =>
    trigger.dispatchEvent(new window.KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
  );
  assert.equal(trigger.getAttribute('aria-expanded'), 'false');
  assert.equal(document.activeElement, trigger);
  await click('Discipline group');
  await act(async () => field('Search').focus());
  assert.equal(document.querySelector('[role="listbox"]'), null);
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
