import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { createApi } from '../src/api/client.js';
import {
  mount,
  cleanup,
  login,
  click,
  until,
  text,
  act,
  independentBrowserFetch,
} from './support/live-app.js';

// Real HTTP, independent sessions and a temporary database provided by pytest.
const talent = createApi({ fetchImpl: independentBrowserFetch() });
const team = createApi();
const fixture = async (name) =>
  JSON.parse(
    await readFile(new URL(`../../docs/api/examples/${name}.json`, import.meta.url), 'utf8')
  );

try {
  await talent.session();
  await talent.login('talent@example.test', 'Test-password-123!');
  const content = (await fixture('profile-write')).content;
  content.education = [
    {
      id: 'edu_53',
      institution: 'UNSW Sydney',
      qualification: 'Master of Data Science',
      discipline: 'Data Science',
      startYear: 2025,
      endYear: 2026,
    },
  ];
  content.researchExperience = [
    {
      id: 'exp_53',
      title: 'Research Assistant',
      organisation: 'Laboratory A',
      description: 'Built a classification pipeline.',
    },
  ];
  content.researchOutputs = [
    {
      id: 'output_53',
      title: 'Classification study',
      type: 'PUBLICATION',
      url: null,
      description: 'Compared two baseline models.',
    },
  ];
  const profile = await talent.saveProfile(0, content);
  await talent.confirm(profile.revision);
  async function share(fields, discoverable = true) {
    const privacy = await talent.privacy();
    await talent.savePrivacy({
      expectedRevision: privacy.revision,
      discoverable,
      visibleFields: fields,
    });
  }
  await share(['displayName', 'education', 'researchExperience', 'researchOutputs']);

  await mount();
  await login('team@example.test');
  await until(() => text().includes('Your account'));
  await team.session();
  const opportunityContent = await fixture('opportunity-create');
  opportunityContent.title = 'Academic evidence integration';
  opportunityContent.requirements = [
    {
      id: 'req_edu_53',
      label: 'Education check',
      kind: 'EDUCATION',
      importance: 'REQUIRED',
      tagIds: [],
      criteria: { qualification: 'Master of Data Science' },
    },
    {
      id: 'req_exp_53',
      label: 'Experience check',
      kind: 'RESEARCH_EXPERIENCE',
      importance: 'REQUIRED',
      tagIds: [],
      criteria: { title: 'Research Assistant', organisation: 'Another laboratory' },
    },
    {
      id: 'req_out_53',
      label: 'Publication check',
      kind: 'RESEARCH_OUTPUT',
      importance: 'PREFERRED',
      tagIds: [],
      criteria: { type: 'PUBLICATION' },
    },
    {
      id: 'req_unknown_53',
      label: 'Missing project check',
      kind: 'RESEARCH_OUTPUT',
      importance: 'PREFERRED',
      tagIds: [],
      criteria: { type: 'PROJECT' },
    },
  ];
  const draft = await team.saveOpportunity(null, null, opportunityContent);
  const opportunity = await team.publish(draft.id, draft.revision);
  await click('Discover talent');
  await until(() => !!document.querySelector('.talent-card'));
  await click('View evidence');
  await until(() => document.querySelectorAll('.evidence-row').length === 4);
  const row = (label) =>
    [...document.querySelectorAll('.evidence-row')].find(
      (item) => item.querySelector('h4').textContent === label
    );
  assert.equal(row('Education check').querySelector('.badge').textContent, 'MATCHED');
  assert.match(
    row('Education check').querySelector('.shared-record').textContent,
    /Master of Data Science.*UNSW Sydney/s
  );
  assert.equal(row('Experience check').querySelector('.badge').textContent, 'PARTIAL');
  assert.match(
    row('Experience check').querySelector('.shared-record').textContent,
    /Research Assistant.*Laboratory A/s
  );
  assert.equal(row('Publication check').querySelector('.badge').textContent, 'MATCHED');
  assert.match(
    row('Publication check').querySelector('.shared-record').textContent,
    /Classification study/
  );
  assert.equal(row('Missing project check').querySelector('.badge').textContent, 'UNKNOWN');
  assert.equal(row('Missing project check').querySelector('.evidence-box'), null);
  const result = await team.talentMatch(opportunity.id, profile.talentId);
  assert.deepEqual(
    result.requirements.flatMap((item) => item.evidence.map((e) => e.recordId)).sort(),
    ['edu_53', 'exp_53', 'output_53']
  );
  assert.equal(result.summary.algorithmVersion, 'academic-evidence-v3');
  assert.doesNotMatch(document.querySelector('dialog').textContent, /documentId|storagePath/);

  await share(['displayName', 'researchExperience', 'researchOutputs']);
  await act(async () => window.dispatchEvent(new window.Event('focus')));
  await until(() => !document.querySelector('dialog') && !!document.querySelector('.talent-card'));
  await click('View evidence');
  await until(() => document.querySelectorAll('.evidence-row').length === 4);
  assert.equal(row('Education check').querySelector('.badge').textContent, 'UNKNOWN');
  assert.equal(row('Education check').querySelector('.evidence-box'), null);
  assert.doesNotMatch(
    document.querySelector('dialog').textContent,
    /Master of Data Science|UNSW Sydney/
  );

  await share([], false);
  await click('Refresh talent');
  await until(() => text().includes('No discoverable talent yet'));
  assert.equal(document.querySelector('dialog'), null);
  await assert.rejects(
    team.talentMatch(opportunity.id, profile.talentId),
    (error) => error.status === 404
  );

  await share(['displayName', 'education']);
  await talent.saveProfile(profile.revision, { ...content, displayName: 'Needs reconfirmation' });
  await click('Refresh talent');
  await until(() => text().includes('No discoverable talent yet'));
  assert.equal(document.querySelector('.talent-card'), null);
  await assert.rejects(
    team.talentMatch(opportunity.id, profile.talentId),
    (error) => error.status === 404
  );

  await team.saveOpportunity(opportunity.id, opportunity.revision, {
    ...opportunityContent,
    deadlineAt: '2000-01-01T00:00:00Z',
  });
  await click('Refresh talent');
  await until(() => text().includes('Publish an opportunity first'));
  assert.equal(document.querySelector('.evidence-row'), null);
  console.log('US-53 real HTTP integration passed');
} finally {
  await cleanup();
}
