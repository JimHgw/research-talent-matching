import test from 'node:test';
import assert from 'node:assert/strict';
import {
  App,
  React,
  act,
  createMockServer,
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

test('login uses entered credentials and a failed password stays on the sign-in form', async () => {
  await mount(null);
  assert.match(text(), /Welcome to Banana/);
  assert.doesNotMatch(text(), /Try as talent|Reset demo/);
  await change('Email address', 'talent@example.test');
  await change('Password', 'incorrect');
  await click('Sign in');
  assert.match(text(), /email or password is incorrect/);
  assert.ok(field('Password'));
  await change('Password', 'Demo1234!');
  await click('Sign in');
  assert.ok(document.querySelector('.workspace'));
  assert.match(document.querySelector('.sidebar-user').textContent, /Alex Morgan/);
  assert.equal(state.requests.filter((r) => r.path === '/auth/login').length, 2);
});

test('offline startup reports an unavailable service and offers retry without synthetic fallback', async () => {
  globalThis.fetch = async () => {
    throw new TypeError('offline');
  };
  await act(async () => state.root.render(React.createElement(App)));
  assert.match(text(), /could not reach your workspace/);
  assert.match(text(), /Cannot connect to the service/);
  assert.ok(button('Reload latest data'));
  assert.doesNotMatch(text(), /Alex Morgan|Casey Jordan|Demo1234/);
});

test('mobile navigation marks its state, makes background inert, and closes with Escape', async () => {
  await mount();
  await click('Open navigation');
  assert.equal(button('Open navigation').getAttribute('aria-expanded'), 'true');
  assert.ok(document.querySelector('.workspace-body').hasAttribute('inert'));
  await act(async () =>
    window.dispatchEvent(new window.KeyboardEvent('keydown', { key: 'Escape' }))
  );
  assert.equal(button('Open navigation').getAttribute('aria-expanded'), 'false');
  assert.equal(document.querySelector('.workspace-body').hasAttribute('inert'), false);
});

test('failed logout keeps the workspace available; retry returns to an empty sign-in form', async () => {
  await mount();
  state.intercept = (path) =>
    path === '/auth/logout'
      ? json(
          { error: { code: 'SERVICE_UNAVAILABLE', message: 'Sign out failed. Please retry.' } },
          503
        )
      : null;
  await click('Sign out');
  assert.match(document.querySelector('[role="alert"]').textContent, /Sign out failed/);
  assert.ok(document.querySelector('.workspace'));
  assert.match(document.querySelector('.sidebar-user').textContent, /Alex Morgan/);
  state.intercept = null;
  await click('Sign out');
  assert.match(text(), /Welcome to Banana/);
  assert.equal(field('Password').value, '');
  assert.equal(document.querySelector('.workspace'), null);
});

test('returning to desktop closes the mobile overlay so the workspace is usable', async () => {
  await mount();
  await click('Open navigation');
  assert.ok(document.querySelector('.workspace-body').hasAttribute('inert'));
  await act(async () => window.dispatchEvent(new window.Event('resize')));
  assert.equal(document.querySelector('.workspace-body').hasAttribute('inert'), false);
  assert.equal(document.querySelector('.menu-backdrop'), null);
});
