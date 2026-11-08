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
  text,
  json,
} from './support/app-harness.js';
import { dataChanged } from '../src/shared/data-invalidation.js';

for (const kind of ['profile', 'privacy'])
  for (const outcome of ['success', 'failure']) {
    test(`${kind}: late write ${outcome} cannot restore account A data or notifications in account B`, async (t) => {
      await mount();
      const path = `/me/${kind}`;
      if (kind === 'profile') await change('Display name', 'Account A private draft');
      else {
        await click('Privacy & visibility');
        await checkbox('Skills');
      }
      let release;
      state.intercept = async (url, options, body) => {
        if (url !== path || options.method !== 'PUT') return null;
        const saved = await state.server.dispatch('PUT', path, body);
        return new Promise((resolve, reject) => {
          release = () =>
            outcome === 'success'
              ? resolve(json(saved))
              : reject(new TypeError('Old account error'));
        });
      };
      await click(kind === 'profile' ? 'Save changes' : 'Save privacy settings');
      let changes = 0;
      const onChange = () => changes++;
      window.addEventListener(dataChanged, onChange);
      t.after(() => window.removeEventListener(dataChanged, onChange));
      await state.server.dispatch('POST', '/auth/login', {
        email: 'new@example.test',
        password: 'Demo1234!',
      });
      await act(async () => window.dispatchEvent(new window.Event('focus')));
      await act(async () => release());
      assert.equal(changes, 0);
      assert.doesNotMatch(
        text(),
        /Account A private draft|Profile saved\.|Privacy settings saved\.|Old account error/
      );
      assert.equal(field('Display name').value, '');
      if (kind === 'privacy') {
        await click('Privacy & visibility');
        assert.equal(
          document.querySelector('.visibility-option input[value="skills"]').checked,
          false
        );
      }
    });
  }

test('session expiry during a pending write clears the workspace and suppresses its late callback', async () => {
  await mount();
  await change('Display name', 'Expired session draft');
  let release;
  state.intercept = (path, options) =>
    path === '/me/profile' && options.method === 'PUT'
      ? new Promise((resolve) => {
          release = resolve;
        })
      : null;
  await click('Save changes');
  await state.server.dispatch('POST', '/auth/logout');
  await act(async () => window.dispatchEvent(new window.Event('focus')));
  await act(async () =>
    release(json({ revision: 100, content: { displayName: 'Expired session draft' } }))
  );
  assert.match(text(), /Welcome to Banana/);
  assert.doesNotMatch(text(), /Expired session draft|Profile saved\./);
  assert.equal(!!document.querySelector('.workspace'), false);
});
