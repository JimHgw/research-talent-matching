import assert from 'node:assert/strict';
import { mount, remount, cleanup, until, text, field, change, click } from './support/live-app.js';
import { createApi } from '../src/api/client.js';

const api = createApi();
try {
  await mount();
  await until(() => text().includes('Welcome to Banana'));
  for (const [email, role, name, heading] of [
    ['registration@example.test', 'TALENT', 'Registered talent', 'Tell your research story'],
    ['registration-team@example.test', 'RESEARCH_TEAM', 'Registered team', 'Your account'],
  ]) {
    await click('Register');
    assert.equal(window.location.pathname, '/register');
    // A refreshed or directly opened registration URL remains a registration page.
    await remount();
    await until(() => text().includes('Create your Banana account'));
    await change('Email address', email);
    await click('Send verification code');
    await until(() => !!document.querySelector('input[autocomplete="one-time-code"]'));
    assert.equal(field('Email address').readOnly, true);
    await change('Verification code', '999999');
    await change('Account type', role);
    await change('Display name', name);
    await change('Password', 'Test-password-123!');
    await change('Confirm password', 'Test-password-123!');
    await click('Create account');
    await until(() => text().includes('registration code is invalid or expired'));
    await change('Verification code', '012345');
    await click('Create account');
    await until(() => text().includes(heading));
    assert.equal(window.location.pathname, '/');
    assert.match(text(), new RegExp(name));
    const registered = await api.session();
    assert.equal(registered.user.email, email);
    assert.equal(registered.user.role, role);
    assert.match(registered.user.id, /^user_[a-f0-9]{32}$/);
    assert.equal(document.querySelector('.account-entry code').textContent, registered.user.id);
    await click('Account details');
    assert.match(document.querySelector('dialog').textContent, new RegExp(registered.user.id));
    assert.match(document.querySelector('dialog').textContent, new RegExp(email));
    await click('Close dialog');
    if (role === 'TALENT') {
      assert.equal((await api.profile()).revision, 0);
      assert.equal((await api.privacy()).discoverable, false);
    }
    await click('Sign out');
    await until(() => text().includes('Welcome to Banana'));
    await change('Email address or account ID', registered.user.id);
    await change('Password', 'Test-password-123!');
    await click('Sign in');
    await until(() => text().includes(heading));
    assert.match(text(), new RegExp(name));
    assert.equal(document.querySelector('.account-entry code').textContent, registered.user.id);
    await click('Sign out');
    await until(() => text().includes('Welcome to Banana'));
  }
  console.log('US-01-register real HTTP integration passed');
} finally {
  await cleanup();
}
