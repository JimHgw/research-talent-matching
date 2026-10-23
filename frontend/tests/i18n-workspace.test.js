import test from 'node:test';
import assert from 'node:assert/strict';
import {
  mount,
  click,
  change,
  checkbox,
  field,
  button,
  text,
  state,
  json,
  fixture,
} from './support/app-harness.js';
import { translate, translateError, languageStorageKey } from '../src/shared/i18n.jsx';
import { languageCatalog } from '../src/shared/locales/index.js';
import { auditInterfaceMessages } from '../scripts/check-i18n.js';
import { labels } from '../src/shared/profile-labels.js';
import { fieldConfigs } from '../src/features/profile/fields.js';
import { opportunityFields } from '../src/features/opportunities/fields.js';
import { displayDate } from '../src/shared/format.js';
const locales = Object.keys(languageCatalog);

test('every visible JSX message, field, notification and status has translations', async () => {
  const { problems, keys } = await auditInterfaceMessages();
  assert.deepEqual(problems, []);
  const messages = new Set([
    ...keys,
    ...Object.values(labels),
    ...Object.values(fieldConfigs)
      .flat()
      .map((f) => f[1]),
    ...opportunityFields.map((f) => f.label),
    'DRAFT',
    'PUBLISHED',
    'CONFIRMED',
    'UNCONFIRMED',
    'QUEUED',
    'PROCESSING',
    'READY',
    'FAILED',
    'MATCHED',
    'PARTIAL',
    'GAP',
    'UNKNOWN',
    'REQUIRED',
    'PREFERRED',
    'CV',
    'TRANSCRIPT',
    'STEM',
    'BUSINESS',
    '{count} characters',
    '{count} entries',
  ]);
  for (const locale of locales.filter((value) => value !== 'en'))
    for (const message of messages)
      assert.equal(
        typeof languageCatalog[locale].messages[message],
        'string',
        `${locale}: ${message}`
      );
});

for (const locale of locales) {
  test(`${locale}: opportunity labels, requirements, validation and save preserve domain values`, async () => {
    const t = (m, v) => translate(locale, m, v);
    await mount('team@example.test');
    await click('Opportunities');
    await click('Create opportunity');
    const input = {
      'Opportunity title': 'Original title العربية 中文',
      University: 'UNSW',
      Discipline: 'Computer Science',
      'Research area': 'AI research',
      Description: 'Verbatim: Create opportunity; Save draft.',
    };
    for (const [label, value] of Object.entries(input)) await change(label, value);
    await click('Add requirement');
    await change('Requirement 1 label', 'Python experience');
    await checkbox('Python');
    const before = state.requests.length;
    await change('Language', locale);
    assert.equal(state.requests.length, before);
    assert.ok(text().includes(t('Create opportunity')));
    assert.ok(text().includes(t('Opportunity details')));
    assert.equal(document.querySelector('.badge').textContent, t('DRAFT'));
    for (const [label, value] of Object.entries(input)) assert.equal(field(t(label)).value, value);
    assert.equal(field(t('Requirement {number} kind', { number: 1 })).value, 'SKILL');
    assert.equal(field(t('Requirement {number} importance', { number: 1 })).value, 'REQUIRED');
    assert.ok(
      text().includes(
        t('Tags for requirement {number} ({count}/{limit})', { number: 1, count: 1, limit: 20 })
      )
    );
    await change(t('University'), '   ');
    await click(t('Save draft'));
    assert.ok(
      document
        .querySelector('[role="alert"]')
        .textContent.includes(t('Complete all required fields with non-blank text.'))
    );
    await change(t('University'), 'UNSW');
    await click(t('Save draft'));
    assert.ok(text().includes(t('Opportunity saved.')));
    const request = state.requests.find((r) => r.path === '/opportunities' && r.method === 'POST');
    assert.equal(request.body.title, input['Opportunity title']);
    assert.equal(request.body.description, input.Description);
    assert.equal(request.body.disciplineGroup, 'STEM');
    assert.equal(request.body.requirements[0].kind, 'SKILL');
    assert.equal(request.body.requirements[0].importance, 'REQUIRED');
    assert.deepEqual(request.body.requirements[0].tagIds, ['skill_python']);
    await change(t('Language'), 'en');
    assert.equal(field('Opportunity title').value, input['Opportunity title']);
    assert.equal(document.documentElement.dir, 'ltr');
  });
  test(`${locale}: profile, privacy, documents, recommendations and saved pages localize`, async () => {
    const t = (m, v) => translate(locale, m, v);
    window.localStorage.setItem(languageStorageKey, locale);
    await mount();
    assert.ok(text().includes(t('Tell your research story')));
    assert.ok(text().includes(t('Education')));
    assert.ok(field(t('Skill title')));
    const draft = 'User text: Save changes, Privacy & visibility العربية';
    await change(t('Display name'), draft);
    await change(t('Language'), 'en');
    assert.equal(field('Display name').value, draft);
    await change('Language', locale);
    assert.equal(field(t('Display name')).value, draft);
    window.confirm = () => true;
    await click(t('Refresh profile'));
    await click(t('Privacy & visibility'));
    assert.ok(text().includes(t('Your profile. Your choice.')));
    assert.equal(document.querySelectorAll('.visibility-option').length, 8);
    assert.ok(
      text().includes(
        t(
          'Research interests also controls your research interest description and personal interest tags. Your resume description always stays private.'
        )
      )
    );
    await click(t('My documents'));
    assert.ok(text().includes(t('Add your CV or transcript')));
    assert.ok(field(t('Choose a document')));
    assert.equal(field(t('Document type')).options[1].value, 'TRANSCRIPT');
    await click(t('Recommended opportunities'));
    assert.ok(text().includes(t('Your recommended opportunities')));
    await click(t('Why this match?'));
    const modal = document.querySelector('dialog');
    assert.ok(modal.textContent.includes(t('EVIDENCE, NOT ASSUMPTIONS')));
    assert.ok(modal.textContent.includes(t('MATCHED')));
    assert.ok(modal.textContent.includes(t('Research interests')));
    await click(t('Close dialog'));
    await click(t('Saved opportunities'));
    assert.ok(text().includes(t('My Saved Opportunities')));
  });
}

test('document review and acknowledgement translate while source text remains verbatim', async () => {
  const doc = await fixture('document-ready');
  const extraction = await fixture('extraction-ready');
  extraction.documentId = doc.id;
  const source = 'Source: Review suggestions العربية 中文';
  extraction.suggestedSections.skills[0].evidenceText = source;
  state.intercept = (path) => {
    if (path.startsWith('/me/documents?'))
      return json({ items: [doc], page: 1, pageSize: 20, total: 1 });
    if (path === `/me/documents/${doc.id}/extraction`) return json(extraction);
    return null;
  };
  await mount();
  await click('My documents');
  await click('Review suggestions');
  await change('Language', 'zh-CN');
  assert.ok(document.querySelector('dialog').textContent.includes('审阅'));
  assert.equal(field(translate('zh-CN', 'Supporting evidence')).value, source);
  assert.equal(button(translate('zh-CN', 'Apply reviewed sections')).disabled, true);
  await checkbox(
    translate(
      'zh-CN',
      'I understand that importing replaces the selected sections in my profile and requires a separate confirmation.'
    )
  );
  await change('界面语言', 'ar');
  assert.equal(field(translate('ar', 'Supporting evidence')).value, source);
  assert.equal(button(translate('ar', 'Apply reviewed sections')).disabled, false);
});

test('known server templates, errors and dates localize without changing captured source', () => {
  const source = 'Python with Company X العربية';
  for (const locale of locales.filter((value) => value !== 'en')) {
    const t = (m, v) => translate(locale, m, v);
    const reason = `Could not reliably parse: ${source}`;
    assert.equal(t(reason), t('Could not reliably parse: {source}', { source }));
    assert.ok(t(reason).includes(source));
    assert.equal(
      translateError(locale, { code: 'REVISION_CONFLICT', message: 'Changed on server.' }),
      languageCatalog[locale].messages.errors.REVISION_CONFLICT
    );
    assert.equal(
      displayDate('2026-10-23T12:00:00Z', locale),
      new Intl.DateTimeFormat(locale, { day: 'numeric', month: 'short', year: 'numeric' }).format(
        new Date('2026-10-23T12:00:00Z')
      )
    );
  }
  assert.equal(translate('zh-CN', source), source);
});

test('team discovery and shared-profile details translate in every language', async () => {
  const list = await fixture('team-talent-page');
  const detail = await fixture('team-match-hidden-skills');
  detail.talent.fields.researchInterestText = 'Original research notes العربية';
  detail.talent.fields.customInterestTags = [
    { id: 'personal_source', label: 'Original personal label' },
  ];
  state.intercept = (path) =>
    path.includes('/talent-matches') ? json(path.includes('?') ? list : detail) : null;
  await mount('team@example.test');
  await click('Discover talent');
  let previous = 'en';
  for (const locale of locales) {
    const t = (m, v) => translate(locale, m, v);
    await change(translate(previous, 'Language'), locale);
    previous = locale;
    assert.ok(text().includes(t('Find people for your next idea')));
    assert.ok(field(t('Match talent to this opportunity')));
    await click(t('View evidence'));
    const modal = document.querySelector('dialog');
    assert.ok(modal.textContent.includes(t('Shared profile')));
    assert.ok(modal.textContent.includes(t('Research interest description')));
    assert.ok(modal.textContent.includes('Original research notes العربية'));
    assert.ok(modal.textContent.includes('Original personal label'));
    await click(t('Close dialog'));
  }
});

test('language changes during a pending profile write preserve controls and submit once', async () => {
  const { deferMutation } = await import('./support/deferred-mutation.js');
  const { act } = await import('./support/app-harness.js');
  await mount();
  await change('Display name', 'Pending source text');
  const release = deferMutation((path) => path === '/me/profile');
  await click('Save changes');
  await change('Language', 'ar');
  assert.equal(field(translate('ar', 'Display name')).value, 'Pending source text');
  assert.equal(button(translate('ar', 'Saving…')).disabled, true);
  assert.equal(button(translate('ar', 'Refresh profile')).disabled, true);
  assert.equal(
    state.requests.filter((r) => r.path === '/me/profile' && r.method === 'PUT').length,
    1
  );
  await act(release);
  assert.ok(
    text().includes(
      translate('ar', 'Profile saved. Review and confirm to use the latest information.')
    )
  );
});

test('unsaved opportunity confirmation uses the active language and keeps cancelled edits', async () => {
  await mount('team@example.test');
  await click('Opportunities');
  await click('Create opportunity');
  await change('Opportunity title', 'Do not discard this');
  await change('Language', 'zh-CN');
  let prompt;
  window.confirm = (message) => {
    prompt = message;
    return false;
  };
  await click(translate('zh-CN', 'Back to opportunities'));
  assert.equal(prompt, translate('zh-CN', 'Discard your unsaved opportunity changes?'));
  assert.equal(field(translate('zh-CN', 'Opportunity title')).value, 'Do not discard this');
});

test('compound extraction diagnostics preserve source and translate each system reason', async () => {
  const { translateDiagnostic } = await import('../src/shared/i18n.jsx');
  const reason = 'Could not reliably parse: Company X, العربية; More items need manual review.';
  for (const locale of locales.filter((value) => value !== 'en')) {
    const result = translateDiagnostic(locale, reason);
    assert.ok(result.includes('Company X, العربية'));
    assert.ok(result.includes(translate(locale, 'More items need manual review.')));
    assert.ok(!result.includes('Could not reliably parse:'));
  }
});

test('fatal recovery reads the saved language after the application provider unmounts', async () => {
  const { React, act } = await import('./support/app-harness.js');
  const { default: FatalError } = await import('../src/shared/FatalError.jsx');
  window.localStorage.setItem(languageStorageKey, 'zh-CN');
  await act(async () => state.root.render(React.createElement(FatalError)));
  assert.ok(text().includes(translate('zh-CN', 'Something interrupted this page.')));
  await change('界面语言', 'ar');
  assert.ok(button(translate('ar', 'Reload page')));
  assert.equal(document.documentElement.dir, 'rtl');
});
