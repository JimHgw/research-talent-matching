import test from 'node:test';
import assert from 'node:assert/strict';
import {
  mount,
  click,
  change,
  checkbox,
  button,
  field,
  text,
  state,
  act,
  json,
  fixture,
} from './support/app-harness.js';

test('recommendations open full opportunity details and then matching evidence', async () => {
  const detail = await fixture('opportunity-published');
  detail.content.description =
    'Full description beyond the card preview.\nA second paragraph of responsibilities.';
  state.intercept = (path, options) =>
    options.method === 'GET' && /^\/opportunities\/[^/?]+$/.test(path) ? json(detail) : null;
  await mount();
  await click('Recommended opportunities');
  const card = [...document.querySelectorAll('.recommendation-card')].find((c) =>
    c.textContent.includes('Research assistant in data science')
  );
  await act(async () =>
    [...card.querySelectorAll('button')]
      .find((b) => b.textContent.startsWith('View opportunity'))
      .click()
  );
  const dialog = document.querySelector('dialog');
  assert.match(dialog.textContent, /A second paragraph of responsibilities/);
  assert.equal(dialog.querySelectorAll('.requirement-list li').length, 4);
  assert.match(dialog.textContent, /Required/);
  assert.match(dialog.textContent, /Preferred/);
  await act(async () =>
    [...dialog.querySelectorAll('button')]
      .find((b) => b.textContent.startsWith('Why this match?'))
      .click()
  );
  assert.equal(document.querySelectorAll('dialog').length, 1);
  assert.equal(document.querySelector('dialog').getAttribute('aria-label'), 'Why this match?');
  assert.equal(document.querySelectorAll('.evidence-row').length, 4);
});

test('unavailable opportunity details show an error and retry without stale content', async () => {
  let missing = true;
  const detail = await fixture('opportunity-published');
  state.intercept = (path) =>
    /^\/opportunities\/[^/?]+$/.test(path)
      ? missing
        ? json({ error: { code: 'NOT_FOUND', message: 'Opportunity no longer available.' } }, 404)
        : json(detail)
      : null;
  await mount();
  await click('Recommended opportunities');
  await click('View opportunity');
  assert.match(document.querySelector('dialog').textContent, /no longer available/);
  assert.equal(document.querySelector('.opportunity-details'), null);
  missing = false;
  await click('Reload latest data');
  assert.ok(document.querySelector('.opportunity-details'));
  assert.equal(document.querySelector('[role="alert"]'), null);
});

test('unavailable matching percentages display as unavailable rather than a numeric percentage', async () => {
  const detail = await fixture('owner-match-four-statuses');
  detail.summary.score = null;
  detail.summary.unknownWeightPercent = null;
  detail.summary.evaluationStatus = 'INSUFFICIENT_CRITERIA';
  detail.requirements = [];
  state.intercept = (path) => (path.startsWith('/me/opportunity-matches/') ? json(detail) : null);
  await mount();
  await click('Recommended opportunities');
  await click('Why this match?');
  assert.match(document.querySelector('.match-metrics').textContent, /Not available/);
  assert.doesNotMatch(
    document.querySelector('.match-metrics').textContent,
    /null|undefined|NaN|—%/
  );
});

test('match explanation displays all four statuses without inventing evidence for Unknown', async () => {
  await mount();
  await click('Recommended opportunities');
  const card = [...document.querySelectorAll('.recommendation-card')].find((c) =>
    c.textContent.includes('Research assistant in data science')
  );
  assert.ok(card);
  await act(async () =>
    [...card.querySelectorAll('button')]
      .find((b) => b.textContent.startsWith('Why this match?'))
      .click()
  );
  const rows = [...document.querySelectorAll('.evidence-row')];
  assert.deepEqual(rows.map((r) => r.querySelector('.badge').textContent).sort(), [
    'GAP',
    'MATCHED',
    'PARTIAL',
    'UNKNOWN',
  ]);
  const unknown = rows.find((r) => r.querySelector('.badge').textContent === 'UNKNOWN');
  assert.equal(unknown.querySelector('.evidence-box'), null);
  assert.match(unknown.textContent, /No supporting evidence/);
  await click('Close dialog');
  assert.equal(document.querySelector('dialog'), null);
});

test('recommendation pages replace old results and enforce first and last page boundaries', async () => {
  const payload = await fixture('recommendations');
  state.intercept = (path) => {
    if (!path.startsWith('/me/recommendations?')) return null;
    const page = Number(new URL(path, 'http://test.local').searchParams.get('page'));
    const data = structuredClone(payload);
    data.page = page;
    data.pageSize = 1;
    data.total = 2;
    data.items[0].opportunity.id = `test-page-${page}`;
    data.items[0].opportunity.content.title = `Research page ${page}`;
    return json(data);
  };
  await mount();
  await click('Recommended opportunities');
  assert.equal(button('Previous').disabled, true);
  await click('Next');
  assert.match(text(), /Research page 2/);
  assert.doesNotMatch(text(), /Research page 1/);
  assert.equal(button('Next').disabled, true);
  await click('Previous');
  assert.match(text(), /Research page 1/);
  assert.equal(document.querySelectorAll('.recommendation-card').length, 1);
});

test('retry recovers a failed recommendation request and handles a valid empty result', async () => {
  state.intercept = (path) =>
    path.startsWith('/me/recommendations?')
      ? json(
          {
            error: {
              code: 'SERVICE_UNAVAILABLE',
              message: 'Recommendations are temporarily unavailable.',
            },
          },
          503
        )
      : null;
  await mount();
  await click('Recommended opportunities');
  assert.equal(document.querySelectorAll('.recommendation-card').length, 0);
  state.intercept = (path) =>
    path.startsWith('/me/recommendations?')
      ? json({ items: [], page: 1, pageSize: 20, total: 0 })
      : null;
  await click('Reload latest data');
  assert.match(text(), /No opportunities just yet/);
  assert.equal(document.querySelector('[role="alert"]'), null);
  assert.equal(document.querySelector('.pager'), null);
});

test('team evidence shows only shared fields and clears stale results on a privacy refresh', async () => {
  const list = await fixture('team-talent-page');
  const detail = await fixture('team-match-hidden-skills');
  let revoked = false;
  state.intercept = (path) => {
    if (!path.includes('/talent-matches')) return null;
    if (path.includes('?')) return json(revoked ? { ...list, items: [], total: 0 } : list);
    return revoked
      ? json({ error: { code: 'NOT_FOUND', message: 'This profile is no longer available.' } }, 404)
      : json(detail);
  };
  await mount('team@example.test');
  await click('My opportunities');
  await click('Discover talent');
  await click('View evidence');
  assert.deepEqual(
    [...document.querySelectorAll('.shared-profile strong')].map((e) => e.textContent),
    ['Display name']
  );
  assert.equal(document.querySelectorAll('.evidence-box').length, 0);
  revoked = true;
  await act(async () => window.dispatchEvent(new window.Event('focus')));
  assert.equal(document.querySelector('dialog'), null);
  assert.equal(document.querySelector('.shared-profile'), null);
  assert.equal(document.querySelectorAll('.evidence-row').length, 0);
  assert.equal(document.querySelectorAll('.talent-card').length, 0);
  assert.doesNotMatch(text(), /Demo Talent A/);
});

test('opening a talent detail after access is revoked shows 404 without profile or evidence', async () => {
  const list = await fixture('team-talent-page');
  state.intercept = (path) =>
    path.includes('/talent-matches')
      ? path.includes('?')
        ? json(list)
        : json(
            { error: { code: 'NOT_FOUND', message: 'This profile is no longer available.' } },
            404
          )
      : null;
  await mount('team@example.test');
  await click('My opportunities');
  await click('Discover talent');
  await click('View evidence');
  const dialog = document.querySelector('dialog');
  assert.match(dialog.querySelector('[role="alert"]').textContent, /no longer available/);
  assert.equal(dialog.querySelector('.shared-profile'), null);
  assert.equal(dialog.querySelector('.evidence-row'), null);
  assert.doesNotMatch(dialog.textContent, /Demo Talent A/);
});

test('unconfirmed profiles see the confirmation gate instead of recommendation results', async () => {
  await mount('new@example.test');
  await click('Recommended opportunities');
  assert.match(text(), /Your profile needs a review/);
  assert.equal(document.querySelector('.recommendation-card'), null);
  await click('Review my profile');
  assert.match(text(), /Tell your research story/);
});

test('matching API failures are shown without synthetic fallback results', async () => {
  state.intercept = (path) =>
    path.startsWith('/me/recommendations?')
      ? json(
          { error: { code: 'NOT_FOUND', message: 'Matching endpoint is not implemented.' } },
          404
        )
      : null;
  await mount();
  await click('Recommended opportunities');
  assert.match(text(), /Matching endpoint is not implemented/);
  assert.equal(document.querySelector('.recommendation-card'), null);
  assert.equal(document.querySelector('.talent-card'), null);
});
