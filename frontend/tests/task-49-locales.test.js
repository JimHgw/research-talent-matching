import test from 'node:test';
import assert from 'node:assert/strict';
import { mount, act, state, field, change, click, text, json } from './support/app-harness.js';
import { languageStorageKey, translate, translateError } from '../src/shared/i18n.jsx';
import { languageCatalog } from '../src/shared/locales/index.js';

const placeholders = (value) => [...value.matchAll(/\{\w+\}/g)].map(([token]) => token).sort();

test('every shipped language has complete messages/errors and preserves all interpolation variables', () => {
  const source = languageCatalog['zh-CN'].messages;
  for (const [locale, { messages, direction, label }] of Object.entries(languageCatalog)) {
    assert.ok(label.trim());
    assert.equal(new Intl.Locale(locale).baseName, locale);
    assert.equal(direction, locale === 'ar' ? 'rtl' : 'ltr');
    if (locale === 'en') continue;
    assert.deepEqual(Object.keys(messages).sort(), Object.keys(source).sort(), locale);
    for (const [key, value] of Object.entries(messages)) {
      if (key === 'errors') continue;
      assert.equal(typeof value, 'string', `${locale}: ${key}`);
      assert.ok(value.trim(), `${locale}: ${key}`);
      assert.deepEqual(placeholders(value), placeholders(key), `${locale}: ${key}`);
    }
    assert.deepEqual(
      Object.keys(messages.errors).sort(),
      Object.keys(source.errors).sort(),
      locale
    );
    for (const message of Object.values(messages.errors)) assert.ok(message.trim(), locale);
  }
});

for (const [locale, { direction, messages }] of Object.entries(languageCatalog)) {
  test(`${locale}: preference, input values, password toggle, errors and return to English`, async () => {
    const t = (message, values) => translate(locale, message, values);
    window.localStorage.setItem(languageStorageKey, locale);
    await mount(null);
    assert.equal(document.documentElement.lang, locale);
    assert.equal(document.documentElement.dir, direction);
    assert.match(
      text(),
      new RegExp(t('Welcome to Banana.').replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
    );
    assert.equal(field(t('Language')).options.length, Object.keys(languageCatalog).length);
    const identifier = 'Verbatim@Example.test';
    const password = 'Original-password-123!';
    await change(t('Email address or account ID'), identifier);
    await change(t('Password'), password);
    assert.equal(field(t('Email address or account ID')).dir, 'ltr');
    assert.equal(field(t('Password')).dir, 'ltr');
    await click(t('Show {label}', { label: t('Password').toLowerCase() }));
    assert.equal(field(t('Password')).type, 'text');
    await change(t('Language'), 'en');
    assert.equal(document.documentElement.dir, 'ltr');
    assert.equal(field('Email address or account ID').value, identifier);
    assert.equal(field('Password').value, password);
    await change('Language', locale);
    assert.equal(window.localStorage.getItem(languageStorageKey), locale);
    state.intercept = (path) =>
      path === '/auth/login'
        ? json({ error: { code: 'INVALID_CREDENTIALS', message: 'Server credential error' } }, 401)
        : null;
    await click(t('Sign in'));
    assert.equal(
      document.querySelector('[role="alert"] strong').textContent,
      messages.errors?.INVALID_CREDENTIALS || 'Server credential error'
    );
    assert.deepEqual(state.requests.find((request) => request.path === '/auth/login').body, {
      email: identifier,
      password,
    });
    assert.equal(field(t('Password')).value, password);
    await change(t('Language'), 'en');
    assert.equal(document.documentElement.lang, 'en');
    assert.equal(document.documentElement.dir, 'ltr');
  });
}

test('all languages preserve account identity and switch navigation without making domain writes', async () => {
  await mount('team@example.test');
  const { user } = await state.server.dispatch('GET', '/auth/session');
  const requests = [...state.requests];
  let previous = 'en';
  for (const locale of Object.keys(languageCatalog)) {
    const t = (message, values) => translate(locale, message, values);
    await change(translate(previous, 'Language'), locale);
    previous = locale;
    assert.equal(document.querySelector('.account-entry code').textContent, user.id);
    assert.equal(document.querySelector('.account-entry code').dir, 'ltr');
    assert.ok(document.querySelector('nav').textContent.includes(t('My opportunities')));
    await click(t('Account details'));
    assert.ok(document.querySelector('dialog').textContent.includes(user.email));
    assert.ok(document.querySelector('dialog').textContent.includes(user.displayName));
    assert.equal(document.querySelector('dialog code').dir, 'ltr');
    await click(t('Close dialog'));
  }
  assert.deepEqual(state.requests, requests);
});

test('Arabic mobile navigation remains guarded and language changes restore document direction', async () => {
  window.localStorage.setItem(languageStorageKey, 'ar');
  await mount();
  await click(translate('ar', 'Open navigation'));
  assert.equal(document.documentElement.dir, 'rtl');
  assert.ok(document.querySelector('.workspace-body').hasAttribute('inert'));
  await act(async () =>
    window.dispatchEvent(new window.KeyboardEvent('keydown', { key: 'Escape' }))
  );
  assert.equal(document.querySelector('.workspace-body').hasAttribute('inert'), false);
  await change(translate('ar', 'Language'), 'ja');
  assert.equal(document.documentElement.lang, 'ja');
  assert.equal(document.documentElement.dir, 'ltr');
});

test('unknown keys/errors fall back safely and interpolation never translates user-provided values', () => {
  for (const locale of Object.keys(languageCatalog)) {
    const marker = 'Research team <Verbatim> الاسم';
    assert.ok(translate(locale, 'Signed in as {name}.', { name: marker }).includes(marker));
    assert.equal(translate(locale, 'Future module message'), 'Future module message');
    assert.equal(
      translateError(locale, { code: '__proto__', message: 'Unrecognised server error' }),
      'Unrecognised server error'
    );
  }
  assert.equal(translate('constructor', 'Sign in'), 'Sign in');
  assert.equal(translate('not-supported', 'Sign in'), 'Sign in');
});
