// Shared browser harness for pytest-driven tests against real HTTP and SQLite.
// Only the DOM is simulated. API responses, cookies and CSRF are real.
import assert from 'node:assert/strict';
import { JSDOM, CookieJar } from 'jsdom';

const backend = process.env.TEST_API_BASE_URL;
assert.ok(backend, 'Run this integration through pytest.');
const origin = process.env.TEST_FRONTEND_ORIGIN || 'http://127.0.0.1:5173';
const jar = new CookieJar();
const dom = new JSDOM('<!doctype html><div id="root"></div>', {
  url: origin,
  cookieJar: jar,
  pretendToBeVisual: true,
});
globalThis.window = dom.window;
globalThis.document = dom.window.document;
globalThis.HTMLElement = dom.window.HTMLElement;
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
window.scrollTo = () => {};
window.confirm = () => true;
window.HTMLDialogElement.prototype.showModal = function () {
  this.open = true;
};
const nativeFetch = globalThis.fetch;
export const requests = [];
function browserFetch(cookieJar, recorded = false) {
  return async (url, options = {}) => {
    const requestHeaders = new Headers(options.headers);
    requestHeaders.set('Cookie', await cookieJar.getCookieString(origin));
    if (options.method && options.method !== 'GET') requestHeaders.set('Origin', origin);
    if (recorded) requests.push({ url, method: options.method || 'GET' });
    const response = await nativeFetch(backend + url, { ...options, headers: requestHeaders });
    for (const cookie of response.headers.getSetCookie()) await cookieJar.setCookie(cookie, origin);
    return response;
  };
}
globalThis.fetch = browserFetch(jar, true);
export const independentBrowserFetch = () => browserFetch(new CookieJar());

const { default: React, act } = await import('react');
const { createRoot } = await import('react-dom/client');
const { default: App } = await import('../../src/App.jsx');
let root = createRoot(document.getElementById('root'));
export { act };
export const text = () => document.body.textContent;
export async function until(condition) {
  const deadline = Date.now() + 10000;
  while (!condition()) {
    assert.ok(Date.now() < deadline, `Timed out. Page: ${text()}`);
    await act(async () => new Promise((resolve) => setTimeout(resolve, 15)));
  }
}
export async function mount() {
  await act(async () =>
    root.render(React.createElement(React.StrictMode, null, React.createElement(App)))
  );
}
export async function remount() {
  await act(async () => root.unmount());
  root = createRoot(document.getElementById('root'));
  await mount();
}
export async function cleanup() {
  await act(async () => root.unmount());
  dom.window.close();
}
export function field(name) {
  const label = [...document.querySelectorAll('label')].find(
    (label) => label.querySelector(':scope > span')?.textContent === name
  );
  assert.ok(label, `Missing field: ${name}`);
  return label.querySelector('input,select,textarea');
}
export async function change(name, value) {
  const element = field(name);
  await act(async () => {
    Object.getOwnPropertyDescriptor(Object.getPrototypeOf(element), 'value').set.call(
      element,
      value
    );
    element.dispatchEvent(
      new window.Event(element.tagName === 'SELECT' ? 'change' : 'input', { bubbles: true })
    );
  });
}
export function button(name) {
  return [...document.querySelectorAll('button')].find(
    (button) => button.textContent.trim() === name || button.getAttribute('aria-label') === name
  );
}
export async function click(name) {
  const element = button(name);
  assert.ok(element && !element.disabled, `Missing or disabled button: ${name}`);
  await act(async () => element.click());
}
export async function login(email) {
  await until(() => text().includes('Welcome to Banana'));
  await change('Email address or account ID', email);
  await change('Password', 'Test-password-123!');
  await click('Sign in');
}
export async function checkbox(labelText) {
  const label = [...document.querySelectorAll('label')].find(
    (label) => label.textContent.trim() === labelText
  );
  assert.ok(label, `Missing checkbox: ${labelText}`);
  await act(async () => label.querySelector('input[type="checkbox"]').click());
}
