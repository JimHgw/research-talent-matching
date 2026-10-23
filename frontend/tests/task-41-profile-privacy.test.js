import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import {
  act,
  state,
  mount,
  text,
  button,
  click,
  field,
  change,
  checkbox,
  json,
  fixture,
} from './support/app-harness.js';
import { deferMutation } from './support/deferred-mutation.js';

const focus = () => act(async () => window.dispatchEvent(new window.Event('focus')));
const discover = () => document.querySelector('[aria-label="Allow teams to discover me"]');
const sharedField = (name) =>
  [...document.querySelectorAll('.visibility-option')]
    .find((label) => label.textContent === name)
    .querySelector('input');
const contract = JSON.parse(
  await readFile(new URL('../../docs/api/openapi.json', import.meta.url), 'utf8')
);

async function editElsewhere(name) {
  const profile = await state.server.dispatch('GET', '/me/profile');
  return state.server.dispatch('PUT', '/me/profile', {
    expectedRevision: profile.revision,
    content: { ...profile.content, displayName: name },
  });
}

test('privacy options and the saved request contain only fields accepted by the API contract', async () => {
  await mount();
  await click('Privacy & visibility');
  const options = [...document.querySelectorAll('.visibility-option input')];
  const allowed = contract.components.schemas.ProfileField.enum;
  assert.deepEqual(options.map((input) => input.value).sort(), [...allowed].sort());
  for (const label of document.querySelectorAll('.visibility-option span')) {
    await checkbox(label.textContent);
  }
  await click('Save privacy settings');
  const request = state.requests.findLast((r) => r.path === '/me/privacy' && r.method === 'PUT');
  assert.deepEqual([...request.body.visibleFields].sort(), [...allowed].sort());
  const saved = await state.server.dispatch('GET', '/me/privacy');
  assert.deepEqual([...saved.visibleFields].sort(), [...allowed].sort());
});

test('grouped interest components and the private resume have no independent privacy checkbox', async () => {
  await mount();
  await click('Privacy & visibility');
  const choices = [...document.querySelectorAll('.visibility-option span')].map(
    (node) => node.textContent
  );
  assert.ok(choices.includes('Research interests'));
  assert.ok(!choices.includes('Research interest description'));
  assert.ok(!choices.includes('Personal interest tags'));
  assert.ok(!choices.includes('Resume description'));
  assert.match(
    text(),
    /Research interests also controls your research interest description and personal interest tags/
  );
  assert.match(text(), /Your resume description always stays private/);
});

test('skills need only a free-text title and supporting evidence even with no skill tags', async () => {
  const vocabulary = await fixture('tags');
  state.intercept = (path) =>
    path === '/tags'
      ? json({ items: vocabulary.items.filter((tag) => tag.kind === 'INTEREST') })
      : null;
  await mount('new@example.test');
  assert.equal(button('Add skill').disabled, false);
  await click('Add skill');
  const record = document.querySelector('.record');
  assert.deepEqual(
    [...record.querySelectorAll('label > span')].map((node) => node.textContent),
    ['Skill title', 'Supporting evidence']
  );
  assert.equal(record.querySelectorAll('select').length, 0);
  assert.equal(field('Skill title').maxLength, 350);
  assert.equal(field('Supporting evidence').maxLength, 2000);
  await change('Skill title', 'Financial modelling');
  await change('Supporting evidence', 'Built a cash-flow forecast.');
  await click('Save changes');
  const saved = await state.server.dispatch('GET', '/me/profile');
  assert.equal(saved.content.skills[0].title, 'Financial modelling');
  assert.equal(saved.content.skills[0].evidenceText, 'Built a cash-flow forecast.');
  assert.deepEqual(Object.keys(saved.content.skills[0]).sort(), ['evidenceText', 'id', 'title']);
  assert.equal(saved.confirmation.status, 'UNCONFIRMED');
  await click('Refresh profile');
  assert.equal(field('Skill title').value, 'Financial modelling');
  await click('Remove skill 1');
  await click('Save changes');
  assert.deepEqual((await state.server.dispatch('GET', '/me/profile')).content.skills, []);
});

test('a clean profile refreshes saved edits from another tab and requires review of the new revision', async () => {
  await mount();
  await editElsewhere('Changed in another tab');
  await focus();
  assert.equal(field('Display name').value, 'Changed in another tab');
  assert.match(text(), /Needs confirmation/);
  assert.equal(button('Confirm profile').disabled, true);
  await checkbox('I have reviewed my saved profile');
  await click('Confirm profile');
  assert.match(text(), /This version is confirmed/);
});

test('profile refresh preserves dirty input on focus and only discards it after explicit consent', async () => {
  await mount();
  await change('Display name', 'Keep my local draft');
  await editElsewhere('Latest saved profile');
  await focus();
  assert.equal(field('Display name').value, 'Keep my local draft');
  await click('Refresh profile');
  assert.equal(field('Display name').value, 'Keep my local draft');
  window.confirm = () => true;
  await click('Refresh profile');
  assert.equal(field('Display name').value, 'Latest saved profile');
  assert.equal(button('Confirm profile').disabled, true);
  assert.equal(
    state.requests.some((r) => r.method === 'PUT'),
    false
  );
});

test('privacy refresh reflects saved consent and visibility from another tab', async () => {
  await mount();
  await click('Privacy & visibility');
  const privacy = await state.server.dispatch('GET', '/me/privacy');
  await state.server.dispatch('PUT', '/me/privacy', {
    expectedRevision: privacy.revision,
    discoverable: true,
    visibleFields: ['displayName'],
  });
  await focus();
  assert.equal(discover().checked, true);
  assert.equal(sharedField('Display name').checked, true);
  assert.match(text(), /Saved discovery status: On/);
  assert.equal(button('Save privacy settings').disabled, true);
});

test('privacy draft changes do not claim saved consent and guarded refresh preserves or replaces them', async () => {
  await mount();
  await click('Privacy & visibility');
  await act(async () => discover().click());
  await checkbox('Skills');
  await focus();
  assert.equal(discover().checked, true);
  assert.match(text(), /Saved discovery status: Off/);
  assert.match(text(), /Unsaved privacy changes/);
  await click('Refresh privacy settings');
  assert.equal(sharedField('Skills').checked, true);
  window.confirm = () => true;
  await click('Refresh privacy settings');
  assert.equal(discover().checked, false);
  assert.equal(sharedField('Skills').checked, false);
  assert.equal(button('Save privacy settings').disabled, true);
});

test('stale confirmation disables repeat confirmation until the current saved revision is reviewed', async () => {
  await mount('new@example.test');
  await checkbox('I have reviewed my saved profile');
  await editElsewhere('New saved revision');
  await click('Confirm profile');
  assert.equal(button('Confirm profile').disabled, true);
  assert.match(text(), /Reload/);
  await click('Reload latest data');
  assert.equal(field('Display name').value, 'New saved revision');
  assert.equal(button('Confirm profile').disabled, true);
});

test('a confirmation for an older revision never marks the current profile confirmed', async () => {
  const profile = await fixture('profile-confirmed');
  profile.confirmation.confirmedRevision = profile.revision - 1;
  state.intercept = (path) => (path === '/me/profile' ? json(profile) : null);
  await mount();
  assert.match(text(), /Needs confirmation/);
  assert.doesNotMatch(text(), /This version is confirmed/);
  assert.equal(button('Confirm profile').disabled, true);
});

for (const entry of ['recommendations', 'saved']) {
  test(`blocked matching from ${entry} links back to the existing profile review flow`, async () => {
    const opportunity = await fixture('opportunity-published');
    state.intercept = (path) => {
      if (path.startsWith('/me/opportunity-matches/'))
        return json(
          { error: { code: 'PROFILE_UNCONFIRMED', message: 'Review your current profile.' } },
          409
        );
      if (path.startsWith('/me/saved-opportunities?'))
        return json({ items: [opportunity], page: 1, pageSize: 20, total: 1 });
      return null;
    };
    await mount();
    await click(entry === 'saved' ? 'Saved opportunities' : 'Recommended opportunities');
    if (entry === 'saved') await click('View opportunity');
    await click('Why this match?');
    assert.match(document.querySelector('dialog').textContent, /Your profile needs a review/);
    assert.equal(document.querySelector('.evidence-row'), null);
    await click('Review my profile');
    assert.equal(document.querySelector('dialog'), null);
    assert.match(text(), /Tell your research story/);
    assert.equal(
      state.requests.some((r) => r.path === '/me/profile/confirmation'),
      false
    );
  });
}

for (const page of ['profile', 'privacy']) {
  test(`${page} refresh cannot replace a pending write or discard the submitted input`, async () => {
    await mount();
    const path = page === 'profile' ? '/me/profile' : '/me/privacy';
    if (page === 'privacy') {
      await click('Privacy & visibility');
      await checkbox('Skills');
    } else await change('Display name', 'Submitted once');
    const reads = () => state.requests.filter((r) => r.path === path && r.method === 'GET').length;
    const before = reads();
    const finish = deferMutation((url) => url === path);
    await click(page === 'profile' ? 'Save changes' : 'Save privacy settings');
    assert.equal(
      button(page === 'profile' ? 'Refresh profile' : 'Refresh privacy settings').disabled,
      true
    );
    await focus();
    assert.equal(reads(), before);
    await act(finish);
    assert.equal(reads(), before);
    assert.equal(state.requests.filter((r) => r.path === path && r.method === 'PUT').length, 1);
    if (page === 'profile') assert.equal(field('Display name').value, 'Submitted once');
    else assert.equal(sharedField('Skills').checked, true);
  });
}
