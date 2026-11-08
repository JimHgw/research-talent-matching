import test from 'node:test';
import assert from 'node:assert/strict';
import { React, act, state } from './support/app-harness.js';
import { useDocumentsQuery } from '../src/features/documents/useDocumentsQuery.js';

function harness(t, strict = false) {
  t.mock.timers.enable({ apis: ['Date', 'setTimeout'], now: 100000 });
  let current;
  const calls = [];
  const documents = (page, { signal }) =>
    new Promise((resolve, reject) => {
      calls.push({
        page,
        signal,
        resolve: (status) =>
          resolve({
            items: [{ id: `doc_${page}`, status }],
            page,
            pageSize: 20,
            total: 2,
          }),
        reject,
      });
    });
  function Probe({ page }) {
    current = useDocumentsQuery(page, documents);
    return React.createElement('p', null, current.data?.items[0].status);
  }
  t.after(() => {
    delete document.visibilityState;
  });
  return {
    calls,
    get current() {
      return current;
    },
    render: (page = 1) =>
      act(async () =>
        state.root.render(
          strict
            ? React.createElement(React.StrictMode, null, React.createElement(Probe, { page }))
            : React.createElement(Probe, { page })
        )
      ),
    tick: (ms) => act(async () => t.mock.timers.tick(ms)),
    finish: (status = 'PROCESSING') => act(async () => calls.at(-1).resolve(status)),
    visibility: (value) =>
      act(async () => {
        Object.defineProperty(document, 'visibilityState', { configurable: true, value });
        document.dispatchEvent(new window.Event('visibilitychange'));
      }),
  };
}

test('polling retains the list, waits two seconds, never overlaps and stops at READY', async (t) => {
  const h = harness(t);
  await h.render();
  await h.finish('QUEUED');
  await h.tick(1999);
  assert.equal(h.calls.length, 1);
  await h.tick(1);
  assert.equal(h.calls.length, 2);
  assert.equal(h.current.data.items[0].status, 'QUEUED');
  assert.equal(h.current.refreshing, true);
  await h.tick(10000);
  assert.equal(h.calls.length, 2);
  await h.finish();
  await h.tick(2000);
  assert.equal(h.calls.length, 3);
  await h.finish('READY');
  await h.tick(90000);
  assert.equal(h.calls.length, 3);
  assert.equal(h.current.paused, false);
});

test('the 60-second budget expires during a slow request; refresh alone starts a fresh budget', async (t) => {
  const h = harness(t);
  await h.render();
  await h.finish();
  await h.tick(2000);
  await h.tick(58000);
  assert.equal(h.calls.length, 2);
  assert.equal(h.current.paused, true);
  await h.finish();
  assert.equal(h.current.data.items[0].status, 'PROCESSING');
  await h.visibility('hidden');
  await h.visibility('visible');
  await act(async () => window.dispatchEvent(new window.Event('focus')));
  await h.tick(10000);
  assert.equal(h.calls.length, 2);
  await act(async () => h.current.refresh());
  assert.equal(h.current.paused, false);
  assert.equal(h.calls.length, 3);
  await h.finish();
  await h.tick(2000);
  assert.equal(h.calls.length, 4);
  await h.finish('FAILED');
  await h.tick(60000);
  assert.equal(h.calls.length, 4);
  assert.equal(h.current.paused, false);
});

test('hidden pages start no polls and returning within the budget checks pending work once', async (t) => {
  const h = harness(t);
  await h.render();
  await h.finish();
  await h.visibility('hidden');
  await h.tick(10000);
  assert.equal(h.calls.length, 1);
  await h.visibility('visible');
  assert.equal(h.calls.length, 2);
  await h.visibility('hidden');
  await h.visibility('visible');
  assert.equal(h.calls.length, 2);
  await h.finish('READY');
  await h.visibility('hidden');
  await h.visibility('visible');
  await h.tick(60000);
  assert.equal(h.calls.length, 2);
});

test('StrictMode, re-renders and unmount leave no duplicate timers or visibility listeners', async (t) => {
  const h = harness(t, true);
  await h.render();
  assert.equal(h.calls.length, 1);
  await h.finish();
  await h.render();
  await h.render();
  await h.tick(2000);
  assert.equal(h.calls.length, 2);
  await act(async () => state.root.render(null));
  assert.equal(h.calls[1].signal.aborted, true);
  await h.finish();
  await h.visibility('hidden');
  await h.visibility('visible');
  await h.tick(60000);
  assert.equal(h.calls.length, 2);
  await h.render();
  await h.finish();
  await h.tick(2000);
  assert.equal(h.calls.length, 4);
});

test('page changes abort old polls and a late document list cannot populate the new page', async (t) => {
  const h = harness(t);
  await h.render(1);
  await h.finish();
  await h.tick(2000);
  const old = h.calls[1];
  await h.render(2);
  assert.equal(old.signal.aborted, true);
  assert.equal(h.current.data, null);
  await h.finish('READY');
  await act(async () => old.resolve('PROCESSING'));
  assert.equal(h.current.data.page, 2);
  await h.tick(60000);
  assert.equal(h.calls.length, 3);
});
