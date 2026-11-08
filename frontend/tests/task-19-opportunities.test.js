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

test('opportunity edits survive cancel, close and Escape until explicitly discarded', async () => {
  await mount('team@example.test');
  await click('My opportunities');
  await click('Edit');
  await change('Opportunity title *', 'Keep my opportunity edits');
  for (const action of ['Cancel', 'Close dialog', 'Escape']) {
    if (action === 'Escape')
      await act(async () =>
        document
          .querySelector('dialog')
          .dispatchEvent(new window.Event('cancel', { cancelable: true }))
      );
    else await click(action);
    assert.match(text(), /Leave without saving/);
    await click('Keep editing');
    assert.equal(field('Opportunity title *').value, 'Keep my opportunity edits');
  }
  const unload = new window.Event('beforeunload', { cancelable: true });
  window.dispatchEvent(unload);
  assert.equal(unload.defaultPrevented, true);
  await click('Cancel');
  await click('Discard changes');
  assert.equal(document.querySelector('dialog'), null);
  assert.equal(
    state.requests.some((r) => r.method === 'PUT'),
    false
  );
  const after = new window.Event('beforeunload', { cancelable: true });
  window.dispatchEvent(after);
  assert.equal(after.defaultPrevented, false);
});

test('opportunity validation prevents blank text, missing skill names and empty published criteria', async () => {
  await mount('team@example.test');
  await click('My opportunities');
  await click('Edit');
  await change('Opportunity title *', '   ');
  await click('Save opportunity');
  assert.match(text(), /non-blank text/);
  await change('Opportunity title *', 'Updated opportunity');
  await change('Skill names for requirement 1', '');
  await act(async () =>
    document
      .querySelector('dialog form')
      .dispatchEvent(new window.Event('submit', { bubbles: true, cancelable: true }))
  );
  assert.match(text(), /Requirement 1 needs a label and 1-20 unique skill names/);
  while (document.querySelector('[aria-label="Remove requirement 1"]'))
    await click('Remove requirement 1');
  await click('Save opportunity');
  assert.match(text(), /Published opportunities need at least one requirement/);
  assert.equal(
    state.requests.some((r) => r.method === 'PUT'),
    false
  );
});

test('empty drafts cannot publish and explain the missing requirement', async () => {
  await mount('team@example.test');
  await click('My opportunities');
  assert.equal(button('Publish').disabled, true);
  assert.match(
    button('Publish').closest('.team-opportunity').textContent,
    /Add a requirement to publish/
  );
  await click('Publish');
  assert.equal(
    state.requests.some((r) => r.path.endsWith('/publish')),
    false
  );
});

test('opportunity conflict keeps edits and reload uses the latest revision on the next save', async () => {
  await mount('team@example.test');
  await click('My opportunities');
  await click('Edit');
  await change('Opportunity title *', 'My first revision');
  let conflict = true;
  const latest = await fixture('opportunity-published');
  latest.revision = 99;
  latest.content.title = 'A colleague updated this';
  state.intercept = (path, options, body) => {
    if (!/^\/opportunities\/[^/?]+$/.test(path)) return null;
    if (options.method === 'GET') return json(latest);
    if (options.method === 'PUT')
      return conflict
        ? json(
            {
              error: {
                code: 'REVISION_CONFLICT',
                message: 'Opportunity changed elsewhere.',
                currentRevision: 99,
              },
            },
            409
          )
        : json({ ...latest, revision: 100, content: body.content });
    return null;
  };
  await click('Save opportunity');
  assert.equal(field('Opportunity title *').value, 'My first revision');
  await click('Reload latest data');
  assert.equal(field('Opportunity title *').value, 'My first revision');
  assert.match(text(), /A colleague updated this/);
  assert.equal(state.requests.filter((r) => r.method === 'PUT').length, 1);
  await click('Use latest version');
  assert.equal(field('Opportunity title *').value, 'A colleague updated this');
  assert.equal(button('Save opportunity').disabled, true);
  conflict = false;
  await change('Opportunity title *', 'Merged opportunity');
  await click('Save opportunity');
  const saves = state.requests.filter((r) => r.method === 'PUT');
  assert.equal(saves.length, 2);
  assert.equal(saves[1].body.expectedRevision, 99);
  assert.equal(document.querySelector('dialog'), null);
});

test('an in-flight opportunity save freezes inputs and cannot be closed or submitted twice', async () => {
  await mount('team@example.test');
  await click('My opportunities');
  await click('Edit');
  await change('Opportunity title *', 'Saving once');
  let finish;
  state.intercept = (path, options, body) =>
    options.method === 'PUT' && path.startsWith('/opportunities/')
      ? new Promise((resolve) => {
          finish = async () => resolve(json(await state.server.dispatch('PUT', path, body)));
        })
      : null;
  await click('Save opportunity');
  assert.equal(document.querySelector('fieldset').disabled, true);
  await click('Close dialog');
  assert.ok(document.querySelector('dialog'));
  await act(async () =>
    document
      .querySelector('dialog form')
      .dispatchEvent(new window.Event('submit', { bubbles: true, cancelable: true }))
  );
  assert.equal(state.requests.filter((r) => r.method === 'PUT').length, 1);
  await act(async () => finish());
  assert.equal(document.querySelector('dialog'), null);
});

test('team creates a draft first and publishes only after a separate action', async () => {
  await mount('team@example.test');
  await click('My opportunities');
  await click('New opportunity');
  await change('Opportunity title *', 'Frontend integration study');
  await change('Organisation *', 'Test University');
  await change('Discipline *', 'Computer Science');
  await change('Research area *', 'Interface testing');
  await change('Description *', 'Synthetic data used by an isolated frontend test.');
  await click('Add requirement');
  await change('Requirement label *', 'Python experience');
  await change('Skill names for requirement 1', 'Python');
  await click('Save draft');
  assert.equal(document.querySelector('dialog'), null);
  assert.equal(
    state.requests.some((r) => r.path.endsWith('/publish')),
    false
  );
  const card = [...document.querySelectorAll('.team-opportunity')].find((c) =>
    c.textContent.includes('Frontend integration study')
  );
  assert.ok(card);
  assert.match(card.textContent, /DRAFT/);
  await act(async () =>
    [...card.querySelectorAll('button')].find((b) => b.textContent === 'Publish').click()
  );
  assert.equal(state.requests.filter((r) => r.path.endsWith('/publish')).length, 1);
  assert.match(
    [...document.querySelectorAll('.team-opportunity')].find((c) =>
      c.textContent.includes('Frontend integration study')
    ).textContent,
    /PUBLISHED/
  );
});

test('opportunity navigation cannot discard an editor draft without confirmation', async () => {
  await mount('team@example.test');
  await click('My opportunities');
  await click('Edit');
  await change('Opportunity title *', 'Preserve during navigation');
  await click('My opportunities');
  await click('Discover talent');
  assert.equal(document.querySelectorAll('dialog').length, 2);
  await act(async () =>
    [...document.querySelectorAll('dialog')].at(-1).querySelector('button').click()
  );
  assert.equal(field('Opportunity title *').value, 'Preserve during navigation');
  await click('Discover talent');
  await click('Discard changes');
  assert.match(text(), /Find people for your next idea/);
  assert.equal(document.querySelector('dialog'), null);
});

test('discover talent passes the selected opportunity through workspace page context', async () => {
  await mount('team@example.test');
  await click('My opportunities');
  const card = document.querySelector('.team-opportunity');
  const opportunities = await state.server.dispatch('GET', '/opportunities?scope=mine&page=1');
  const opportunity = opportunities.items.find(
    (item) => item.content.title === card.querySelector('h3').textContent
  );
  await act(async () =>
    [...card.querySelectorAll('button')]
      .find((b) => b.textContent.startsWith('Discover talent'))
      .click()
  );
  assert.equal(field('Match talent to this opportunity').value, opportunity.id);
  assert.ok(
    state.requests.some((r) =>
      r.path.startsWith('/opportunities/' + opportunity.id + '/talent-matches')
    )
  );
});

test('modal creation checks saved drafts after a lost response instead of creating twice', async () => {
  await mount('team@example.test');
  await click('My opportunities');
  await click('New opportunity');
  for (const [label, value] of Object.entries({
    'Opportunity title *': 'Recovered draft',
    'Organisation *': 'UNSW',
    'Discipline *': 'Computer Science',
    'Research area *': 'Data systems',
    'Description *': 'Synthetic recovery test.',
  }))
    await change(label, value);
  state.intercept = async (path, options, body) => {
    if (path === '/opportunities' && options.method === 'POST') {
      await state.server.dispatch('POST', path, body);
      throw new TypeError('Response lost after commit');
    }
    return null;
  };
  await click('Save draft');
  assert.equal(button('Save draft').disabled, true);
  await act(async () =>
    document
      .querySelector('dialog form')
      .dispatchEvent(new window.Event('submit', { bubbles: true, cancelable: true }))
  );
  assert.equal(
    state.requests.filter((r) => r.path === '/opportunities' && r.method === 'POST').length,
    1
  );
  state.intercept = null;
  await click('Reload latest data');
  await click('Open saved draft: Recovered draft');
  assert.equal(field('Opportunity title *').value, 'Recovered draft');
  assert.equal(button('Save opportunity').disabled, true);
  const result = await state.server.dispatch('GET', '/opportunities?scope=mine&page=1');
  assert.equal(result.items.filter((item) => item.content.title === 'Recovered draft').length, 1);
});
