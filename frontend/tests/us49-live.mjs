import assert from 'node:assert/strict';
import {
  act,
  mount,
  remount,
  cleanup,
  until,
  text,
  field,
  change,
  click,
  login,
  independentBrowserFetch,
} from './support/live-app.js';
import { createApi } from '../src/api/client.js';
import { translate } from '../src/shared/i18n.jsx';
import { languageCatalog } from '../src/shared/locales/index.js';

const api = createApi();
const secondBrowser = createApi({ fetchImpl: independentBrowserFetch() });
try {
  await mount();
  await login('talent@example.test');
  await until(() => text().includes('Tell your research story'));
  const talent = (await api.session()).user;
  assert.equal(document.querySelector('.account-entry code').textContent, talent.id);
  await change('Display name', 'Private draft, preserve verbatim');
  await change('Language', 'zh-CN');
  assert.match(document.querySelector('nav').textContent, /我的资料/);
  assert.equal(field('Display name').value, 'Private draft, preserve verbatim');
  assert.equal(document.documentElement.lang, 'zh-CN');

  assert.equal((await secondBrowser.session()).user, null);
  const team = (await secondBrowser.login('team@example.test', 'Test-password-123!')).user;
  assert.equal(team.role, 'RESEARCH_TEAM');
  assert.equal((await api.session()).user.id, talent.id);
  await assert.rejects(secondBrowser.profile(), (error) => error.status === 403);
  await assert.rejects(api.saveOpportunity(null, null, {}), (error) => error.status === 403);
  await secondBrowser.logout();
  assert.equal((await api.session()).user.id, talent.id);

  // Same-cookie tabs can change identity; returning to a tab must remove the old draft.
  await api.logout();
  await api.session();
  await api.login('team@example.test', 'Test-password-123!');
  await act(async () => window.dispatchEvent(new window.Event('focus')));
  await until(() => text().includes('您的账号'));
  assert.equal(document.querySelector('.account-entry code').textContent, team.id);
  assert.doesNotMatch(text(), /Private draft/);
  assert.equal(document.querySelector('nav').textContent.includes('我的资料'), false);
  await remount();
  await until(() => text().includes('您的账号'));
  assert.equal(document.documentElement.lang, 'zh-CN');
  let previousLanguage = 'zh-CN';
  for (const [locale, { direction }] of Object.entries(languageCatalog)) {
    await change(translate(previousLanguage, 'Language'), locale);
    assert.equal(document.documentElement.lang, locale);
    assert.equal(document.documentElement.dir, direction);
    assert.equal(document.querySelector('.account-entry code').textContent, team.id);
    assert.equal(document.querySelector('.account-entry code').dir, 'ltr');
    assert.ok(text().includes(translate(locale, 'Your account')));
    if (locale === 'ar' || locale === 'ja') {
      await remount();
      await until(() => text().includes(translate(locale, 'Your account')));
      assert.equal(document.documentElement.lang, locale);
      assert.equal(document.documentElement.dir, direction);
    }
    previousLanguage = locale;
  }
  await change(translate(previousLanguage, 'Language'), 'zh-CN');
  await click('账号信息');
  assert.match(document.querySelector('dialog').textContent, /team@example.test/);
  await click('切换账号');
  await until(() => text().includes('欢迎使用 Banana'));
  assert.equal(document.querySelector('.account-entry'), null);
  await change('邮箱或账号 ID', talent.id);
  await change('密码', 'Test-password-123!');
  await click('显示密码');
  assert.equal(field('密码').type, 'text');
  await click('登录');
  await until(() => document.querySelector('.account-entry code')?.textContent === talent.id);
  await until(() => text().includes('Tell your research story'));
  assert.equal(field('Display name').value, '');
  await change('界面语言', 'en');
  await click('Sign out');
  await until(() => text().includes('Welcome to Banana'));
  assert.equal(field('Password').value, '');
  assert.equal(field('Password').type, 'password');
  console.log('US-49 real HTTP integration passed');
} finally {
  await cleanup();
}
