import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { createReviewRepository } from '../src/api/review-repository.ts';
import { ApiError } from '../src/api/errors.js';
import { requireMatchDetail, requireMatchPage } from '../src/api/match-contract.ts';
import {
  applyReviewedExtraction,
  loadExtractionReview,
} from '../src/features/documents/extraction-review-use-cases.ts';

const fixture = async (name) =>
  JSON.parse(
    await readFile(new URL(`../../docs/api/examples/${name}.json`, import.meta.url), 'utf8')
  );
const invalidResponse = { code: 'INVALID_RESPONSE' };

test('document review loads a contract-valid extraction and a canonical profile through an injected repository', async () => {
  const extraction = await fixture('extraction-ready');
  const profile = await fixture('profile-confirmed');
  const signal = new AbortController().signal;
  const repository = createReviewRepository({
    async extraction(documentId, options) {
      assert.equal(documentId, extraction.documentId);
      assert.equal(options.signal, signal);
      return extraction;
    },
    async profile(options) {
      assert.equal(options.signal, signal);
      return profile;
    },
  });
  assert.deepEqual(await loadExtractionReview(repository, extraction.documentId, { signal }), {
    extraction,
    profile,
  });
});

test('review boundary rejects malformed records, invalid revisions and inconsistent confirmation', async () => {
  const extraction = await fixture('extraction-ready');
  const profile = await fixture('profile-confirmed');
  const malformed = [
    [{ ...extraction, suggestedSections: { skills: [null] } }, profile],
    [extraction, { ...profile, revision: '5' }],
    [
      extraction,
      {
        ...profile,
        content: {
          ...profile.content,
          customInterestTags: [{ id: 'personal_1', label: 'Ecology', description: 42 }],
        },
      },
    ],
    [
      extraction,
      {
        ...profile,
        confirmation: { ...profile.confirmation, confirmedRevision: profile.revision + 1 },
      },
    ],
  ];
  for (const [incomingExtraction, incomingProfile] of malformed) {
    const repository = createReviewRepository({
      extraction: async () => incomingExtraction,
      profile: async () => incomingProfile,
    });
    await assert.rejects(loadExtractionReview(repository, extraction.documentId), invalidResponse);
  }
  const malformedError = new ApiError(409, {
    error: { code: 'REVISION_CONFLICT', fieldErrors: {}, currentRevision: '5' },
  });
  assert.equal(malformedError.code, 'REVISION_CONFLICT');
  assert.deepEqual(malformedError.fields, []);
  assert.equal(malformedError.currentRevision, undefined);
});

test('apply sends only selected sections with the loaded revision, including deliberate clears', async () => {
  const extraction = await fixture('extraction-ready');
  const profile = await fixture('profile-confirmed');
  const saved = {
    ...profile,
    revision: profile.revision + 1,
    confirmation: { status: 'UNCONFIRMED', confirmedRevision: null, confirmedAt: null },
  };
  let request;
  const repository = createReviewRepository({
    extraction: async () => extraction,
    profile: async () => profile,
    async apply(...args) {
      request = args;
      return saved;
    },
  });
  const review = await loadExtractionReview(repository, extraction.documentId);
  const result = await applyReviewedExtraction(
    repository,
    review,
    { skills: [], researchInterestText: '', researchInterests: ['tag_ignored'] },
    ['skills', 'researchInterestText']
  );
  assert.deepEqual(request, [
    extraction.documentId,
    profile.revision,
    { skills: [], researchInterestText: '' },
  ]);
  assert.equal(result, saved);
});

test('matching boundaries accept both score contracts and reject malformed scores and methods', async () => {
  const current = await fixture('owner-match-requirement-semantic');
  const legacy = await fixture('owner-match-semantic');
  assert.equal(requireMatchDetail(current), current);
  assert.equal(requireMatchDetail(legacy), legacy);
  const bad = structuredClone(current);
  bad.requirements[0].scoring.method = 'MADE_UP';
  assert.throws(() => requireMatchDetail(bad), invalidResponse);
  assert.throws(
    () =>
      requireMatchPage({
        items: [{ rank: 1, summary: { ...current.summary, recommendationScore: '70' } }],
      }),
    invalidResponse
  );
});
