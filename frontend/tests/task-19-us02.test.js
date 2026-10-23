import test from 'node:test';
import assert from 'node:assert/strict';
import {
  act,
  mount,
  click,
  change,
  checkbox,
  button,
  field,
  text,
  state,
  json,
} from './support/app-harness.js';

async function teamPage() {
  await mount('team@example.test');
  await click('Opportunities');
}
async function newDraft() {
  await teamPage();
  await click('Create opportunity');
  for (const [label, value] of Object.entries({
    'Opportunity title': 'New research project',
    University: 'UNSW',
    Discipline: 'Computer Science',
    'Research area': 'Data systems',
    Description: 'Synthetic research opportunity.',
  }))
    await change(label, value);
}
const writes = () =>
  state.requests.filter((r) => r.method !== 'GET' && r.path.startsWith('/opportunities'));

test('team creates a draft, adds free-text skills and publishes only saved requirements', async () => {
  await newDraft();
  await click('Save draft');
  assert.match(text(), /Opportunity saved/);
  assert.equal(writes()[0].body.title, 'New research project');
  assert.equal('status' in writes()[0].body, false);
  assert.equal(button('Publish opportunity').disabled, true);
  await click('Add requirement');
  await change('Requirement 1 label', 'Python and SQL experience');
  await change('Skill names for requirement 1', 'Python\nSQL');
  assert.equal(button('Publish opportunity').disabled, true);
  await click('Save changes');
  const saved = writes().at(-1).body;
  assert.deepEqual(saved.content.requirements[0].skillTitles, ['Python', 'SQL']);
  assert.equal(saved.expectedRevision, 1);
  assert.equal(button('Publish opportunity').disabled, false);
  await click('Publish opportunity');
  assert.equal(writes().at(-1).body.expectedRevision, 2);
  assert.match(text(), /Opportunity published/);
  assert.match(text(), /PUBLISHED/);
  assert.equal(document.querySelectorAll('button').length > 0, true);
  await click('Back to opportunities');
  assert.match(text(), /New research project/);
});

test('existing requirement IDs survive edits and switching kind clears incompatible tags', async () => {
  await teamPage();
  await click('View and edit');
  const get = state.requests
    .filter((r) => r.method === 'GET' && /^\/opportunities\//.test(r.path))
    .at(-1);
  const original = await state.server.dispatch('GET', get.path);
  await change('Requirement 1 label', 'Changed requirement label');
  await change('Requirement 1 kind', 'INTEREST');
  assert.equal(
    [
      ...document.querySelector('.requirement-card').querySelectorAll('input[type="checkbox"]'),
    ].some((input) => input.checked),
    false
  );
  await checkbox('Machine learning');
  await click('Save changes');
  const requirement = writes().at(-1).body.content.requirements[0];
  assert.equal(requirement.id, original.content.requirements[0].id);
  assert.deepEqual(requirement.tagIds, ['interest_ml']);
  assert.equal('skillTitles' in requirement, false);
  assert.equal(requirement.kind, 'INTEREST');
});

test('arbitrary opportunity skills save without a SKILL vocabulary and survive reopening', async () => {
  state.intercept = (path) =>
    path === '/tags'
      ? json({
          items: [
            {
              id: 'interest_ml',
              kind: 'INTEREST',
              label: 'Machine learning',
              disciplineGroups: ['STEM'],
            },
          ],
        })
      : null;
  await newDraft();
  await click('Add requirement');
  await change('Requirement 1 label', 'Experimental and business methods');
  await change('Skill names for requirement 1', 'CRISPR experimental design\nFinancial modelling');
  assert.equal(document.querySelector('.requirement-card input[type="checkbox"]'), null);
  await click('Save draft');
  const saved = writes().at(-1).body.requirements[0];
  assert.deepEqual(saved.skillTitles, ['CRISPR experimental design', 'Financial modelling']);
  assert.deepEqual(saved.tagIds, []);
  await click('Back to opportunities');
  await click('View and edit');
  assert.equal(
    field('Skill names for requirement 1').value,
    'CRISPR experimental design\nFinancial modelling'
  );
});

test('conflict reload compares versions without overwriting local input or retrying', async () => {
  await teamPage();
  await click('View and edit');
  const get = state.requests
    .filter((r) => r.method === 'GET' && /^\/opportunities\//.test(r.path))
    .at(-1);
  const original = await state.server.dispatch('GET', get.path);
  await state.server.dispatch('PUT', get.path, {
    expectedRevision: original.revision,
    content: { ...original.content, title: 'Saved by another teammate' },
  });
  await change('Opportunity title', 'Keep my local title');
  await click('Save changes');
  assert.equal(field('Opportunity title').value, 'Keep my local title');
  assert.equal(button('Save changes').disabled, true);
  await click('Reload latest data');
  assert.match(text(), /Saved by another teammate/);
  assert.equal(field('Opportunity title').value, 'Keep my local title');
  assert.equal(writes().length, 1);
  await click('Continue editing my version');
  assert.equal(writes().length, 1);
  await change('Description', 'Manually merged description');
  await click('Save changes');
  assert.equal(writes().at(-1).body.expectedRevision, original.revision + 1);
  assert.equal(writes().at(-1).body.content.title, 'Keep my local title');
});

test('failed creation keeps input and checks saved drafts before any manual retry', async () => {
  await newDraft();
  state.intercept = async (path, options, body) => {
    if (path === '/opportunities' && options.method === 'POST') {
      await state.server.dispatch('POST', path, body);
      throw new TypeError('Response lost after commit');
    }
  };
  await click('Save draft');
  assert.equal(writes().length, 1);
  assert.equal(field('Opportunity title').value, 'New research project');
  assert.equal(button('Save draft').disabled, true);
  await click('Reload latest data');
  assert.match(text(), /Recently saved opportunities/);
  await click('Open saved draft: New research project');
  assert.equal(writes().length, 1);
  assert.equal(field('Opportunity title').value, 'New research project');
  assert.match(text(), /Edit opportunity/);
});

test('field errors preserve the editor and unsaved back/navigation can be cancelled', async () => {
  await newDraft();
  state.intercept = (path, options) =>
    path === '/opportunities' && options.method === 'POST'
      ? json(
          {
            error: {
              code: 'VALIDATION_ERROR',
              message: 'Check the submitted fields.',
              fieldErrors: [{ field: 'title', message: 'Title is invalid.' }],
            },
          },
          422
        )
      : null;
  await click('Save draft');
  assert.match(text(), /Title is invalid/);
  assert.equal(field('Opportunity title').value, 'New research project');
  await click('Back to opportunities');
  assert.equal(field('Opportunity title').value, 'New research project');
  await click('Overview');
  assert.match(text(), /Leave without saving/);
  await click('Keep editing');
  assert.equal(field('Opportunity title').value, 'New research project');
  await click('Overview');
  await click('Discard changes');
  assert.match(text(), /Your account/);
});

test('talent can browse published details without management controls', async () => {
  await mount();
  await click('Opportunities');
  assert.equal(
    state.requests.some((r) => r.path.includes('scope=mine')),
    false
  );
  assert.doesNotMatch(text(), /Create opportunity|View and edit|DRAFT/);
  await click('View details');
  assert.match(text(), /Requirements/);
  assert.equal(document.querySelector('form'), null);
  assert.equal(writes().length, 0);
  await click('Back to opportunities');
  await click('Sign out');
  assert.doesNotMatch(text(), /Research assistant in data science/);
});

test('empty lists, service errors, pagination and focus refresh are recoverable', async () => {
  let fail = true;
  let total = 0;
  state.intercept = (path) => {
    if (!path.startsWith('/opportunities?')) return null;
    if (fail) return json({ error: { code: 'INTERNAL_ERROR', message: 'List unavailable.' } }, 500);
    const page = Number(new URL(path, 'http://test').searchParams.get('page'));
    return json({ items: [], page, pageSize: 20, total });
  };
  await teamPage();
  assert.match(text(), /List unavailable/);
  fail = false;
  await click('Reload latest data');
  assert.match(text(), /Create your first opportunity/);
  total = 21;
  await act(async () => window.dispatchEvent(new window.Event('focus')));
  await click('Next');
  assert.match(text(), /No opportunities on this page/);
  assert.match(state.requests.at(-1).path, /page=2/);
  await click('Back to first page');
  assert.match(state.requests.at(-1).path, /page=1/);
});

test('an unavailable detail offers a route back to the refreshed list', async () => {
  await teamPage();
  state.intercept = (path) =>
    /^\/opportunities\//.test(path)
      ? json({ error: { code: 'NOT_FOUND', message: 'Opportunity not found.' } }, 404)
      : null;
  await click('View and edit');
  assert.match(text(), /Opportunity not found/);
  await click('Back to opportunities');
  assert.ok(button('Create opportunity'));
});
