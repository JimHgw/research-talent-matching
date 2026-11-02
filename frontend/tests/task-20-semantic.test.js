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

test('requirement scores show weights, contributions and semantic sources in English and Chinese', async () => {
  const detail = await fixture('owner-match-requirement-semantic');
  const recommendations = await fixture('recommendations-semantic');
  recommendations.items[0].summary = detail.summary;
  state.intercept = (path) =>
    path.startsWith('/me/recommendations?')
      ? json(recommendations)
      : path.startsWith('/me/opportunity-matches/')
        ? json(detail)
        : null;
  await mount();
  await click('Recommended opportunities');
  assert.match(document.querySelector('.score-chip').textContent, /^70/);
  await click('Why this match?');
  const dialog = document.querySelector('dialog');
  assert.match(dialog.querySelector('.score-large').textContent, /70.*Weighted score/s);
  assert.match(dialog.querySelector('.semantic-interest').textContent, /Required: 2; preferred: 1/);
  assert.doesNotMatch(dialog.querySelector('.semantic-interest').textContent, /70%|30%/);
  assert.equal(dialog.querySelectorAll('.requirement-score').length, 4);
  const scores = dialog.querySelectorAll('.requirement-score');
  assert.match(scores[0].textContent, /100\/100.*Weight: 2.*Total contribution: 33.33/s);
  assert.match(
    scores[1].textContent,
    /80\/100.*Semantic relevance.*Related confirmed skill title/s
  );
  assert.match(scores[2].textContent, /0\/100.*Explicitly reported gap/s);
  assert.match(dialog.querySelector('.match-metrics').textContent, /50.*Evidence coverage/s);
  await change('Language', 'zh-CN');
  assert.match(dialog.querySelector('.score-large').textContent, /加权总分/);
  assert.match(scores[1].textContent, /要求得分.*权重.*对总分的贡献.*语义相关度/s);
  assert.match(dialog.querySelector('.semantic-interest').textContent, /必需项：2；优先项：1/);
});

test('requirement model fallback explains the structured scores', async () => {
  const detail = await fixture('owner-match-requirement-semantic');
  detail.summary.semanticRequirements.status = 'UNAVAILABLE';
  detail.requirements[1].scoring.method = 'UNAVAILABLE';
  detail.requirements[1].scoring.matches = [];
  state.intercept = (path) => (path.startsWith('/me/opportunity-matches/') ? json(detail) : null);
  await mount();
  await click('Recommended opportunities');
  await click('Why this match?');
  const dialog = document.querySelector('dialog');
  assert.match(
    dialog.querySelector('.semantic-interest').textContent,
    /Model unavailable; using structured evidence/
  );
  assert.match(
    dialog.querySelectorAll('.requirement-score')[1].textContent,
    /Model unavailable; using structured evidence/
  );
  assert.doesNotMatch(dialog.textContent, /NaN|undefined|null/);
});
