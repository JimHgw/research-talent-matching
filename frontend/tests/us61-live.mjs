import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import {
  act,
  mount,
  cleanup,
  until,
  text,
  field,
  change,
  click,
  login,
  checkbox,
  button,
  requests,
  independentBrowserFetch,
} from './support/live-app.js';
import { createApi } from '../src/api/client.js';

const { ids, hashes } = JSON.parse(process.env.TEST_REVIEW_DOCUMENTS_JSON);
const api = createApi();
const owner = createApi({ fetchImpl: independentBrowserFetch() });
const row = (name) =>
  [...document.querySelectorAll('.document-row')].find((entry) => entry.textContent.includes(name));
async function open(name) {
  await until(() => !!row(name));
  await act(async () =>
    [...row(name).querySelectorAll('button')]
      .find((b) => b.textContent.trim() === 'Review suggestions')
      .click()
  );
}
async function dialogClick(name) {
  const target = [...document.querySelectorAll('dialog button')].find(
    (b) => b.textContent.trim() === name
  );
  assert.ok(target && !target.disabled, `Missing or disabled review action: ${name}`);
  await act(async () => target.click());
}
const applyCount = () =>
  requests.filter((r) => r.method === 'POST' && r.url.endsWith('/apply')).length;

try {
  await mount();
  await login('talent@example.test');
  await until(() => text().includes('Tell your research story'));
  await api.session();
  const example = JSON.parse(
    await readFile(new URL('../../docs/api/examples/profile-write.json', import.meta.url), 'utf8')
  );
  let profile = await api.saveProfile(0, example.content);
  await api.confirm(profile.revision);
  await owner.session();
  await owner.login('talent@example.test', 'Test-password-123!');
  await click('My documents');
  await until(() => !!row('pending.docx'));
  assert.match(row('pending.docx').textContent, /Waiting for document processing/);
  assert.equal(
    [...row('pending.docx').querySelectorAll('button')].some(
      (b) => b.textContent.trim() === 'Review suggestions'
    ),
    false
  );
  await assert.rejects(
    api.extraction(ids.pending),
    (e) => e.code === 'EXTRACTION_NOT_READY' && e.status === 409
  );
  assert.match(row('failed.docx').textContent, /could not be processed/);
  assert.ok(
    [...row('failed.docx').querySelectorAll('button')].some(
      (b) => b.textContent.trim() === 'Enter manually'
    )
  );
  await assert.rejects(
    api.extraction(ids.failed),
    (e) => e.code === 'EXTRACTION_FAILED' && e.status === 422
  );

  // Reproduce the reported READY -> Review sequence using a real text PDF.
  const confirmations = requests.filter((r) => r.url.endsWith('/me/profile/confirmation')).length;
  await open('ready-pdf.pdf');
  await until(() => !!button('Apply reviewed sections'));
  assert.match(document.querySelector('dialog').textContent, /ready-pdf.pdf/);
  assert.doesNotMatch(document.querySelector('dialog').textContent, /not-recording/);
  for (const section of [
    'Education',
    'Courses',
    'Research experience',
    'Research outputs',
    'Research interests',
  ])
    await checkbox(section);
  await change('Supporting evidence', 'Task 61 corrected PDF evidence');
  await checkbox(
    'I understand that importing replaces the selected sections in my profile and requires a separate confirmation.'
  );
  await dialogClick('Apply reviewed sections');
  await until(
    () => text().includes('Tell your research story') && text().includes('Needs confirmation')
  );
  profile = await api.profile();
  assert.equal(profile.content.skills[0].evidenceText, 'Task 61 corrected PDF evidence');
  assert.equal(profile.confirmation.status, 'UNCONFIRMED');
  assert.equal(profile.origins.find((entry) => entry.field === 'skills').documentId, ids.readyPdf);
  assert.equal(
    requests.filter((r) => r.url.endsWith('/me/profile/confirmation')).length,
    confirmations
  );

  await click('My documents');
  await open('ready-word.docx');
  await until(() => !!button('Apply reviewed sections'));
  assert.match(document.querySelector('dialog').textContent, /ready-word.docx/);
  assert.equal(button('Apply reviewed sections').disabled, true);
  await change('Supporting evidence', 'Keep this Word correction');
  await checkbox(
    'I understand that importing replaces the selected sections in my profile and requires a separate confirmation.'
  );
  profile = await owner.profile();
  await owner.saveProfile(profile.revision, {
    ...profile.content,
    displayName: 'A newer saved profile',
  });
  const beforeConflict = applyCount();
  await dialogClick('Apply reviewed sections');
  await until(() => !!document.querySelector('dialog [role="alert"]'));
  assert.equal(field('Supporting evidence').value, 'Keep this Word correction');
  assert.equal(button('Apply reviewed sections').disabled, true);
  assert.equal(applyCount(), beforeConflict + 1);
  assert.equal((await api.profile()).content.displayName, 'A newer saved profile');
  await dialogClick('Reload suggestions');
  await until(() => !!button('Apply reviewed sections'));
  assert.equal(button('Apply reviewed sections').disabled, true);
  await dialogClick('Cancel');

  await open('empty.docx');
  await until(() => !!button('Continue with manual entry'));
  assert.match(document.querySelector('dialog').textContent, /No structured suggestions/);
  assert.equal(document.querySelector('dialog form'), null);
  await dialogClick('Continue with manual entry');
  await until(() => text().includes('Tell your research story'));
  assert.equal((await api.profile()).content.displayName, 'A newer saved profile');
  for (const key of ['readyPdf', 'readyWord']) {
    const bytes = Buffer.from(await (await api.download(ids[key])).arrayBuffer());
    assert.equal(createHash('sha256').update(bytes).digest('hex'), hashes[key]);
  }

  await click('My documents');
  await open('ready-word.docx');
  await until(() => !!button('Apply reviewed sections'));
  await api.logout();
  await api.session();
  await api.login('other@example.test', 'Test-password-123!');
  await act(async () => window.dispatchEvent(new window.Event('focus')));
  await until(() => text().includes('Tell your research story'));
  assert.equal(document.querySelector('dialog'), null);
  assert.equal(field('Display name').value, '');
  await assert.rejects(api.extraction(ids.readyWord), (e) => e.status === 404);
  await assert.rejects(api.download(ids.readyPdf), (e) => e.status === 404);
  await assert.rejects(api.apply(ids.readyWord, 0, {}), (e) => e.status === 404);
  console.log('US-61 real HTTP integration passed');
} finally {
  await cleanup();
}
