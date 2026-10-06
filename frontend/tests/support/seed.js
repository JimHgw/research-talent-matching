// Test double only. Never import this module from application code.
import baseProfile from '../../../docs/api/examples/profile-confirmed.json' with { type: 'json' };
import baseOpportunity from '../../../docs/api/examples/opportunity-published.json' with { type: 'json' };
import baseTags from '../../../docs/api/examples/tags.json' with { type: 'json' };

export const TEST_PASSWORD = 'Demo1234!';
export const TEST_ACCOUNTS = [
  {
    id: 'talent_demo_001',
    email: 'talent@example.test',
    displayName: 'Alex Morgan',
    role: 'TALENT',
    label: 'Talent workspace',
  },
  {
    id: 'team_demo_001',
    email: 'team@example.test',
    displayName: 'Research Lab',
    role: 'RESEARCH_TEAM',
    label: 'Research team',
  },
  {
    id: 'talent_new_001',
    email: 'new@example.test',
    displayName: 'New Talent',
    role: 'TALENT',
    label: 'Empty profile',
  },
];
export const SECTIONS = [
  'education',
  'courses',
  'researchExperience',
  'skills',
  'researchInterests',
  'researchOutputs',
];
export const PROFILE_FIELDS = ['displayName', 'disciplineGroup', ...SECTIONS];
export const emptyContent = () => ({
  displayName: '',
  disciplineGroup: null,
  ...Object.fromEntries(SECTIONS.map((key) => [key, []])),
});
export const tags = [
  ...baseTags.items,
  { id: 'skill_stats', label: 'Statistics', kind: 'SKILL', disciplineGroups: ['STEM', 'BUSINESS'] },
  {
    id: 'skill_visualisation',
    label: 'Data visualisation',
    kind: 'SKILL',
    disciplineGroups: ['STEM', 'BUSINESS'],
  },
  {
    id: 'interest_sustainability',
    label: 'Sustainability',
    kind: 'INTEREST',
    disciplineGroups: ['STEM', 'BUSINESS'],
  },
  {
    id: 'interest_economics',
    label: 'Behavioural economics',
    kind: 'INTEREST',
    disciplineGroups: ['BUSINESS'],
  },
];

export function createSeed() {
  const stamp = '2026-10-05T00:00:00Z';
  const alex = structuredClone(baseProfile);
  alex.content.displayName = 'Alex Morgan';
  alex.content.researchExperience[0].title = 'Research data exploration';
  const casey = structuredClone(alex);
  casey.talentId = 'talent_demo_002';
  casey.content.displayName = 'Casey Jordan';
  casey.content.skills = [
    {
      tagId: 'skill_python',
      claim: 'HAS',
      evidenceText: 'Prepared data for a synthetic research project.',
    },
    { tagId: 'skill_sql', claim: 'HAS', evidenceText: 'Queried a sample research database.' },
    {
      tagId: 'skill_stats',
      claim: 'HAS',
      evidenceText: 'Used descriptive statistics in a class project.',
    },
  ];
  const hidden = structuredClone(casey);
  hidden.talentId = 'talent_private';
  hidden.content.displayName = 'Private Demo Profile';
  const fresh = {
    talentId: 'talent_new_001',
    revision: 0,
    content: emptyContent(),
    confirmation: { status: 'UNCONFIRMED', confirmedRevision: null, confirmedAt: null },
    origins: SECTIONS.map((field) => ({ field, sourceType: 'MANUAL', documentId: null })),
    updatedAt: stamp,
  };
  const opportunity = structuredClone(baseOpportunity);
  opportunity._ownerId = 'team_demo_001';
  opportunity.content.title = 'Research assistant in data science';
  opportunity.content.description =
    'Help explore how transparent data analysis can support better research decisions. Work with a small team on reproducible experiments, data preparation and clear communication of findings. This is a synthetic opportunity for the Sprint 1 demonstration.';
  const ml = structuredClone(opportunity);
  ml.id = 'opp_demo_002';
  ml.content.title = 'Machine learning for sustainable cities';
  ml.content.university = 'Monash University';
  ml.content.researchArea = 'Urban sustainability';
  ml.content.description =
    'Explore interpretable machine learning methods using synthetic urban datasets. Contribute to experiments and discuss their limitations with an interdisciplinary team. Synthetic demo opportunity.';
  ml.content.requirements = [
    {
      id: 'req_ml',
      label: 'Interest in machine learning',
      kind: 'INTEREST',
      importance: 'REQUIRED',
      tagIds: ['interest_ml'],
    },
    {
      id: 'req_code',
      label: 'Python programming',
      kind: 'SKILL',
      importance: 'REQUIRED',
      tagIds: ['skill_python'],
    },
    {
      id: 'req_viz',
      label: 'Data visualisation',
      kind: 'SKILL',
      importance: 'PREFERRED',
      tagIds: ['skill_visualisation'],
    },
  ];
  const business = structuredClone(opportunity);
  business.id = 'opp_demo_003';
  business._ownerId = 'team_other';
  business.content.title = 'Understanding sustainable consumer choices';
  business.content.university = 'University of Sydney';
  business.content.disciplineGroup = 'BUSINESS';
  business.content.discipline = 'Business';
  business.content.researchArea = 'Behavioural economics';
  business.content.description =
    'Investigate patterns in consumer choices through structured analysis and research interviews. Synthetic demo opportunity.';
  business.content.requirements = [
    {
      id: 'req_behaviour',
      label: 'Behavioural economics interest',
      kind: 'INTEREST',
      importance: 'REQUIRED',
      tagIds: ['interest_economics'],
    },
    {
      id: 'req_interview',
      label: 'Research interviews',
      kind: 'SKILL',
      importance: 'PREFERRED',
      tagIds: ['skill_interviews'],
    },
  ];
  const draft = structuredClone(ml);
  draft.id = 'opp_draft_001';
  draft.status = 'DRAFT';
  draft.revision = 1;
  draft.content.title = 'A new research collaboration';
  draft.content.requirements = [];
  return {
    version: 1,
    sessionUserId: null,
    profiles: Object.fromEntries([alex, casey, hidden, fresh].map((p) => [p.talentId, p])),
    privacy: Object.fromEntries(
      [alex, casey, hidden, fresh].map((p) => [
        p.talentId,
        {
          revision: 0,
          discoverable: p === casey,
          visibleFields: p === casey ? [...PROFILE_FIELDS] : [],
          updatedAt: stamp,
        },
      ])
    ),
    opportunities: [opportunity, ml, business, draft],
    documents: [],
  };
}
