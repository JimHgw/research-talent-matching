import { beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { JSDOM } from 'jsdom';
import { readFile } from 'node:fs/promises';
import { createMockServer } from './server.js';

const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>', {
  url: 'http://localhost:5173',
});
globalThis.window = dom.window;
globalThis.document = dom.window.document;
globalThis.HTMLElement = dom.window.HTMLElement;
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
window.scrollTo = () => {};
window.confirm = () => false;
// jsdom does not implement the browser top layer; behavior is checked in-browser separately.
window.HTMLDialogElement.prototype.showModal = function () {
  this.open = true;
};
const { default: React, act } = await import('react');
const { createRoot } = await import('react-dom/client');
const { default: App } = await import('../../src/App.jsx');
export const state = { root: null, server: null, requests: [], intercept: null };
beforeEach(() => {
  window.localStorage.clear();
  window.history.replaceState(null, '', '/');
  window.confirm = () => false;
  document.getElementById('root').replaceChildren();
  state.root = createRoot(document.getElementById('root'));
  state.server = createMockServer();
  state.requests = [];
  state.intercept = null;
  const collections = new Set();
  globalThis.fetch = async (url, options) => {
    const path = url.replace('/api/v1', '');
    const body =
      options.body instanceof FormData
        ? options.body
        : options.body
          ? JSON.parse(options.body)
          : undefined;
    state.requests.push({ path, method: options.method, body });
    if (state.intercept) {
      const response = await state.intercept(path, options, body);
      if (response) return response;
    }
    // Collection state for synthetic cards, including IDs supplied by individual tests.
    // Authorization and persistence are exercised against the real API in live tests.
    if (
      /^\/me\/saved-opportunities\/[^/?]+$/.test(path) ||
      /^\/opportunities\/[^/]+\/shortlist\/[^/?]+$/.test(path)
    ) {
      if (options.method === 'PUT') collections.add(path);
      if (options.method === 'DELETE') collections.delete(path);
      return json({ saved: collections.has(path) });
    }
    try {
      const value = await state.server.dispatch(options.method, path, body);
      if (value === undefined) return new Response(null, { status: 204 });
      if (value instanceof Blob) return new Response(value);
      return new Response(JSON.stringify(value), {
        headers: { 'Content-Type': 'application/json' },
      });
    } catch (error) {
      return new Response(
        JSON.stringify({
          error: {
            code: error.code,
            message: error.message,
            fieldErrors: error.fields,
            currentRevision: error.currentRevision,
          },
        }),
        { status: error.status || 500 }
      );
    }
  };
});
afterEach(async () => {
  await act(async () => state.root.unmount());
});
async function mount(email = 'talent@example.test', configuration) {
  if (email) await state.server.dispatch('POST', '/auth/login', { email, password: 'Demo1234!' });
  await act(async () => state.root.render(React.createElement(App, { configuration })));
}
const text = () => document.body.textContent;
function button(name) {
  const found = [...document.querySelectorAll('button')].find(
    (b) => b.textContent.trim() === name || b.getAttribute('aria-label') === name
  );
  assert.ok(found, `Button not found: ${name}`);
  return found;
}
async function click(name) {
  await act(async () => button(name).click());
}
function field(name, scope = document) {
  const label = [...scope.querySelectorAll('label')].find(
    (l) => l.querySelector(':scope > span')?.textContent === name
  );
  assert.ok(label, `Field not found: ${name}`);
  return label.querySelector('input,select,textarea');
}
async function change(name, value, scope = document) {
  const input = field(name, scope);
  await act(async () => {
    const proto =
      input.tagName === 'SELECT'
        ? window.HTMLSelectElement.prototype
        : input.tagName === 'TEXTAREA'
          ? window.HTMLTextAreaElement.prototype
          : window.HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(proto, 'value').set.call(input, value);
    input.dispatchEvent(
      new window.Event(input.tagName === 'SELECT' ? 'change' : 'input', { bubbles: true })
    );
  });
}
async function checkbox(labelText) {
  const label = [...document.querySelectorAll('label')].find((l) =>
    l.textContent.includes(labelText)
  );
  assert.ok(label, `Checkbox label not found: ${labelText}`);
  await act(async () => label.querySelector('input[type="checkbox"]').click());
}
const json = (body, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const fixture = async (name) =>
  JSON.parse(
    await readFile(new URL(`../../../docs/api/examples/${name}.json`, import.meta.url), 'utf8')
  );

export {
  App,
  React,
  act,
  createMockServer,
  mount,
  text,
  button,
  click,
  field,
  change,
  checkbox,
  json,
  fixture,
};
