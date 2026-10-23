import test from 'node:test';
import assert from 'node:assert/strict';
import { mount, click, change, text, state, json, fixture } from './support/app-harness.js';

test('discovery finds published opportunities beyond the first page and resets talent pages on selection', async () => {
  const opportunity = await fixture('opportunity-published');
  const talent = (await fixture('team-talent-page')).items[0];
  state.intercept = (path) => {
    if (path.startsWith('/opportunities?scope=mine')) {
      const page = Number(new URL(path, 'http://test').searchParams.get('page'));
      return json({
        items: [{ ...opportunity, id: `opp_${page}`, status: page === 1 ? 'DRAFT' : 'PUBLISHED' }],
        page,
        pageSize: 1,
        total: 3,
      });
    }
    if (path.includes('/talent-matches?')) {
      const page = Number(new URL(path, 'http://test').searchParams.get('page'));
      return json({
        items: [{ ...talent, rank: page, talent: { talentId: `talent_${page}`, fields: {} } }],
        page,
        pageSize: 1,
        total: 2,
      });
    }
    return null;
  };
  await mount('team@example.test');
  await click('Discover talent');
  assert.deepEqual(
    [...document.querySelectorAll('.opportunity-select option')].map((e) => e.value),
    ['opp_2', 'opp_3']
  );
  assert.match(text(), /Anonymous talent/);
  await click('Next');
  assert.match(document.querySelector('.talent-card').textContent, /#2 match/);
  await change('Match talent to this opportunity', 'opp_3');
  assert.match(document.querySelector('.talent-card').textContent, /#1 match/);
  assert.ok(state.requests.some((r) => r.path === '/opportunities/opp_3/talent-matches?page=1'));
  assert.ok(!state.requests.some((r) => r.path.includes('/opp_1/talent-matches')));
});

test('manual refresh removes an open detail and previously shared fields after consent is revoked', async () => {
  const list = await fixture('team-talent-page');
  const detail = await fixture('team-match-hidden-skills');
  let revoked = false;
  state.intercept = (path) => {
    if (!path.includes('/talent-matches')) return null;
    if (path.includes('?')) return json(revoked ? { ...list, items: [], total: 0 } : list);
    return json(detail);
  };
  await mount('team@example.test');
  await click('Discover talent');
  await click('View evidence');
  assert.match(text(), /Demo Talent A/);
  revoked = true;
  await click('Refresh talent');
  assert.equal(document.querySelector('dialog'), null);
  assert.equal(document.querySelector('.talent-card'), null);
  assert.match(text(), /No discoverable talent yet/);
  assert.doesNotMatch(text(), /Demo Talent A/);
});

test('talent list failures clear old results and retry can recover an empty list', async () => {
  let failing = true;
  state.intercept = (path) =>
    path.includes('/talent-matches?')
      ? failing
        ? json({ error: { code: 'INTERNAL_ERROR', message: 'Talent discovery unavailable.' } }, 500)
        : json({ items: [], page: 1, pageSize: 20, total: 0 })
      : null;
  await mount('team@example.test');
  await click('Discover talent');
  assert.match(text(), /Talent discovery unavailable/);
  assert.equal(document.querySelector('.talent-card'), null);
  failing = false;
  await click('Reload latest data');
  assert.match(text(), /No discoverable talent yet/);
  assert.equal(document.querySelector('[role="alert"]'), null);
});

test('shared skills display their free-text titles without a skill vocabulary lookup', async () => {
  const list = await fixture('team-talent-page');
  const detail = await fixture('team-match-hidden-skills');
  const fields = {
    skills: [
      { id: 'opaque_27', title: 'Financial modelling', evidenceText: 'Built a valuation model.' },
    ],
    researchInterests: ['opaque_99'],
  };
  list.items[0].talent.fields = fields;
  detail.talent.fields = fields;
  state.intercept = (path) => {
    if (path === '/tags')
      return json({
        items: [
          { id: 'opaque_27', label: 'Python', kind: 'SKILL', disciplineGroups: ['STEM'] },
          {
            id: 'opaque_99',
            label: 'Machine learning',
            kind: 'INTEREST',
            disciplineGroups: ['STEM'],
          },
        ],
      });
    if (path.includes('/talent-matches')) return json(path.includes('?') ? list : detail);
    return null;
  };
  await mount('team@example.test');
  await click('Discover talent');
  assert.match(document.querySelector('.talent-card').textContent, /Financial modelling/);
  await click('View evidence');
  assert.match(
    document.querySelector('.shared-profile').textContent,
    /Financial modelling — Built a valuation model/
  );
  assert.match(document.querySelector('.shared-profile').textContent, /Machine learning/);
  assert.doesNotMatch(text(), /opaque_27|opaque_99/);
});

test('an emptied later talent page offers a return to the first page', async () => {
  const list = await fixture('team-talent-page');
  state.intercept = (path) => {
    if (!path.includes('/talent-matches?')) return null;
    const page = Number(new URL(path, 'http://test').searchParams.get('page'));
    return json({
      ...list,
      page,
      pageSize: 1,
      total: page === 1 ? 2 : 1,
      items: page === 1 ? list.items : [],
    });
  };
  await mount('team@example.test');
  await click('Discover talent');
  await click('Next');
  assert.match(text(), /No talent on this page/);
  await click('Back to first page');
  assert.ok(document.querySelector('.talent-card'));
  const lastDiscovery = state.requests.filter((r) => r.path.includes('/talent-matches?')).at(-1);
  assert.match(lastDiscovery.path, /page=1/);
});
