import assert from 'node:assert/strict';
import {
  mount,
  remount,
  cleanup,
  until,
  text,
  field,
  change,
  click,
  login,
  requests,
} from './support/live-app.js';
import { createApi } from '../src/api/client.js';

try {
  await mount();
  await until(() => text().includes('Welcome to Banana'));
  assert.equal(requests.filter((request) => request.url.endsWith('/auth/session')).length, 1);
  await change('Email address or account ID', 'talent@example.test');
  await change('Password', 'incorrect');
  await click('Sign in');
  await until(() => text().includes('email or password is incorrect'));
  await login('talent@example.test');
  await until(() => text().includes('Tell your research story'));
  await change('Display name', 'Live integration talent');
  await change('Discipline group', 'STEM');
  await click('Add education');
  await change('Institution *', 'UNSW');
  await change('Qualification *', 'Master of IT');
  await change('Start year', '2025');
  await click('Add education');
  await click('Remove Education record 2');
  await click('Add courses');
  await change('Course name *', 'Research methods');
  const courseCode = 'COMP'.repeat(50);
  await change('Course code', courseCode);
  assert.equal(field('Course code').maxLength, 200);
  await click('Add research experience');
  await change('Project / role title *', 'Synthetic research project');
  await click('Add research outputs');
  await change('Output title *', 'Sample output');
  const outputUrl = `https://example.test/research/${'x'.repeat(220)}`;
  await change('Link (optional)', outputUrl);
  await click('Add skill');
  await change('Skill title', 'Financial modelling');
  await change('Supporting evidence', 'Built the test project.');
  const headings = [...document.querySelectorAll('.profile-fields h3')].map(
    (heading) => heading.textContent
  );
  assert.ok(!headings.includes('Research interests'));
  assert.ok(!headings.includes('Research interest description'));
  assert.ok(headings.includes('Personal interest tags'));

  // Per-interest descriptions are a frontend change; the backend contract is unchanged.
  // Check the new editor and its validation, then remove the draft before saving.
  await click('Add personal interest');
  assert.equal(field('Personal interest label').validity.valueMissing, true);
  assert.equal(field('Personal interest description').validity.valueMissing, true);
  await change('Personal interest label', 'Ecological forecasting');
  assert.equal(field('Personal interest description').checkValidity(), false);
  await change('Personal interest description', 'Predicting changes in ecosystems.');
  assert.equal(field('Personal interest label').checkValidity(), true);
  assert.equal(field('Personal interest description').checkValidity(), true);
  await click('Remove personal interest');
  assert.equal(document.querySelectorAll('.record-list .record').length, 0);
  await click('Save changes');
  await until(() => text().includes('Profile saved.'));
  const api = createApi();
  await api.session();
  const saved = await api.profile();
  assert.equal(saved.revision, 1);
  assert.equal(saved.content.displayName, 'Live integration talent');
  assert.equal(saved.content.courses[0].code, courseCode);
  assert.equal(saved.content.education[0].startYear, 2025);
  assert.equal(saved.content.education[0].endYear, null);
  assert.equal(saved.content.researchOutputs[0].url, outputUrl);
  assert.equal(saved.content.researchOutputs[0].type, 'PROJECT');
  assert.equal(saved.content.skills[0].title, 'Financial modelling');
  assert.deepEqual(Object.keys(saved.content.skills[0]).sort(), ['evidenceText', 'id', 'title']);
  assert.deepEqual(saved.content.researchInterests, []);
  assert.deepEqual(saved.content.customInterestTags, []);
  assert.deepEqual(Object.keys(saved.content).sort(), [
    'courses',
    'customInterestTags',
    'disciplineGroup',
    'displayName',
    'education',
    'researchExperience',
    'researchInterestText',
    'researchInterests',
    'researchOutputs',
    'resumeDescription',
    'skills',
  ]);
  for (const section of ['education', 'courses', 'researchExperience', 'researchOutputs'])
    assert.match(saved.content[section][0].id, /^record_/);
  for (const section of ['education', 'courses', 'researchExperience', 'skills', 'researchOutputs'])
    assert.equal(saved.content[section].length, 1, section);

  // Reload the React application while keeping the browser cookie.
  await remount();
  await until(() => text().includes('Tell your research story'));
  assert.equal(field('Display name').value, 'Live integration talent');
  assert.equal(field('Institution *').value, 'UNSW');
  assert.equal(field('Course code').value, courseCode);
  assert.equal(field('Link (optional)').value, outputUrl);
  assert.equal(field('Skill title').value, 'Financial modelling');

  await api.saveProfile(1, { ...saved.content, displayName: 'Saved by another tab' });
  await change('Display name', 'Keep my draft');
  await click('Save changes');
  await until(() => text().includes('Your profile changed.'));
  assert.equal(field('Display name').value, 'Keep my draft');
  await click('Reload latest data');
  await until(() => document.querySelector('input')?.value === 'Saved by another tab');
  await click('Sign out');
  await until(() => text().includes('Welcome to Banana'));
  await assert.rejects(api.profile(), (error) => error.status === 401);

  await login('other@example.test');
  await until(() => text().includes('Tell your research story'));
  assert.equal(field('Display name').value, '');
  assert.doesNotMatch(text(), /UNSW|Saved by another tab/);
  await click('Sign out');
  await login('team@example.test');
  await until(() => text().includes('Your account'));
  await assert.rejects(api.profile(), (error) => error.status === 403);
  await click('Sign out');
  await until(() => text().includes('Welcome to Banana'));
  console.log('US-01 real HTTP integration passed');
} finally {
  await cleanup();
}
