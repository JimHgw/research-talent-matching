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
  React,
} from './support/app-harness.js';
import OpportunityFields from '../src/features/opportunities/OpportunityFields.jsx';
import OpportunityMetadata from '../src/features/opportunities/OpportunityMetadata.jsx';
import { validSourceUrl, futureDeadline } from '../src/features/opportunities/metadata.js';

test('source URL accepts optional HTTP(S), rejects unsafe or malformed destinations', () => {
  for (const value of [
    null,
    '',
    'https://example.org/research?q=AI#details',
    'http://localhost:8000/a',
  ])
    assert.equal(validSourceUrl(value), true);
  for (const value of [
    'javascript:alert(1)',
    'data:text/html,test',
    'file:///tmp/a',
    '//example.org',
    'https:/example.org',
    'https://',
    'https://a b',
    'https://user:password@example.org',
    'https://example.org/\\evil',
    'https://example.org/' + 'a'.repeat(2048),
  ])
    assert.equal(validSourceUrl(value), false, value);
});

test('reopening date boundary is strict, with no deadline permitted', () => {
  const now = Date.parse('2030-01-01T00:00:00Z');
  assert.equal(futureDeadline('2029-12-31T23:59:59.999Z', now), false);
  assert.equal(futureDeadline('2030-01-01T00:00:00Z', now), false);
  assert.equal(futureDeadline('2030-01-01T00:00:00.001Z', now), true);
  assert.equal(futureDeadline(null, now), true);
  assert.equal(futureDeadline('invalid', now), false);
});

test('source field is gated for the legacy backend and supports new content when enabled', async () => {
  const item = await fixture('opportunity-published');
  const render = (sourceEnabled) =>
    act(async () =>
      state.root.render(
        React.createElement(OpportunityFields, {
          content: item.content,
          tags: [],
          sourceEnabled,
          onChange: (next) => {
            item.content = next;
          },
        })
      )
    );
  await render(false);
  assert.ok(!text().includes('Source URL (optional)'));
  await render(true);
  await change('Source URL (optional)', 'https://example.org/new');
  assert.equal(item.content.sourceUrl, 'https://example.org/new');
});

async function ownedItem(availabilityStatus = 'ACTIVE') {
  const item = await fixture('opportunity-published');
  item.availabilityStatus = availabilityStatus;
  item.content.sourceUrl = null;
  if (availabilityStatus === 'EXPIRED') item.content.deadlineAt = '2000-01-01T00:00:00Z';
  state.intercept = (path, options, body) => {
    if (path.startsWith('/opportunities?'))
      return json({ items: [item], page: 1, pageSize: 20, total: 1 });
    if (path === `/opportunities/${item.id}`) {
      if (options.method === 'PUT') {
        item.content = body.content;
        item.revision++;
        if (body.reopen) item.availabilityStatus = 'ACTIVE';
      }
      return json(item);
    }
    return null;
  };
  await mount('team@example.test');
  await click('My opportunities');
  await click('Edit');
  return item;
}

test('source add, edit and explicit removal survive reopening the editor', async () => {
  await ownedItem();
  for (const value of ['https://example.org/first', 'https://example.org/second', '']) {
    await change('Source URL (optional)', value);
    await click('Save opportunity');
    const request = state.requests.findLast((r) => r.method === 'PUT');
    assert.equal(request.body.content.sourceUrl, value || null);
    await click('Edit');
    assert.equal(field('Source URL (optional)').value, value);
  }
});

test('source details open separately and do not render unsafe links', async () => {
  await act(async () =>
    state.root.render(
      React.createElement(OpportunityMetadata, {
        content: { sourceUrl: 'https://example.org/research', deadlineAt: '2030-01-01T00:00:00Z' },
      })
    )
  );
  const link = document.querySelector('a');
  assert.equal(link.target, '_blank');
  assert.match(link.rel, /noopener/);
  assert.equal(document.querySelector('time').dateTime, '2030-01-01T00:00:00Z');
  await act(async () =>
    state.root.render(
      React.createElement(OpportunityMetadata, { content: { sourceUrl: 'javascript:alert(1)' } })
    )
  );
  assert.equal(document.querySelector('a'), null);
});

test('expired opportunity saves a future deadline and explicitly reopens in one revision-checked write', async () => {
  const item = await ownedItem('EXPIRED');
  const revision = item.revision;
  await click('Reopen opportunity');
  assert.match(text(), /Choose a future deadline/);
  assert.equal(state.requests.filter((r) => r.method === 'PUT').length, 0);
  await change('Deadline', '2099-01-01T12:00');
  await click('Save and reopen opportunity');
  const saves = state.requests.filter((r) => r.method === 'PUT');
  assert.equal(saves.length, 1);
  assert.equal(saves[0].body.reopen, true);
  assert.equal(saves[0].body.expectedRevision, revision);
  assert.equal(saves[0].body.content.deadlineAt, new Date('2099-01-01T12:00').toISOString());
  assert.equal(item.availabilityStatus, 'ACTIVE');
});

test('ordinary save with a cleared deadline remains expired until explicit reopen', async () => {
  const item = await ownedItem('EXPIRED');
  await change('Deadline', '');
  await click('Save opportunity');
  assert.equal(item.content.deadlineAt, null);
  assert.equal(item.availabilityStatus, 'EXPIRED');
  assert.equal(state.requests.findLast((r) => r.method === 'PUT').body.reopen, undefined);
  await click('Edit');
  await click('Reopen opportunity');
  assert.equal(state.requests.findLast((r) => r.method === 'PUT').body.reopen, true);
});

test('reopen conflict preserves changed deadline and blocks repeated writes', async () => {
  await ownedItem('EXPIRED');
  const previous = state.intercept;
  state.intercept = (path, options, body) =>
    options.method === 'PUT'
      ? json({ error: { code: 'REVISION_CONFLICT', message: 'Changed elsewhere.' } }, 409)
      : previous(path, options, body);
  await change('Deadline', '2099-01-01T12:00');
  await click('Save and reopen opportunity');
  assert.equal(field('Deadline').value, '2099-01-01T12:00');
  assert.equal(button('Save and reopen opportunity').disabled, true);
  assert.equal(state.requests.filter((r) => r.method === 'PUT').length, 1);
});

test('invalid filter interval does not request data; clear removes the error and applied state', async () => {
  await mount();
  await click('Opportunities');
  await change('Search', 'research');
  await click('Apply filters');
  assert.match(text(), /Active filters: research/);
  await change('Deadline from', '2030-01-02T00:00');
  await change('Deadline before', '2030-01-01T00:00');
  const count = state.requests.length;
  await click('Apply filters');
  assert.equal(state.requests.length, count);
  assert.match(text(), /upper deadline bound/);
  await click('Clear filters');
  assert.ok(!text().includes('Active filters:'));
  assert.ok(!text().includes('upper deadline bound'));
});

test('late search response cannot replace newer results', async () => {
  const item = await fixture('opportunity-published');
  let finish;
  state.intercept = (path) => {
    if (!path.startsWith('/opportunities?')) return null;
    const query = new URL(path, 'http://test').searchParams.get('q');
    if (query === 'old')
      return new Promise((resolve) => {
        finish = () => resolve(json({ items: [item], total: 1, page: 1, pageSize: 20 }));
      });
    return json({ items: [], total: 0, page: 1, pageSize: 20 });
  };
  await mount();
  await click('Opportunities');
  await change('Search', 'old');
  await click('Apply filters');
  await change('Search', 'new');
  await click('Apply filters');
  await act(async () => finish());
  assert.match(text(), /No results match/);
  assert.equal(document.querySelector('.opportunity-card'), null);
});
