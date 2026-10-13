import test from 'node:test';
import assert from 'node:assert/strict';
import { mount, click, button, text, state, act, json } from './support/app-harness.js';

test('saving updates the card and detail state, and removing restores the save action', async () => {
  await mount();
  await click('Recommended opportunities');
  await click('Save Opportunity');
  assert.match(text(), /Saved successfully/);
  assert.equal(button('Remove from Saved').disabled, false);
  await click('View opportunity');
  assert.match(document.querySelector('dialog').textContent, /Remove from Saved/);
  await click('Close dialog');
  await click('Remove from Saved');
  assert.match(text(), /Removed successfully/);
  assert.equal(button('Save Opportunity').disabled, false);
  assert.equal(state.requests.filter((r) => r.method === 'PUT').length, 1);
  assert.equal(state.requests.filter((r) => r.method === 'DELETE').length, 1);
});

test('a failed save shows an error without a saved state or success message', async () => {
  state.intercept = (path, options) =>
    path.startsWith('/me/saved-opportunities/') && options.method === 'PUT'
      ? json({ error: { code: 'INTERNAL_ERROR', message: 'Save could not be persisted.' } }, 500)
      : null;
  await mount();
  await click('Recommended opportunities');
  await click('Save Opportunity');
  assert.match(text(), /Save could not be persisted/);
  assert.doesNotMatch(text(), /Saved successfully|Remove from Saved/);
  state.intercept = null;
  await click('Save Opportunity');
  assert.match(text(), /Saved successfully/);
  assert.doesNotMatch(text(), /Save could not be persisted/);
});

test('rapid repeated clicks issue only one pending save request', async () => {
  let release;
  state.intercept = (path, options) =>
    path.startsWith('/me/saved-opportunities/') && options.method === 'PUT'
      ? new Promise((resolve) => {
          release = () => resolve(null);
        })
      : null;
  await mount();
  await click('Recommended opportunities');
  const save = button('Save Opportunity');
  await act(async () => {
    save.click();
    save.click();
  });
  assert.equal(button('Saving…').disabled, true);
  assert.equal(state.requests.filter((r) => r.method === 'PUT').length, 1);
  await act(async () => release());
  assert.match(text(), /Saved successfully/);
  assert.equal(button('Remove from Saved').disabled, false);
});
