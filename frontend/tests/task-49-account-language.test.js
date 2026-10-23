import test from 'node:test';
import assert from 'node:assert/strict';
import {
  App,
  React,
  act,
  state,
  mount,
  change,
  click,
  field,
  text,
  button,
  json,
} from './support/app-harness.js';
import { languageStorageKey, translate } from '../src/shared/i18n.jsx';
import { deferMutation } from './support/deferred-mutation.js';

const { createRoot } = await import('react-dom/client');

async function focus() {
  await act(async () => window.dispatchEvent(new window.Event('focus')));
}
async function remount() {
  await act(async () => state.root.unmount());
  state.root = createRoot(document.getElementById('root'));
  await act(async () => state.root.render(React.createElement(App)));
}

test('logout hides sign-in until the fresh anonymous session has supplied its CSRF token', async () => {
  await mount();
  let release;
  const sessionResponse = new Promise((resolve) => {
    release = resolve;
  });
  let loginToken;
  state.intercept = (path, options) => {
    if (path === '/auth/session') return sessionResponse;
    if (path === '/auth/login') loginToken = options.headers['X-CSRF-Token'];
    return null;
  };
  await click('Sign out');
  try {
    assert.doesNotMatch(text(), /Welcome to Banana/);
    assert.equal(document.querySelector('input[autocomplete="current-password"]'), null);
    assert.equal(state.requests.filter((r) => r.path === '/auth/login').length, 0);
  } finally {
    await act(async () => release(json({ user: null, csrfToken: 'fresh-anonymous-token' })));
  }
  assert.match(text(), /Welcome to Banana/);
  await change('Email address or account ID', 'talent@example.test');
  await change('Password', 'Demo1234!');
  await click('Sign in');
  assert.equal(loginToken, 'fresh-anonymous-token');
  assert.match(text(), /Tell your research story/);
});

test('failed session refresh after logout blocks sign-in and can be retried', async () => {
  await mount();
  state.intercept = (path) =>
    path === '/auth/session'
      ? json({ error: { code: 'UNAVAILABLE', message: 'Session unavailable.' } }, 503)
      : null;
  await click('Sign out');
  assert.match(text(), /We could not reach your workspace/);
  assert.doesNotMatch(text(), /Welcome to Banana|Tell your research story/);
  state.intercept = null;
  await click('Reload latest data');
  assert.match(text(), /Welcome to Banana/);
});

test('sign-in visibility toggles preserve the exact password and clear when leaving the form', async () => {
  await mount(null);
  await change('Password', 'Exact-password-123!');
  assert.equal(field('Password').type, 'password');
  await click('Show password');
  assert.equal(field('Password').type, 'text');
  assert.equal(field('Password').value, 'Exact-password-123!');
  assert.equal(button('Hide password').getAttribute('aria-pressed'), 'true');
  assert.equal(button('Hide password').getAttribute('aria-controls'), field('Password').id);
  await click('Hide password');
  assert.equal(field('Password').type, 'password');
  await click('Register');
  await click('Back to sign in');
  assert.equal(field('Password').value, '');
  assert.equal(field('Password').type, 'password');
  assert.equal(
    state.requests.some((r) => r.path === '/auth/login'),
    false
  );
});

test('registration and reset fields have independent visibility controls', async () => {
  await mount(null);
  await click('Register');
  await change('Email address', 'new@example.test');
  state.intercept = (path) =>
    path === '/auth/register/code' ? json({ resendAfterSeconds: 60 }, 202) : null;
  await click('Send verification code');
  await change('Password', 'Registration-123!');
  await change('Confirm password', 'Registration-123!');
  await click('Show confirm password');
  assert.equal(field('Password').type, 'password');
  assert.equal(field('Confirm password').type, 'text');
  await click('Back to sign in');
  await click('Reset password');
  await change('Current password', 'Current-123!');
  await change('New password', 'Next-456!');
  await change('Confirm new password', 'Next-456!');
  await click('Show new password');
  assert.equal(field('Current password').type, 'password');
  assert.equal(field('New password').type, 'text');
  assert.equal(field('Confirm new password').type, 'password');
  await click('Use an email code');
  await click('I remember my password');
  assert.equal(field('New password').type, 'password');
  assert.equal(field('New password').value, '');
});

test('English defaults, Chinese persists across remount and form values are preserved', async () => {
  await mount(null);
  assert.equal(document.documentElement.lang, 'en');
  await change('Email address or account ID', 'Research team');
  await change('Password', 'Secret-123!');
  await change('Language', 'zh-CN');
  assert.equal(document.documentElement.lang, 'zh-CN');
  assert.equal(window.localStorage.getItem(languageStorageKey), 'zh-CN');
  assert.equal(field('邮箱或账号 ID').value, 'Research team');
  assert.equal(field('密码').value, 'Secret-123!');
  assert.match(text(), /欢迎使用 Banana/);
  await remount();
  assert.match(text(), /欢迎使用 Banana/);
  assert.equal(field('界面语言').value, 'zh-CN');
  await change('界面语言', 'en');
  assert.match(text(), /Welcome to Banana/);
  assert.equal(document.documentElement.lang, 'en');
});

test('changing language keeps registration verification state and translates errors without changing the API payload', async () => {
  await mount(null);
  await click('Register');
  await change('Email address', 'new@example.test');
  state.intercept = (path) =>
    path === '/auth/register/code' ? json({ resendAfterSeconds: 60 }, 202) : null;
  await click('Send verification code');
  await change('Verification code', '012345');
  await change('Account type', 'RESEARCH_TEAM');
  await change('Display name', 'Research talent');
  await change('Password', 'Selected-123!');
  await change('Confirm password', 'Selected-123!');
  state.intercept = (path) =>
    path === '/auth/register'
      ? json(
          {
            error: {
              code: 'VERIFICATION_CODE_INVALID',
              message: 'The code is invalid or expired.',
            },
          },
          422
        )
      : null;
  await click('Create account');
  await change('Language', 'zh-CN');
  assert.match(document.querySelector('[role="alert"]').textContent, /验证码无效或已过期/);
  assert.equal(field('显示名称').value, 'Research talent');
  assert.equal(field('账号类型').value, 'RESEARCH_TEAM');
  assert.equal(field('验证码').value, '012345');
  assert.equal(field('密码').value, 'Selected-123!');
  assert.equal(field('邮箱').readOnly, true);
  await click('创建账号');
  assert.deepEqual(state.requests.filter((r) => r.path === '/auth/register').at(-1).body, {
    email: 'new@example.test',
    code: '012345',
    password: 'Selected-123!',
    displayName: 'Research talent',
    role: 'RESEARCH_TEAM',
  });
});

test('unknown translations and unsupported preferences fall back to English without translating user data', async () => {
  window.localStorage.setItem(languageStorageKey, 'unsupported');
  await mount(null);
  assert.equal(field('Language').value, 'en');
  assert.equal(translate('zh-CN', 'New module message'), 'New module message');
  assert.equal(
    translate('zh-CN', 'Signed in as {name}.', { name: 'Research team' }),
    '当前登录：Research team。'
  );
  assert.equal(translate('unknown', 'Sign in'), 'Sign in');
});

test('unavailable local storage does not block login or language selection', async (t) => {
  t.mock.method(window.Storage.prototype, 'getItem', () => {
    throw new Error('denied');
  });
  t.mock.method(window.Storage.prototype, 'setItem', () => {
    throw new Error('denied');
  });
  await mount(null);
  await change('Language', 'zh-CN');
  assert.match(text(), /欢迎使用 Banana/);
  await change('邮箱或账号 ID', 'talent@example.test');
  await change('密码', 'Demo1234!');
  await click('登录');
  assert.ok(document.querySelector('.workspace'));
});

test('language selection follows a supported cross-tab preference and clearing storage restores English', async () => {
  await mount(null);
  await act(async () =>
    window.dispatchEvent(
      new window.StorageEvent('storage', { key: languageStorageKey, newValue: 'zh-CN' })
    )
  );
  assert.match(text(), /欢迎使用 Banana/);
  await act(async () =>
    window.dispatchEvent(
      new window.StorageEvent('storage', { key: languageStorageKey, newValue: 'bad' })
    )
  );
  assert.equal(document.documentElement.lang, 'zh-CN');
  await act(async () =>
    window.dispatchEvent(new window.StorageEvent('storage', { key: null, newValue: null }))
  );
  assert.match(text(), /Welcome to Banana/);
});

test('account ID and server role are displayed for both roles, persist on refresh and clear after switching accounts', async () => {
  await mount();
  const talent = await state.server.dispatch('GET', '/auth/session');
  assert.match(document.querySelector('.account-entry').textContent, new RegExp(talent.user.id));
  await click('Account details');
  assert.match(document.querySelector('dialog').textContent, /talent@example.test/);
  assert.match(document.querySelector('dialog').textContent, /Research talent/);
  await click('Switch account');
  assert.equal(document.querySelector('.account-entry'), null);
  assert.doesNotMatch(text(), new RegExp(talent.user.id));
  await change('Email address or account ID', 'team@example.test');
  await change('Password', 'Demo1234!');
  await click('Sign in');
  const team = await state.server.dispatch('GET', '/auth/session');
  assert.match(document.querySelector('.account-entry').textContent, new RegExp(team.user.id));
  assert.doesNotMatch(text(), new RegExp(talent.user.id));
  await remount();
  assert.match(document.querySelector('.account-entry').textContent, new RegExp(team.user.id));
  await click('Account details');
  assert.match(document.querySelector('dialog').textContent, /Research team/);
});

test('signing out waits for the new anonymous session before showing sign-in controls', async () => {
  await mount();
  let release;
  state.intercept = (path) =>
    path === '/auth/session'
      ? new Promise((resolve) => {
          release = resolve;
        })
      : null;
  await click('Sign out');
  try {
    assert.equal(document.querySelector('.workspace'), null);
    assert.ok(
      !document.querySelector('.login-fields'),
      'Sign-in controls appeared before CSRF was ready'
    );
    assert.ok(document.querySelector('.app-loading'));
  } finally {
    await act(async () => release(json({ user: null, csrfToken: 'after-logout' })));
  }
  let loginToken;
  state.intercept = (path, options) => {
    if (path === '/auth/login') loginToken = options.headers['X-CSRF-Token'];
    return null;
  };
  await change('Email address or account ID', 'team@example.test');
  await change('Password', 'Demo1234!');
  await click('Sign in');
  assert.equal(loginToken, 'after-logout');
  assert.match(text(), /Your account/);
});

test('a failed session refresh after sign-out can be retried before signing in', async () => {
  await mount();
  state.intercept = (path) =>
    path === '/auth/session'
      ? json({ error: { code: 'UNAVAILABLE', message: 'Service unavailable.' } }, 503)
      : null;
  await click('Sign out');
  assert.equal(document.querySelector('.workspace'), null);
  assert.equal(document.querySelector('.login-fields'), null);
  assert.match(text(), /We could not reach your workspace/);
  state.intercept = null;
  await click('Reload latest data');
  assert.match(text(), /Welcome to Banana/);
});

test('language changes and same-account session checks preserve unsaved profile edits', async () => {
  await mount();
  await change('Display name', 'Do not translate this draft');
  await change('Language', 'zh-CN');
  assert.equal(field('显示名称').value, 'Do not translate this draft');
  assert.match(document.querySelector('nav').textContent, /我的资料/);
  await focus();
  assert.equal(field('显示名称').value, 'Do not translate this draft');
  assert.equal(
    state.requests.some((r) => r.method === 'PUT'),
    false
  );
  await change('界面语言', 'en');
  await click('Account details');
  await click('Switch account');
  assert.match(text(), /Leave without saving/);
  await click('Keep editing');
  assert.equal(field('Display name').value, 'Do not translate this draft');
});

test('switching accounts obeys pending-write guards', async () => {
  await mount();
  await change('Display name', 'Pending profile');
  const finish = deferMutation((path) => path === '/me/profile');
  await click('Save changes');
  await click('Account details');
  await click('Switch account');
  assert.equal(button('Discard changes').disabled, true);
  assert.equal(
    state.requests.some((r) => r.path === '/auth/logout'),
    false
  );
  await click('Keep editing');
  await act(finish);
});

test('returning to a tab replaces a changed server account and removes the previous private draft', async () => {
  await mount();
  await change('Display name', 'Private account A draft');
  await state.server.dispatch('POST', '/auth/login', {
    email: 'team@example.test',
    password: 'Demo1234!',
  });
  await focus();
  assert.match(text(), /Your account/);
  assert.doesNotMatch(text(), /Private account A draft|Alex Morgan/);
  assert.equal(document.querySelector('nav').textContent.includes('My profile'), false);
  await state.server.dispatch('POST', '/auth/logout');
  await focus();
  assert.match(text(), /Welcome to Banana/);
  assert.equal(field('Password').value, '');
});

test('an old session check cannot undo a completed login or restore an account after logout', async () => {
  await mount(null);
  let release;
  state.intercept = (path) =>
    path === '/auth/session'
      ? new Promise((resolve) => {
          release = resolve;
        })
      : null;
  await focus();
  await change('Email address or account ID', 'talent@example.test');
  await change('Password', 'Demo1234!');
  await click('Sign in');
  await act(async () => release(json({ user: null, csrfToken: 'old' })));
  assert.ok(document.querySelector('.workspace'));
  const previous = await state.server.dispatch('GET', '/auth/session');
  await focus();
  const finishOldCheck = release;
  state.intercept = null;
  await click('Sign out');
  await act(async () => finishOldCheck(json(previous)));
  assert.match(text(), /Welcome to Banana/);
  assert.equal(document.querySelector('.workspace'), null);
});

test('an unauthorised session role never renders talent or team pages', async () => {
  state.intercept = (path) =>
    path === '/auth/session'
      ? json({
          user: { id: 'unknown-user', displayName: 'Unknown', role: 'ADMIN' },
          csrfToken: 'token',
        })
      : null;
  await mount(null);
  assert.match(text(), /cannot open this workspace/);
  assert.equal(document.querySelector('.workspace'), null);
  assert.equal(
    state.requests.some((r) => /profile|opportunities|tags/.test(r.path)),
    false
  );
});

test('sign-in pending state rejects duplicate submits and cannot edit or navigate to another form', async () => {
  await mount(null);
  await change('Email address or account ID', 'talent@example.test');
  await change('Password', 'Demo1234!');
  let release;
  state.intercept = (path) =>
    path === '/auth/login'
      ? new Promise((resolve) => {
          release = resolve;
        })
      : null;
  await click('Sign in');
  assert.equal(field('Password').matches(':disabled'), true);
  assert.equal(button('Register').disabled, true);
  await act(async () =>
    document
      .querySelector('form')
      .dispatchEvent(new window.Event('submit', { bubbles: true, cancelable: true }))
  );
  assert.equal(state.requests.filter((r) => r.path === '/auth/login').length, 1);
  await act(async () =>
    release(json({ error: { code: 'INVALID_CREDENTIALS', message: 'Try again.' } }, 401))
  );
  assert.equal(button('Sign in').disabled, false);
});
