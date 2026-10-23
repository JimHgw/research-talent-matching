import assert from 'node:assert/strict';
import {
  mount,
  login,
  click,
  change,
  field,
  button,
  checkbox,
  until,
  text,
  cleanup,
} from './support/live-app.js';
import { api } from '../src/api/client.js';
import { translate } from '../src/shared/i18n.jsx';
import { languageCatalog } from '../src/shared/locales/index.js';

let language = 'en';
const t = (m, values) => translate(language, m, values);
async function switchLanguage(next) {
  await change(t('Language'), next);
  language = next;
  assert.equal(document.documentElement.lang, language);
}
try {
  await mount();
  await login('team@example.test');
  await until(() => text().includes('Your account'));
  await click('Opportunities');
  await until(() => !!button('Create opportunity'));
  await click('Create opportunity');
  const title = 'Original opportunity 中文 العربية';
  for (const [label, value] of Object.entries({
    'Opportunity title': title,
    University: 'UNSW',
    Discipline: 'Computer Science',
    'Research area': 'AI',
    Description: 'Verbatim description: Create opportunity; Save draft.',
  }))
    await change(label, value);
  for (const locale of Object.keys(languageCatalog)) {
    await switchLanguage(locale);
    assert.equal(field(t('Opportunity title')).value, title);
    assert.ok(text().includes(t('Opportunity details')));
    assert.equal(document.querySelector('.badge').textContent, t('DRAFT'));
  }
  await switchLanguage('zh-CN');
  await click(t('Save draft'));
  await until(() => text().includes(t('Opportunity saved.')));
  await click(t('Add requirement'));
  await change(t('Requirement {number} label', { number: 1 }), 'Python requirement');
  await checkbox('Python');
  await click(t('Save changes'));
  await until(() => button(t('Publish opportunity'))?.disabled === false);
  await click(t('Publish opportunity'));
  await until(() => document.querySelector('.badge').textContent === t('PUBLISHED'));
  const own = await api.opportunities('mine');
  const published = own.items.find((o) => o.content.title === title);
  assert.ok(published && published.status === 'PUBLISHED');
  assert.equal(published.content.requirements[0].kind, 'SKILL');
  assert.deepEqual(published.content.requirements[0].tagIds, ['skill_python']);
  await switchLanguage('en');
  await click('Sign out');
  await until(() => text().includes('Welcome to Banana'));
  await login('talent@example.test');
  await until(() => text().includes('Tell your research story'));
  await change('Display name', 'Talent 中文 العربية');
  await click('Add skill');
  await change('Skill title', 'Python');
  const evidence = 'User evidence: Why this match? 中文 العربية';
  await change('Supporting evidence', evidence);
  await switchLanguage('zh-CN');
  assert.equal(field(t('Supporting evidence')).value, evidence);
  await click(t('Save changes'));
  await until(() =>
    text().includes(t('Profile saved. Review and confirm to use the latest information.'))
  );
  await checkbox(t('I have reviewed my saved profile and confirm it reflects my information.'));
  await click(t('Confirm profile'));
  await until(() => text().includes(t('This version is confirmed.')));
  const saved = await api.profile();
  assert.equal(saved.content.skills[0].evidenceText, evidence);
  assert.equal(saved.confirmation.status, 'CONFIRMED');
  await click(t('Privacy & visibility'));
  await until(() => text().includes(t('Choose what you share')));
  await checkbox(t('Skills'));
  await click(t('Save privacy settings'));
  await until(() =>
    text().includes(t('Privacy settings saved. Future team results use these choices.'))
  );
  assert.deepEqual((await api.privacy()).visibleFields, ['skills']);
  await click(t('Recommended opportunities'));
  await until(() => text().includes(title));
  await click(t('Why this match?'));
  await until(() => document.querySelector('dialog')?.textContent.includes(evidence));
  assert.ok(
    document
      .querySelector('dialog')
      .textContent.includes(t('All requested tags have confirmed supporting evidence.'))
  );
  await click(t('Close dialog'));
  await click(t('My documents'));
  await until(() => text().includes('review-cv.docx'));
  await click(t('Review suggestions'));
  await until(() => !!document.querySelector('dialog input'));
  const originalFileName = document.querySelector('.review-document bdi').textContent;
  assert.equal(originalFileName, 'review-cv.docx');
  await checkbox(
    t(
      'I understand that importing replaces the selected sections in my profile and requires a separate confirmation.'
    )
  );
  await switchLanguage('ar');
  assert.equal(document.querySelector('.review-document bdi').textContent, originalFileName);
  await click(t('Apply reviewed sections'));
  await until(
    () => text().includes(t('Tell your research story')) && !document.querySelector('dialog')
  );
  const imported = await api.profile();
  assert.equal(imported.confirmation.status, 'UNCONFIRMED');
  assert.ok(imported.origins.some((o) => o.sourceType === 'USER_REVIEWED_DOCUMENT'));
  await switchLanguage('en');
  assert.equal(field('Display name').value, 'Talent 中文 العربية');
  console.log('US-i18n real HTTP integration passed');
} finally {
  await cleanup();
}
