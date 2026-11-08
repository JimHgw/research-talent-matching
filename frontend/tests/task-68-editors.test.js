import test from 'node:test';
import assert from 'node:assert/strict';
import {
  act,
  state,
  mount,
  click,
  change,
  checkbox,
  field,
  button,
  text,
  json,
  fixture,
  React,
} from './support/app-harness.js';
import { useProfileEditor } from '../src/features/profile/useProfileEditor.js';
import { usePrivacyEditor } from '../src/features/privacy/usePrivacyEditor.js';
import { invalidateData } from '../src/shared/data-invalidation.js';

const focus = () => act(async () => window.dispatchEvent(new window.Event('focus')));
const writes = (path) => state.requests.filter((r) => r.path === path && r.method === 'PUT');
const discover = () => document.querySelector('[aria-label="Allow teams to discover me"]');
async function open(kind) {
  await mount();
  if (kind === 'privacy') await click('Privacy & visibility');
}
async function edit(kind) {
  if (kind === 'profile') await change('Display name', 'Local recovery draft');
  else {
    await act(async () => discover().click());
    await checkbox('Skills');
  }
}
const saveLabel = (kind) => (kind === 'profile' ? 'Save changes' : 'Save privacy settings');

for (const kind of ['profile', 'privacy']) {
  const path = `/me/${kind}`;
  test(`${kind}: CSRF rejection preserves the draft and saved revision for an explicit retry`, async () => {
    await open(kind);
    const baseline = await state.server.dispatch('GET', path);
    await edit(kind);
    let renewed = false;
    state.intercept = (url, options) => {
      if (url === '/auth/session') renewed = true;
      if (url === path && options.method === 'PUT' && !renewed)
        return json(
          { error: { code: 'CSRF_INVALID', message: 'Refresh the page and try again.' } },
          403
        );
      return null;
    };
    await click(saveLabel(kind));
    assert.match(text(), /Refresh the page and try again/);
    assert.equal(button(saveLabel(kind)).disabled, false);
    if (kind === 'profile') assert.equal(field('Display name').value, 'Local recovery draft');
    else {
      assert.equal(discover().checked, true);
      assert.match(text(), /Saved discovery status: Off/);
    }
    await focus();
    assert.equal(renewed, true);
    assert.equal(writes(path).length, 1, 'session refresh must not retry the write');
    await click(saveLabel(kind));
    assert.equal(writes(path).length, 2);
    assert.equal(writes(path).at(-1).body.expectedRevision, baseline.revision);
    assert.equal(button(saveLabel(kind)).disabled, true);
    if (kind === 'privacy') assert.match(text(), /Saved discovery status: On/);
  });

  test(`${kind}: a pending focus read cannot replace new input or advance its submission revision`, async () => {
    await open(kind);
    const baseline = await state.server.dispatch('GET', path);
    let release, signal;
    state.intercept = (url, options) =>
      url === path && options.method === 'GET'
        ? new Promise((resolve) => {
            signal = options.signal;
            release = () => resolve(json({ ...baseline, revision: baseline.revision + 50 }));
          })
        : null;
    await focus();
    await edit(kind);
    assert.equal(signal.aborted, true);
    await act(async () => release());
    if (kind === 'profile') assert.equal(field('Display name').value, 'Local recovery draft');
    else assert.equal(discover().checked, true);
    state.intercept = null;
    await click(saveLabel(kind));
    assert.equal(writes(path).at(-1).body.expectedRevision, baseline.revision);
  });

  for (const mode of ['lost-response', 'unreadable-success', 'malformed-success']) {
    test(`${kind}: ${mode} after commit requires a read and explicit reconciliation before another write`, async () => {
      await open(kind);
      await edit(kind);
      state.intercept = async (url, options, body) => {
        if (url !== path || options.method !== 'PUT') return null;
        const saved = await state.server.dispatch('PUT', path, body);
        if (mode === 'lost-response') throw new TypeError('Response lost after commit');
        if (mode === 'unreadable-success') return new Response('not JSON', { status: 200 });
        return json({ ...saved, revision: 'not-a-revision' });
      };
      await click(saveLabel(kind));
      assert.equal(button(saveLabel(kind)).disabled, true);
      assert.match(text(), /request may have succeeded/);
      assert.doesNotMatch(text(), /Profile saved\.|Privacy settings saved\./);
      if (kind === 'profile') assert.equal(field('Display name').value, 'Local recovery draft');
      else assert.match(text(), /Saved discovery status: Off/);
      const beforeReads = state.requests.filter(
        (r) => r.path === path && r.method === 'GET'
      ).length;
      await focus();
      await click(saveLabel(kind));
      assert.equal(writes(path).length, 1);
      assert.equal(
        state.requests.filter((r) => r.path === path && r.method === 'GET').length,
        beforeReads
      );
      state.intercept = null;
      await click('Compare before continuing');
      assert.match(text(), /Latest saved version/);
      assert.equal(button(saveLabel(kind)).disabled, true);
      assert.equal(writes(path).length, 1);
      await click('Use latest version');
      assert.equal(button(saveLabel(kind)).disabled, true);
      assert.doesNotMatch(text(), /request may have succeeded/);
      if (kind === 'profile') {
        assert.match(text(), /Needs confirmation/);
        assert.equal(button('Confirm profile').disabled, true);
      } else assert.match(text(), /Saved discovery status: On/);
    });
  }

  test(`${kind}: comparison preserves input and only a deliberate choice adopts the canonical revision`, async () => {
    await open(kind);
    await edit(kind);
    const before = await state.server.dispatch('GET', path);
    const latest =
      kind === 'profile'
        ? await state.server.dispatch('PUT', path, {
            expectedRevision: before.revision,
            content: { ...before.content, displayName: 'Server-side edit' },
          })
        : await state.server.dispatch('PUT', path, {
            expectedRevision: before.revision,
            discoverable: false,
            visibleFields: ['displayName'],
          });
    state.intercept = (url, options) =>
      url === path && options.method === 'PUT'
        ? json(
            {
              error: {
                code: 'REVISION_CONFLICT',
                currentRevision: 99999,
                message: 'Changed elsewhere.',
              },
            },
            409
          )
        : null;
    await click(saveLabel(kind));
    await click('Compare before continuing');
    assert.equal(button(saveLabel(kind)).disabled, true);
    if (kind === 'profile') assert.equal(field('Display name').value, 'Local recovery draft');
    else assert.match(text(), /Saved discovery status: Off/);
    assert.equal(writes(path).length, 1);
    await click('Continue editing my version');
    assert.equal(button(saveLabel(kind)).disabled, false);
    state.intercept = null;
    await click(saveLabel(kind));
    assert.equal(writes(path).at(-1).body.expectedRevision, latest.revision);
    assert.notEqual(writes(path).at(-1).body.expectedRevision, 99999);
  });

  test(`${kind}: failed comparison keeps the original recovery block and the local draft`, async () => {
    await open(kind);
    await edit(kind);
    state.intercept = (url, options) =>
      url !== path
        ? null
        : options.method === 'PUT'
          ? json({ error: { code: 'REVISION_CONFLICT', message: 'Changed elsewhere.' } }, 409)
          : json({ error: { code: 'UNAVAILABLE', message: 'Read temporarily unavailable.' } }, 503);
    await click(saveLabel(kind));
    await click('Compare before continuing');
    assert.match(text(), /Read temporarily unavailable/);
    assert.equal(button(saveLabel(kind)).disabled, true);
    await focus();
    assert.equal(writes(path).length, 1);
  });

  for (const status of [401, 403, 404]) {
    test(`${kind}: write ${status} removes private editor state`, async () => {
      await open(kind);
      await edit(kind);
      state.intercept = (url, options) =>
        url === path && options.method === 'PUT'
          ? json({ error: { code: 'FORBIDDEN', message: 'Access removed.' } }, status)
          : null;
      await click(saveLabel(kind));
      assert.match(text(), /Access removed/);
      assert.equal(!!document.querySelector('.profile-fields,.visibility-grid'), false);
      assert.doesNotMatch(text(), /Local recovery draft/);
    });
  }

  test(`${kind}: unreadable initial snapshot cannot expose enabled writes`, async () => {
    state.intercept = (url) => (url === path ? json({ revision: 'broken' }) : null);
    await open(kind);
    assert.match(text(), /unreadable response/);
    assert.equal(!!document.querySelector('.profile-fields,.visibility-grid'), false);
  });
}

test('editing and reverting a profile resets acknowledgement; confirmation uses exactly the reviewed revision', async () => {
  await mount();
  await change('Display name', 'Profile ready for review');
  await click('Save changes');
  const original = field('Display name').value;
  await checkbox('I have reviewed my saved profile');
  await change('Display name', 'Temporary edit');
  await change('Display name', original);
  assert.equal(button('Confirm profile').disabled, true);
  await checkbox('I have reviewed my saved profile');
  const saved = await state.server.dispatch('GET', '/me/profile');
  await click('Confirm profile');
  const request = state.requests.findLast((r) => r.path === '/me/profile/confirmation');
  assert.equal(request.body.expectedRevision, saved.revision);
});

test('an inconsistent successful confirmation is uncertain until the committed version is explicitly loaded', async () => {
  await mount();
  await change('Display name', 'Profile ready for confirmation');
  await click('Save changes');
  await checkbox('I have reviewed my saved profile');
  state.intercept = async (path, options, body) => {
    if (path !== '/me/profile/confirmation') return null;
    const result = await state.server.dispatch('POST', path, body);
    return json({
      ...result,
      confirmation: { ...result.confirmation, confirmedRevision: result.revision + 1 },
    });
  };
  await click('Confirm profile');
  assert.doesNotMatch(text(), /This version is confirmed|Profile confirmed\./);
  assert.equal(button('Confirm profile').disabled, true);
  await click('Confirm profile');
  assert.equal(state.requests.filter((r) => r.path === '/me/profile/confirmation').length, 1);
  state.intercept = null;
  await click('Compare before continuing');
  await click('Use latest version');
  assert.match(text(), /This version is confirmed/);
});

test('pending confirmation submits exactly the reviewed revision once and freezes acknowledgement', async () => {
  await mount();
  await change('Display name', 'Ready for confirmation');
  await click('Save changes');
  const saved = await state.server.dispatch('GET', '/me/profile');
  await checkbox('I have reviewed my saved profile');
  let release;
  state.intercept = (path, options, body) =>
    path === '/me/profile/confirmation'
      ? new Promise((resolve) => {
          release = async () => resolve(json(await state.server.dispatch('POST', path, body)));
        })
      : null;
  await click('Confirm profile');
  await click('Confirm profile');
  const attempts = state.requests.filter((r) => r.path === '/me/profile/confirmation');
  assert.equal(attempts.length, 1);
  assert.equal(attempts[0].body.expectedRevision, saved.revision);
  assert.equal(document.querySelector('.check-label input').matches(':disabled'), true);
  await act(async () => release());
  assert.match(text(), /This version is confirmed/);
});

test('validated changes invalidate mounted recommendations and remove an ineligible open match', async () => {
  await mount();
  await click('Recommended opportunities');
  await click('Why this match?');
  assert.ok(document.querySelector('.evidence-row'));
  const profile = await state.server.dispatch('GET', '/me/profile');
  await state.server.dispatch('PUT', '/me/profile', {
    expectedRevision: profile.revision,
    content: { ...profile.content, displayName: 'Changed outside this view' },
  });
  await act(async () => invalidateData('profile', 'matching', 'collections'));
  assert.equal(!!document.querySelector('.recommendation-card,dialog'), false);
  assert.match(text(), /Your profile needs a review/);
});

for (const kind of ['profile', 'privacy']) {
  test(`${kind} ViewModel accepts an in-memory repository without mounting the application`, async () => {
    let snapshot = await fixture(kind === 'profile' ? 'profile-unconfirmed' : 'privacy-default');
    const requests = [];
    const repository = {
      profile: async () => structuredClone(snapshot),
      privacy: async () => structuredClone(snapshot),
      saveProfile: async (revision, content) => {
        requests.push(revision);
        snapshot = { ...snapshot, revision: revision + 1, content };
        return structuredClone(snapshot);
      },
      savePrivacy: async ({ expectedRevision, ...value }) => {
        requests.push(expectedRevision);
        snapshot = { ...snapshot, ...value, revision: expectedRevision + 1 };
        return structuredClone(snapshot);
      },
    };
    let editor;
    function Probe() {
      const settings = { repository, notify: () => {}, confirmDiscard: () => true };
      editor = kind === 'profile' ? useProfileEditor(settings) : usePrivacyEditor(settings);
      return React.createElement('p', null, editor.saved?.revision);
    }
    globalThis.fetch = () => {
      throw new Error('Unexpected HTTP request');
    };
    await act(async () =>
      state.root.render(React.createElement(React.StrictMode, null, React.createElement(Probe)))
    );
    const revision = snapshot.revision;
    await act(async () =>
      editor.change(
        kind === 'profile'
          ? { ...editor.content, displayName: 'Fake repository edit' }
          : { ...editor.content, discoverable: true }
      )
    );
    await act(async () => editor.save({ preventDefault() {} }));
    assert.deepEqual(requests, [revision]);
    assert.equal(editor.saved.revision, revision + 1);
    assert.equal(editor.dirty, false);
  });
}
