import test from 'node:test';
import assert from 'node:assert/strict';
import { mount, click, change, state, json, fixture } from './support/app-harness.js';

test('recommendation cards and details show hybrid ranking separately from coverage and interest', async () => {
  const recommendations = await fixture('recommendations-semantic');
  const detail = await fixture('owner-match-semantic');
  const summary = detail.summary;
  recommendations.items[0].summary = summary;
  state.intercept = (path) =>
    path.startsWith('/me/recommendations?')
      ? json(recommendations)
      : path.startsWith('/me/opportunity-matches/')
        ? json(detail)
        : null;
  await mount();
  await click('Recommended opportunities');
  const card = document.querySelector('.recommendation-card');
  assert.equal(card.querySelector('.score-chip').title, 'Recommendation score');
  assert.ok(
    card.querySelector('.score-chip').textContent.startsWith(`${summary.recommendationScore}`)
  );
  assert.match(
    card.querySelector('.semantic-interest').textContent,
    /Research interest similarity.*80\/100.*Closely related/s
  );
  await click('Why this match?');
  const dialog = document.querySelector('dialog');
  assert.ok(
    dialog.querySelector('.score-large').textContent.startsWith(`${summary.recommendationScore}`)
  );
  assert.match(dialog.querySelector('.match-metrics').textContent, /50.*Evidence coverage/s);
  assert.match(
    dialog.querySelector('.semantic-interest').textContent,
    /Evidence weight 70%; interest weight 30%/
  );
  assert.match(
    dialog.querySelector('.semantic-interest').textContent,
    /skills and qualifications use confirmed evidence/
  );
  assert.equal(dialog.querySelectorAll('.evidence-row').length, detail.requirements.length);
  await change('Language', 'zh-CN');
  assert.match(dialog.querySelector('.semantic-interest').textContent, /研究兴趣相似度.*高度相关/s);
  assert.match(dialog.querySelector('.score-large').textContent, /推荐分数/);
  assert.doesNotMatch(
    dialog.querySelector('.semantic-interest').textContent,
    /Research interest|Closely related/
  );
});

for (const status of ['UNAVAILABLE', 'MISSING_EVIDENCE']) {
  test(`${status}: matching explains the fallback without inventing a similarity percentage`, async () => {
    const detail = await fixture('owner-match-semantic');
    detail.summary.recommendationScore = detail.summary.score;
    detail.summary.semanticInterest = {
      ...detail.summary.semanticInterest,
      status,
      similarity: null,
      score: null,
      relevance: 'UNKNOWN',
      weight: 0,
    };
    state.intercept = (path) => (path.startsWith('/me/opportunity-matches/') ? json(detail) : null);
    await mount();
    await click('Recommended opportunities');
    await click('Why this match?');
    const interest = document.querySelector('dialog .semantic-interest');
    assert.match(interest.textContent, /unavailable; ranked by evidence coverage/);
    assert.doesNotMatch(interest.textContent, /null|NaN|undefined|0\/100|Closely related|weight/);
  });
}

test('team discovery cards and match details use the same semantic score', async () => {
  const page = await fixture('team-talent-page');
  const detail = await fixture('team-match-hidden-skills');
  const summary = (await fixture('owner-match-semantic')).summary;
  detail.summary = summary;
  page.items = [{ ...page.items[0], summary }];
  page.total = 1;
  state.intercept = (path) =>
    path.includes('/talent-matches') ? json(path.includes('?') ? page : detail) : null;
  await mount('team@example.test');
  await click('Discover talent');
  const card = document.querySelector('.talent-card');
  assert.ok(
    card.querySelector('.score-chip').textContent.startsWith(`${summary.recommendationScore}`)
  );
  assert.match(card.querySelector('.semantic-interest').textContent, /Closely related/);
  await click('View evidence');
  assert.ok(
    document
      .querySelector('dialog .score-large')
      .textContent.startsWith(`${summary.recommendationScore}`)
  );
  assert.match(document.querySelector('dialog .semantic-interest').textContent, /80\/100/);
});
