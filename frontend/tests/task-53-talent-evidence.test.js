import test from 'node:test';
import assert from 'node:assert/strict';
import { mount, click, change, text, state, json, fixture, act } from './support/app-harness.js';

async function teamResults() {
  const list = await fixture('team-talent-page');
  const detail = await fixture('team-match-hidden-skills');
  detail.talent.fields.education = [
    {
      id: 'edu_1',
      institution: 'UNSW Sydney',
      qualification: 'Master of IT',
      discipline: 'Computer Science',
      privateNote: 'HIDDEN_NOTE',
    },
  ];
  detail.talent.fields.researchExperience = [
    {
      id: 'exp_1',
      title: 'Research assistant',
      organisation: 'Data Lab',
      description: 'Built a classification pipeline.',
    },
  ];
  detail.talent.fields.researchOutputs = [
    {
      id: 'out_1',
      title: 'Classification study',
      type: 'PUBLICATION',
      description: 'Compared two baseline models.',
      documentUrl: '/private/CV.pdf',
    },
  ];
  detail.requirements = [
    [
      'EDUCATION',
      'education',
      'edu_1',
      'Academic background',
      'MATCHED',
      'ACADEMIC_CRITERIA_SUPPORTED',
    ],
    [
      'RESEARCH_EXPERIENCE',
      'researchExperience',
      'exp_1',
      'Research experience',
      'PARTIAL',
      'ACADEMIC_CRITERIA_PARTIAL',
    ],
    [
      'RESEARCH_OUTPUT',
      'researchOutputs',
      'out_1',
      'Research output',
      'MATCHED',
      'ACADEMIC_CRITERIA_SUPPORTED',
    ],
    ['SKILL', 'skills', 'missing', 'R programming', 'UNKNOWN', 'INSUFFICIENT_EVIDENCE'],
  ].map(([kind, field, recordId, label, status, reasonCode], i) => ({
    requirement: { id: `req_${i}`, label, kind, importance: 'REQUIRED', tagIds: [] },
    status,
    reasonCode,
    reason: 'Server explanation.',
    evidence:
      status === 'UNKNOWN' ? [] : [{ field, recordId, valueSummary: `Evidence for ${label}` }],
  }));
  state.intercept = (path) => {
    if (path.includes('/talent-matches?')) return json(list);
    if (path.includes('/talent-matches/')) return json(detail);
    return null;
  };
  await mount('team@example.test');
  await click('Discover talent');
  return { list, detail };
}

test('academic explanations display the specific permitted education, experience and output records', async () => {
  await teamResults();
  await click('View evidence');
  const rows = [...document.querySelectorAll('.evidence-row')];
  assert.match(
    rows[0].querySelector('.supporting-record').textContent,
    /Master of IT.*UNSW Sydney/s
  );
  assert.match(
    rows[1].querySelector('.supporting-record').textContent,
    /Research assistant.*Data Lab/s
  );
  assert.match(
    rows[2].querySelector('.supporting-record').textContent,
    /Classification study.*PUBLICATION/s
  );
  assert.equal(rows[3].querySelector('.supporting-record'), null);
  assert.match(rows[3].textContent, /UNKNOWN.*No supporting evidence/s);
  assert.doesNotMatch(text(), /HIDDEN_NOTE|\/private\/CV.pdf|undefined/);
  assert.equal(
    state.requests.some((r) => /\/documents|\/talents\//.test(r.path)),
    false
  );
});

test('missing record references do not borrow unrelated visible records', async () => {
  const { detail } = await teamResults();
  detail.requirements[0].evidence[0].recordId = 'not_shared';
  await click('View evidence');
  assert.equal(
    document.querySelector('.evidence-row').querySelector('.supporting-record .shared-record'),
    null
  );
  assert.match(document.querySelector('.shared-profile').textContent, /Master of IT/);
});

test('unexpected profile fields and private provenance are not rendered', async () => {
  const { detail } = await teamResults();
  detail.talent.fields.resumeDescription = 'PRIVATE_RESUME';
  detail.talent.fields.documentId = 'PRIVATE_DOCUMENT';
  await click('View evidence');
  assert.doesNotMatch(
    document.querySelector('dialog').textContent,
    /PRIVATE_RESUME|PRIVATE_DOCUMENT|HIDDEN_NOTE/
  );
  assert.equal(document.querySelector('dialog a[href*="private"]'), null);
});

test('applying filters hides open evidence while new results are pending', async () => {
  await teamResults();
  await click('View evidence');
  const previous = state.intercept;
  let finish;
  state.intercept = (path) =>
    path.includes('/talent-matches?')
      ? new Promise((resolve) => {
          finish = () => resolve(json({ items: [], total: 0, page: 1, pageSize: 20 }));
        })
      : previous(path);
  await change('Skills', 'SQL');
  await click('Apply filters');
  assert.equal(document.querySelector('dialog'), null);
  await act(async () => finish());
  assert.match(text(), /No results match/);
});

test('academic reason codes translate while original profile text stays unchanged', async () => {
  await teamResults();
  await click('View evidence');
  await change('Language', 'zh-CN');
  assert.match(text(), /一条已确认的记录支持所有结构化条件/);
  assert.match(text(), /部分条件有证据支持/);
  assert.match(text(), /UNSW Sydney/);
  assert.match(text(), /Classification study/);
});
