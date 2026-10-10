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

const nextPassword = 'New-password-456!';
const sent = { expiresAt: '2026-10-10T00:10:00Z', resendAfterSeconds: 60 };
const resetRequests = () =>
  state.requests.filter((request) => request.path.startsWith('/auth/login/reset'));
async function open() {
  await mount(null);
  await change('Email address or account ID', 'talent@example.test');
  await click('Reset password');
}
async function choosePassword(newValue = nextPassword, confirm = newValue) {
  await change('New password', newValue);
  await change('Confirm new password', confirm);
}

test('current-password reset submits chosen credentials and returns to sign in with cleared passwords', async () => {
  await open();
  state.intercept = (path, options, body) => {
    if (path !== '/auth/login/reset') return null;
    return body.currentPassword === 'wrong'
      ? json(
          { error: { code: 'INVALID_CREDENTIALS', message: 'The current password is incorrect.' } },
          401
        )
      : json({ user: null, csrfToken: 'reset-token' });
  };
  await change('Current password', 'wrong');
  await choosePassword();
  await click('Update password');
  assert.match(text(), /current password is incorrect/);
  assert.equal(field('New password').value, nextPassword);
  await change('Current password', 'Demo1234!');
  await click('Update password');
  assert.match(text(), /Password updated. Sign in with your new password/);
  assert.equal(field('Password').value, '');
  assert.equal(field('Email address or account ID').value, 'talent@example.test');
  assert.deepEqual(resetRequests().at(-1).body, {
    method: 'PASSWORD',
    identifier: 'talent@example.test',
    currentPassword: 'Demo1234!',
    newPassword: nextPassword,
    confirmPassword: nextPassword,
  });
});

test('weak passwords, mismatched confirmation and unchanged passwords block submission', async () => {
  await open();
  await change('Current password', 'Demo1234!');
  for (const [chosen, confirm, message] of [
    ['abcdefgh1', 'abcdefgh1', /uppercase letter/],
    ['ABCDEFGH1', 'ABCDEFGH1', /lowercase letter/],
    ['Abcdefgh', 'Abcdefgh', /digit/],
    ['Abcd123', 'Abcd123', /At least 8/],
    [nextPassword, 'Different123!', /must match/],
    ['Demo1234!', 'Demo1234!', /must be different/],
  ]) {
    await choosePassword(chosen, confirm);
    await click('Update password');
    assert.match(text(), message);
  }
  assert.equal(resetRequests().length, 0);
});

test('email reset requires successful server verification before exposing new-password fields', async () => {
  await open();
  await click('Use an email code');
  assert.equal(document.querySelector('input[autocomplete="new-password"]'), null);
  state.intercept = (path, options, body) => {
    if (path.endsWith('/reset/code')) return json(sent, 202);
    if (path.endsWith('/reset/verify'))
      return body.code === '012345'
        ? json({ verified: true, expiresAt: sent.expiresAt })
        : json(
            {
              error: {
                code: 'VERIFICATION_CODE_INVALID',
                message: 'The code is invalid or expired.',
              },
            },
            422
          );
    if (path.endsWith('/reset')) return json({ user: null, csrfToken: 'new-anonymous' });
    return null;
  };
  await click('Send code');
  assert.equal(button('Resend in 60s').disabled, true);
  assert.equal(field('Email address').readOnly, true);
  await change('Verification code', '999999');
  await click('Verify email');
  assert.match(text(), /code is invalid or expired/);
  assert.equal(document.querySelector('input[autocomplete="new-password"]'), null);
  await change('Verification code', '012345');
  await click('Verify email');
  assert.match(text(), /Email verified/);
  await choosePassword();
  await click('Update password');
  assert.match(text(), /Password updated/);
  assert.deepEqual(resetRequests().at(-1).body, {
    method: 'EMAIL_CODE',
    email: 'talent@example.test',
    newPassword: nextPassword,
    confirmPassword: nextPassword,
  });
});

test('failed delivery keeps email input available; an expired grant returns to verification', async () => {
  await open();
  await click('Use an email code');
  state.intercept = (path) =>
    path.endsWith('/reset/code')
      ? json({ error: { code: 'EMAIL_DELIVERY_FAILED', message: 'Email is unavailable.' } }, 503)
      : null;
  await click('Send code');
  assert.match(text(), /Email is unavailable/);
  assert.equal(field('Email address').readOnly, false);
  state.intercept = (path) => {
    if (path.endsWith('/reset/code')) return json(sent, 202);
    if (path.endsWith('/reset/verify')) return json({ verified: true, expiresAt: sent.expiresAt });
    if (path.endsWith('/reset'))
      return json(
        { error: { code: 'VERIFICATION_CODE_INVALID', message: 'Verification expired.' } },
        422
      );
    return null;
  };
  await click('Send code');
  await change('Verification code', '012345');
  await click('Verify email');
  await choosePassword();
  await click('Update password');
  assert.match(text(), /Verification expired/);
  assert.equal(document.querySelector('input[autocomplete="new-password"]'), null);
  assert.equal(field('Email address').readOnly, false);
  assert.ok(button('Send code'));
});

test('pending reset prevents duplicate submission, method switching and navigation', async () => {
  await open();
  await change('Current password', 'Demo1234!');
  await choosePassword();
  let release;
  state.intercept = (path) =>
    path === '/auth/login/reset'
      ? new Promise((resolve) => {
          release = resolve;
        })
      : null;
  await click('Update password');
  assert.equal(document.querySelector('.reset-fields').disabled, true);
  assert.equal(button('Use an email code').disabled, true);
  assert.equal(button('Back to sign in').disabled, true);
  await click('Please wait…');
  assert.equal(resetRequests().length, 1);
  await act(async () => release(json({ user: null, csrfToken: 'new-token' })));
  assert.match(text(), /Password updated/);
});
