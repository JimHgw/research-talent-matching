import assert from 'node:assert/strict';
import { mount, cleanup, until, text, change, click } from './support/live-app.js';
import { createApi } from '../src/api/client.js';

const api = createApi();
try {
  await api.session();
  const email = 'registration@example.test';
  const sent = await api.requestRegistrationCode(email);
  assert.equal(sent.resendAfterSeconds, 60);
  assert.equal(sent.code, undefined);
  await assert.rejects(
    api.register({
      email,
      code: '999999',
      password: 'Test-password-123!',
      displayName: 'Registered talent',
      role: 'TALENT',
    }),
    (error) => error.code === 'VERIFICATION_CODE_INVALID'
  );
  const registered = await api.register({
    email,
    code: '012345',
    password: 'Test-password-123!',
    displayName: 'Registered talent',
    role: 'TALENT',
  });
  assert.match(registered.user.id, /^user_[a-f0-9]{32}$/);
  assert.equal((await api.profile()).revision, 0);
  assert.equal((await api.privacy()).discoverable, false);
  await api.logout();
  await mount();
  await until(() => text().includes('Welcome to Banana'));
  await change('Email address or account ID', registered.user.id);
  await change('Password', 'Test-password-123!');
  await click('Sign in');
  await until(() => text().includes('Tell your research story'));
  assert.match(text(), /Registered talent/);
  console.log('US-01-register real HTTP integration passed');
} finally {
  await cleanup();
}
