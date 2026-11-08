// Executed by test_fe3_frontend_integration.py with an isolated database and Worker.
import assert from 'node:assert/strict';
import { writeFile } from 'node:fs/promises';
import {
  act,
  mount,
  login,
  click,
  until,
  text,
  cleanup,
  requests,
  button,
} from './support/live-app.js';

const listReads = () =>
  requests.filter((request) => request.url.startsWith('/api/v1/me/documents?')).length;
async function wait(ms) {
  const deadline = Date.now() + ms;
  while (Date.now() < deadline) {
    await act(
      async () =>
        new Promise((resolve) => setTimeout(resolve, Math.min(100, deadline - Date.now())))
    );
    if (document.querySelector('.document-list'))
      assert.ok(
        document.querySelector('.document-row'),
        'Polling removed the last authorised list'
      );
  }
}

try {
  await mount();
  await login('talent@example.test');
  await until(() => !!button('My documents'));
  await click('My documents');
  await until(() => document.querySelector('.document-row'));
  assert.match(document.querySelector('.document-row').textContent, /PROCESSING/);
  await wait(62000);
  assert.match(text(), /Automatic checks paused after 60 seconds/);
  assert.match(document.querySelector('.document-row').textContent, /PROCESSING/);
  assert.doesNotMatch(document.querySelector('.document-row').textContent, /FAILED/);
  const pausedReads = listReads();
  assert.ok(pausedReads >= 2 && pausedReads <= 31, `Unexpected polling count: ${pausedReads}`);
  await act(async () => window.dispatchEvent(new window.Event('focus')));
  await wait(2200);
  assert.equal(listReads(), pausedReads, 'Focus must not reset an exhausted budget');
  assert.ok(button('Enter details manually'));
  await click('Refresh status');
  await until(() => listReads() > pausedReads);
  assert.doesNotMatch(text(), /Automatic checks paused/);
  await writeFile(process.env.TEST_WORKER_RELEASE_PATH, 'continue actual extraction\n');
  await until(() => !!button('Review suggestions'));
  assert.match(document.querySelector('.document-row').textContent, /READY/);
  const readyReads = listReads();
  await wait(2400);
  assert.equal(listReads(), readyReads, 'Terminal state must stop polling');
  await click('Review suggestions');
  await until(() => !!button('Apply reviewed sections'));
  assert.equal(button('Apply reviewed sections').disabled, true);
  assert.equal(requests.filter((request) => request.url.endsWith('/apply')).length, 0);
  console.log(
    `FE-3 real slow Worker integration passed (${pausedReads} checks before pause; READY review remains explicit)`
  );
} finally {
  await cleanup();
}
