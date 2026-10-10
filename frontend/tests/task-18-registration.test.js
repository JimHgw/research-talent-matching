import test from 'node:test';
import assert from 'node:assert/strict';
import {
  act,
  mount,
  state,
  text,
  field,
  change,
  click,
  button,
  json,
} from './support/app-harness.js';

const password = 'New-password-123!';
const sent = { expiresAt: '2026-10-10T00:10:00Z', resendAfterSeconds: 60 };
const registrationRequests = () =>
  state.requests.filter((request) => request.path.startsWith('/auth/register'));

async function open() {
  await mount(null);
  await click('Register');
  await change('Email address', 'new@example.test');
}

async function sendCode() {
  state.intercept = (path) => (path === '/auth/register/code' ? json(sent, 202) : null);
  await click('Send verification code');
}

async function fill(chosen = password, confirm = chosen) {
  await change('Verification code', '012345');
  await change('Display name', 'New researcher');
  await change('Password', chosen);
  await change('Confirm password', confirm);
}

test('the registration button navigates to /register and returning clears the sign-in password', async () => {
  await mount(null);
  await change('Email address or account ID', 'new@example.test');
  await change('Password', 'Do-not-retain-123!');
  await click('Register');
  assert.equal(window.location.pathname, '/register');
  assert.match(text(), /Create your Banana account/);
  assert.equal(field('Email address').value, 'new@example.test');
  assert.equal(registrationRequests().length, 0);
  await click('Back to sign in');
  assert.equal(window.location.pathname, '/');
  assert.match(text(), /Welcome to Banana/);
  assert.equal(field('Password').value, '');
});

test('direct navigation to /register and browser back/forward show the correct page', async () => {
  window.history.replaceState(null, '', '/register');
  await mount(null);
  assert.match(text(), /Create your Banana account/);
  await click('Back to sign in');
  await click('Register');
  for (const [direction, path, heading] of [
    ['back', '/', /Welcome to Banana/],
    ['forward', '/register', /Create your Banana account/],
  ]) {
    await act(async () => {
      const navigated = new Promise((resolve) =>
        window.addEventListener('popstate', resolve, { once: true })
      );
      window.history[direction]();
      await navigated;
    });
    assert.equal(window.location.pathname, path);
    assert.match(text(), heading);
  }
});

test('a successful email request locks the address and enforces the resend cooldown', async (t) => {
  t.mock.timers.enable({ apis: ['Date', 'setInterval'], now: Date.now() });
  await open();
  await sendCode();
  assert.deepEqual(registrationRequests()[0].body, { email: 'new@example.test' });
  assert.equal(field('Email address').readOnly, true);
  assert.equal(button('Resend in 60s').disabled, true);
  await click('Resend in 60s');
  assert.equal(registrationRequests().length, 1);
  await change('Verification code', '012345');
  await act(async () => t.mock.timers.tick(60_000));
  await click('Resend code');
  assert.equal(registrationRequests().length, 2);
  assert.equal(field('Verification code').value, '');
  assert.equal(button('Resend in 60s').disabled, true);
});

test('a failed email delivery keeps the editable email form and allows retry', async () => {
  await open();
  state.intercept = (path) =>
    path === '/auth/register/code'
      ? json({ error: { code: 'EMAIL_DELIVERY_FAILED', message: 'Email is unavailable.' } }, 503)
      : null;
  await click('Send verification code');
  assert.match(text(), /Email is unavailable/);
  assert.equal(field('Email address').readOnly, false);
  assert.equal(document.querySelector('input[autocomplete="one-time-code"]'), null);
  await sendCode();
  assert.ok(field('Verification code'));
});

test('password policy, confirmation and blank names block account creation', async () => {
  await open();
  await sendCode();
  for (const [chosen, confirm, message] of [
    ['abcdefg1', 'abcdefg1', /uppercase letter/],
    ['ABCDEFG1', 'ABCDEFG1', /lowercase letter/],
    ['Abcdefgh', 'Abcdefgh', /digit/],
    ['Abcd123', 'Abcd123', /At least 8/],
    [password, 'Different123!', /passwords must match/],
  ]) {
    await fill(chosen, confirm);
    await click('Create account');
    assert.match(text(), message);
  }
  await fill();
  await change('Display name', '   ');
  await click('Create account');
  assert.match(text(), /Enter your name/);
  assert.equal(
    registrationRequests().filter((request) => request.path === '/auth/register').length,
    0
  );
});

test('invalid or expired codes keep the form available with the selected role', async () => {
  await open();
  await sendCode();
  await fill();
  await change('Account type', 'RESEARCH_TEAM');
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
  assert.match(text(), /code is invalid or expired/);
  assert.equal(field('Account type').value, 'RESEARCH_TEAM');
  assert.equal(field('Display name').value, 'New researcher');
  assert.deepEqual(registrationRequests().at(-1).body, {
    email: 'new@example.test',
    code: '012345',
    password,
    displayName: 'New researcher',
    role: 'RESEARCH_TEAM',
  });
});

test('changing email clears the previous code and passwords and retains the sending cooldown', async () => {
  await open();
  await sendCode();
  await fill();
  await click('Change email');
  assert.equal(field('Email address').readOnly, false);
  assert.equal(document.querySelector('input[autocomplete="one-time-code"]'), null);
  assert.equal(document.querySelector('input[type="password"]'), null);
  assert.equal(button('Send code in 60s').disabled, true);
});

test('pending account creation prevents duplicate submission and button navigation', async () => {
  await open();
  await sendCode();
  await fill();
  let release;
  state.intercept = (path) =>
    path === '/auth/register'
      ? new Promise((resolve) => {
          release = resolve;
        })
      : null;
  await click('Create account');
  assert.equal(document.querySelector('.registration-fields').disabled, true);
  assert.equal(button('Back to sign in').disabled, true);
  await click('Please wait…');
  assert.equal(
    registrationRequests().filter((request) => request.path === '/auth/register').length,
    1
  );
  await act(async () =>
    release(json({ error: { code: 'SERVICE_UNAVAILABLE', message: 'Please try again.' } }, 503))
  );
  assert.match(text(), /Please try again/);
  assert.equal(document.querySelector('.registration-fields').disabled, false);
});
