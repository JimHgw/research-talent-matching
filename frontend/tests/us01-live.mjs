// Invoked by pytest with a temporary SQLite database and real Python HTTP server.
// Only the browser environment is simulated; no API responses are mocked.
import assert from 'node:assert/strict';
import { JSDOM, CookieJar } from 'jsdom';

const backend = process.env.TEST_API_BASE_URL;
assert.ok(backend, 'Run this integration through pytest.');
const origin = 'http://127.0.0.1:5173';
const jar = new CookieJar();
const dom = new JSDOM('<!doctype html><div id="root"></div>', { url: origin, cookieJar: jar });
globalThis.window = dom.window;
globalThis.document = dom.window.document;
globalThis.HTMLElement = dom.window.HTMLElement;
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
window.scrollTo = () => {};
window.confirm = () => true;
const nativeFetch = globalThis.fetch;
const requests = [];
globalThis.fetch = async (url, options = {}) => {
  const requestHeaders = new Headers(options.headers);
  requestHeaders.set('Cookie', await jar.getCookieString(origin));
  if (options.method && options.method !== 'GET') requestHeaders.set('Origin', origin);
  requests.push({ url, method: options.method || 'GET' });
  const response = await nativeFetch(backend + url, { ...options, headers: requestHeaders });
  for (const cookie of response.headers.getSetCookie()) await jar.setCookie(cookie, origin);
  return response;
};

const { default: React, act } = await import('react');
const { createRoot } = await import('react-dom/client');
const { default: App } = await import('../src/App.jsx');
const { createApi } = await import('../src/api/client.js');
let root = createRoot(document.getElementById('root'));
const text = () => document.body.textContent;
async function until(condition) {
  const deadline = Date.now() + 10000;
  while (!condition()) {
    assert.ok(Date.now() < deadline, `Timed out. Page: ${text()}`);
    await act(async () => new Promise((resolve) => setTimeout(resolve, 15)));
  }
}
async function mount() {
  await act(async () =>
    root.render(React.createElement(React.StrictMode, null, React.createElement(App)))
  );
}
function field(name) {
  const label = [...document.querySelectorAll('label')].find(
    (label) => label.querySelector(':scope > span')?.textContent === name
  );
  assert.ok(label, `Missing field: ${name}`);
  return label.querySelector('input,select,textarea');
}
async function change(name, value) {
  const element = field(name);
  const prototype = Object.getPrototypeOf(element);
  await act(async () => {
    Object.getOwnPropertyDescriptor(prototype, 'value').set.call(element, value);
    element.dispatchEvent(
      new window.Event(element.tagName === 'SELECT' ? 'change' : 'input', { bubbles: true })
    );
  });
}
async function click(name) {
  const element = [...document.querySelectorAll('button')].find(
    (button) => button.textContent.trim() === name || button.getAttribute('aria-label') === name
  );
  assert.ok(element && !element.disabled, `Missing or disabled button: ${name}`);
  await act(async () => element.click());
}
async function login(email) {
  await until(() => text().includes('Welcome to Banana'));
  await change('Email address', email);
  await change('Password', 'Test-password-123!');
  await click('Sign in');
}

try {
  await mount();
  await until(() => text().includes('Welcome to Banana'));
  assert.equal(requests.filter((request) => request.url.endsWith('/auth/session')).length, 1);
  await change('Email address', 'talent@example.test');
  await change('Password', 'incorrect');
  await click('Sign in');
  await until(() => text().includes('email or password is incorrect'));
  await login('talent@example.test');
  await until(() => text().includes('Tell your research story'));
  await change('Display name', 'Live integration talent');
  await change('Discipline group', 'STEM');
  await click('Add education');
  await change('Institution *', 'UNSW');
  await change('Qualification *', 'Master of IT');
  await change('Start year', '2025');
  await click('Add courses');
  await change('Course name *', 'Research methods');
  const courseCode = 'COMP'.repeat(50);
  await change('Course code', courseCode);
  assert.equal(field('Course code').maxLength, 200);
  await click('Add research experience');
  await change('Project / role title *', 'Synthetic research project');
  await click('Add research outputs');
  await change('Output title *', 'Sample output');
  await change('Link (optional)', 'https://example.test/research');
  await click('Add skill');
  await change('Skill', 'skill_python');
  await change('Supporting evidence', 'Built the test project.');
  const interest = [...document.querySelectorAll('label')].find(
    (label) => label.textContent.trim() === 'Machine learning'
  );
  await act(async () => interest.querySelector('input').click());
  await click('Save changes');
  await until(() => text().includes('Profile saved.'));
  const api = createApi();
  await api.session();
  const saved = await api.profile();
  assert.equal(saved.revision, 1);
  assert.equal(saved.content.displayName, 'Live integration talent');
  assert.equal(saved.content.courses[0].code, courseCode);
  for (const section of [
    'education',
    'courses',
    'researchExperience',
    'skills',
    'researchInterests',
    'researchOutputs',
  ])
    assert.equal(saved.content[section].length, 1, section);

  // Reload the React application while keeping the browser cookie.
  await act(async () => root.unmount());
  root = createRoot(document.getElementById('root'));
  await mount();
  await until(() => text().includes('Tell your research story'));
  assert.equal(field('Display name').value, 'Live integration talent');
  assert.equal(field('Institution *').value, 'UNSW');
  assert.equal(field('Course code').value, courseCode);

  await api.saveProfile(1, { ...saved.content, displayName: 'Saved by another tab' });
  await change('Display name', 'Keep my draft');
  await click('Save changes');
  await until(() => text().includes('Your profile changed.'));
  assert.equal(field('Display name').value, 'Keep my draft');
  await click('Reload latest data');
  await until(() => document.querySelector('input')?.value === 'Saved by another tab');
  await click('Sign out');
  await until(() => text().includes('Welcome to Banana'));
  await assert.rejects(api.profile(), (error) => error.status === 401);

  await login('other@example.test');
  await until(() => text().includes('Tell your research story'));
  assert.equal(field('Display name').value, '');
  assert.doesNotMatch(text(), /UNSW|Saved by another tab/);
  await click('Sign out');
  await login('team@example.test');
  await until(() => text().includes('Your account'));
  await assert.rejects(api.profile(), (error) => error.status === 403);
  await click('Sign out');
  await until(() => text().includes('Welcome to Banana'));
  console.log('US-01 real HTTP integration passed');
} finally {
  await act(async () => root.unmount());
  dom.window.close();
}
