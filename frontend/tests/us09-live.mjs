import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
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
  act,
  requests,
} from './support/live-app.js';
import { createApi } from '../src/api/client.js';

const originalBytes = readFileSync(process.env.TEST_DOCUMENT_PATH);
const documentName = process.env.TEST_DOCUMENT_NAME || 'review-cv.docx';
const documentType =
  process.env.TEST_DOCUMENT_MEDIA_TYPE ||
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document';

try {
  // Prepare and confirm a profile through the React page.
  await mount();
  await login('talent@example.test');
  await until(() => text().includes('Tell your research story'));

  await change('Display name', 'US-09 HTTP talent');
  await click('Add education');
  await change('Institution *', 'UNSW');
  await change('Qualification *', 'Master of IT');
  await checkbox('Machine learning');
  await click('Save changes');

  await until(() => !!button('Save changes') && !field('Display name').matches(':disabled'));

  await checkbox('I have reviewed my saved profile and confirm it reflects my information.');
  await click('Confirm profile');
  await until(() => text().includes('This version is confirmed.'));

  const api = createApi();
  await api.session();
  const before = await api.profile();

  const confirmationCount = requests.filter(
    (request) => request.method === 'POST' && request.url.endsWith('/me/profile/confirmation')
  ).length;

  // Select the real DOCX file and submit the upload form.
  await click('My documents');
  await until(() => text().includes('Add your CV or transcript'));

  const input = field('Choose a document');
  const file = new File([originalBytes], documentName, { type: documentType });

  await act(async () => {
    Object.defineProperty(input, 'files', {
      configurable: true,
      value: [file],
    });
    input.dispatchEvent(new window.Event('change', { bubbles: true }));
  });

  // jsdom simulates file selection; submit the actual React form.
  await act(async () =>
    input.closest('form').dispatchEvent(
      new window.Event('submit', {
        bubbles: true,
        cancelable: true,
      })
    )
  );

  await until(() => !!button('Review suggestions'));

  // Uploading and processing must leave the profile unchanged.
  assert.deepEqual(await api.profile(), before);

  const documents = await api.documents();
  const uploaded = documents.items.find((item) => item.fileName === documentName);
  assert.ok(uploaded);
  assert.equal(uploaded.status, 'READY');
  const extraction = await api.extraction(uploaded.id);
  assert.deepEqual(Object.keys(extraction.suggestedSections).sort(), [
    'courses',
    'customInterestTags',
    'education',
    'researchExperience',
    'researchInterestText',
    'researchInterests',
    'researchOutputs',
    'resumeDescription',
    'skills',
  ]);
  assert.ok(
    extraction.uncertainFields.some(
      (item) => item.field === 'skills' && item.reason.includes('COBOL')
    )
  );

  // Check the frontend download client against the real backend.
  const downloaded = await api.download(uploaded.id);
  assert.deepEqual(Buffer.from(await downloaded.arrayBuffer()), originalBytes);

  // Edit the suggestions and import only the skills section.
  await click('Review suggestions');
  await until(() => !!button('Apply reviewed sections'));
  assert.ok(document.querySelector('dialog').textContent.includes(documentName));
  assert.doesNotMatch(document.querySelector('dialog').textContent, /not-recording/);
  assert.equal(button('Apply reviewed sections').disabled, true);
  assert.ok(text().includes('COBOL'));

  for (const label of [
    'Education',
    'Courses',
    'Research experience',
    'Research outputs',
    'Research interest description',
    'Personal interest tags',
    'Resume description',
  ]) {
    await checkbox(label);
  }

  await change('Supporting evidence', 'Reviewed through the React page.');
  await click('Remove skill 2');
  await checkbox('Research interests');

  await checkbox(
    'I understand that importing replaces the selected sections in my profile and requires a separate confirmation.'
  );
  await click('Apply reviewed sections');

  await until(
    () => text().includes('Tell your research story') && text().includes('Needs confirmation')
  );

  const imported = await api.profile();

  assert.equal(imported.revision, before.revision + 1);
  assert.deepEqual(imported.content.skills, [
    {
      tagId: 'skill_python',
      claim: 'HAS',
      evidenceText: 'Reviewed through the React page.',
    },
  ]);

  for (const key of Object.keys(before.content)) {
    if (key !== 'skills') {
      assert.deepEqual(imported.content[key], before.content[key]);
    }
  }

  assert.deepEqual(imported.confirmation, {
    status: 'UNCONFIRMED',
    confirmedRevision: null,
    confirmedAt: null,
  });

  assert.deepEqual(
    imported.origins.find((item) => item.field === 'skills'),
    {
      field: 'skills',
      sourceType: 'USER_REVIEWED_DOCUMENT',
      documentId: uploaded.id,
    }
  );

  assert.deepEqual(
    imported.origins.find((item) => item.field === 'researchInterests'),
    before.origins.find((item) => item.field === 'researchInterests')
  );

  // Importing must not automatically call the confirmation endpoint.
  assert.equal(
    requests.filter(
      (request) => request.method === 'POST' && request.url.endsWith('/me/profile/confirmation')
    ).length,
    confirmationCount
  );

  assert.equal(
    requests.filter((request) => request.method === 'POST' && request.url.endsWith('/apply'))
      .length,
    1
  );

  // Confirm the imported version through the profile page.
  await checkbox('I have reviewed my saved profile and confirm it reflects my information.');
  await click('Confirm profile');
  await until(() => text().includes('This version is confirmed.'));

  const confirmed = await api.profile();
  assert.equal(confirmed.revision, imported.revision);
  assert.equal(confirmed.confirmation.status, 'CONFIRMED');
  assert.equal(confirmed.confirmation.confirmedRevision, imported.revision);

  // Reuse the same real document/review workflow for US-11 text and personal tags.
  await click('My documents');
  await until(() => !!button('Review suggestions'));
  await click('Review suggestions');
  await until(() => !!button('Apply reviewed sections'));
  assert.equal(
    field('Research interest description').value,
    'Machine learning; Climate-resilient urban systems'
  );
  assert.equal(field('Personal interest label').value, 'Climate-resilient urban systems');
  for (const label of [
    'Education',
    'Courses',
    'Research experience',
    'Research outputs',
    'Skills',
    'Research interests',
  ]) {
    await checkbox(label);
  }
  await change('Research interest description', 'Reviewed ecological forecasting interests.');
  assert.ok(field('Resume description').value.includes('Bachelor of Science'));
  await change(
    'Resume description',
    'Reviewed unified resume description with Python, SQL and ecological forecasting.'
  );
  await change('Personal interest label', 'Ecological forecasting');
  await checkbox(
    'I understand that importing replaces the selected sections in my profile and requires a separate confirmation.'
  );
  await click('Apply reviewed sections');
  await until(
    () => text().includes('Tell your research story') && text().includes('Needs confirmation')
  );
  const withText = await api.profile();
  assert.equal(withText.content.researchInterestText, 'Reviewed ecological forecasting interests.');
  assert.equal(
    withText.content.resumeDescription,
    'Reviewed unified resume description with Python, SQL and ecological forecasting.'
  );
  assert.equal(withText.content.customInterestTags.length, 1);
  assert.equal(withText.content.customInterestTags[0].label, 'Ecological forecasting');
  assert.match(withText.content.customInterestTags[0].id, /^personal_/);
  assert.deepEqual(withText.content.skills, confirmed.content.skills);
  assert.deepEqual(withText.content.researchInterests, confirmed.content.researchInterests);
  assert.equal(withText.confirmation.status, 'UNCONFIRMED');
  assert.equal(field('Research interest description').value, withText.content.researchInterestText);
  assert.equal(field('Personal interest label').value, 'Ecological forecasting');
  assert.equal(
    (await api.tags()).items.some((tag) => tag.label === 'Ecological forecasting'),
    false
  );

  console.log('US-09 real HTTP integration passed');
} finally {
  await cleanup();
}
