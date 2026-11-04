import { OpportunityContent } from '../src/features/opportunities/OpportunityDetails.jsx';
import test from 'node:test';
import assert from 'node:assert/strict';
import {
  mount,
  click,
  change,
  text,
  state,
  json,
  fixture,
  React,
  act,
} from './support/app-harness.js';
import { validateOpportunity } from '../src/features/opportunities/fields.js';

const examples = [
  [
    'EDUCATION',
    'Education',
    { qualification: 'Master of Data Science' },
    'Qualification',
    'Master of IT',
  ],
  [
    'RESEARCH_EXPERIENCE',
    'Research experience',
    { title: 'Research Assistant', organisation: 'UNSW' },
    'Organisation',
    'Laboratory A',
  ],
  [
    'RESEARCH_OUTPUT',
    'Research outputs',
    { type: 'PUBLICATION', title: 'Baseline study' },
    'Type',
    'PROJECT',
  ],
];

for (const [kind, label, criteria, field, next] of examples) {
  test(`${kind}: edit the title and criteria without tags, and display the correct type`, async () => {
    const item = await fixture('opportunity-published');
    item.content.requirements = [
      {
        id: 'req_academic',
        label: 'Academic requirement',
        kind,
        importance: 'REQUIRED',
        tagIds: [],
        criteria,
      },
    ];
    state.intercept = (path, options, body) => {
      if (path.startsWith('/opportunities?'))
        return json({ items: [item], page: 1, pageSize: 20, total: 1 });
      if (path === `/opportunities/${item.id}` && options.method === 'PUT') {
        assert.equal(validateOpportunity(body.content, [], 'PUBLISHED'), null);
        return json({ ...item, content: body.content, revision: item.revision + 1 });
      }
      return null;
    };
    await mount('team@example.test');
    await click('My opportunities');
    await click('Edit');
    await change('Opportunity title *', 'Updated academic opportunity');
    await click('Save opportunity');
    assert.deepEqual(
      state.requests.find((r) => r.method === 'PUT').body.content.requirements[0].criteria,
      criteria
    );
    await click('Edit');
    await change(field, next);
    await click('Save opportunity');
    const saved = state.requests.filter((r) => r.method === 'PUT').at(-1).body.content
      .requirements[0];
    assert.equal(
      saved.criteria[Object.keys(criteria).find((key) => key === field.toLowerCase())],
      next
    );
    await click('Edit');
    await change('Kind', 'SKILL');
    await change('Skill names for requirement 1', 'Python');
    await click('Save opportunity');
    const switched = state.requests.filter((r) => r.method === 'PUT').at(-1).body.content
      .requirements[0];
    assert.equal(Object.hasOwn(switched, 'criteria'), false);
    await act(async () =>
      state.root.render(
        React.createElement(OpportunityContent, { content: item.content, tags: [] })
      )
    );
    assert.match(text(), new RegExp(label));
    assert.doesNotMatch(text(), /Research interest/);
    assert.ok(
      text().includes(
        Object.values(criteria)[0] === 'PUBLICATION' ? 'Publication' : Object.values(criteria)[0]
      )
    );
  });
}

test('academic validation rejects empty, unknown, oversized or incompatible criteria', async () => {
  const content = await fixture('opportunity-create');
  const row = {
    id: 'req_a',
    label: 'Academic requirement',
    kind: 'EDUCATION',
    importance: 'REQUIRED',
    tagIds: [],
  };
  for (const criteria of [
    {},
    { qualification: ' ' },
    { qualification: 'x'.repeat(201) },
    { unknown: 'Master' },
  ]) {
    content.requirements = [{ ...row, criteria }];
    assert.equal(
      validateOpportunity(content, [], 'PUBLISHED'),
      'Check the academic requirement criteria.'
    );
  }
  for (const patch of [{ tagIds: ['tag_1'] }, { skillTitles: [] }]) {
    content.requirements = [{ ...row, criteria: { qualification: 'Master' }, ...patch }];
    assert.ok(validateOpportunity(content, [], 'PUBLISHED'));
  }
});

test('switching to academic criteria removes skill fields and requires at least one criterion', async () => {
  await mount('team@example.test');
  await click('My opportunities');
  await click('Edit');
  await change('Kind', 'EDUCATION');
  await click('Save opportunity');
  assert.match(text(), /Check the academic requirement criteria/);
  assert.equal(
    state.requests.some((r) => r.method === 'PUT'),
    false
  );
});

test('create academic requirements in the full-page editor without incompatible fields', async () => {
  const item = await fixture('opportunity-published');
  state.intercept = (path, options, body) => {
    if (path === '/opportunities' && options.method === 'POST') {
      assert.equal(validateOpportunity(body, [], 'DRAFT'), null);
      return json({ ...item, status: 'DRAFT', content: body });
    }
    return null;
  };
  await mount('team@example.test');
  await click('Opportunities');
  await click('Create opportunity');
  for (const [label, value] of Object.entries({
    'Opportunity title': 'Academic opportunity',
    Organisation: 'UNSW',
    Discipline: 'Computing',
    'Research area': 'Data science',
    Description: 'Research project',
  }))
    await change(label, value);
  for (const [index, [kind, , , field, value]] of examples.entries()) {
    await click('Add requirement');
    await change(`Requirement ${index + 1} label`, `Academic check ${index + 1}`);
    await change(`Requirement ${index + 1} kind`, kind);
    await change(field, value, document.querySelectorAll('.requirement-card')[index]);
  }
  await click('Save draft');
  const requirements = state.requests.find(
    (r) => r.path === '/opportunities' && r.method === 'POST'
  ).body.requirements;
  assert.deepEqual(
    requirements.map((r) => r.kind),
    examples.map((r) => r[0])
  );
  assert.ok(requirements.every((r) => !r.tagIds.length && !Object.hasOwn(r, 'skillTitles')));
});
