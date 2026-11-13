import { ApiError, invalidApiResponse } from '../../api/errors.js';
import { mismatchedExtraction, type ReviewRepository } from '../../api/review-repository.ts';
import {
  isReviewedSections,
  type Extraction,
  type OwnerProfile,
  type ReviewedSections,
} from '../../api/review-contract.ts';

export type LoadedReview = {
  extraction: Extraction;
  profile: OwnerProfile;
};

export async function loadExtractionReview(
  repository: ReviewRepository,
  documentId: string,
  { signal }: { signal?: AbortSignal } = {}
): Promise<LoadedReview> {
  const [extraction, profile] = await Promise.all([
    repository.extraction(documentId, { signal }),
    repository.profile({ signal }),
  ]);
  signal?.throwIfAborted();
  if (extraction.documentId !== documentId || extraction.status !== 'READY') {
    throw mismatchedExtraction();
  }
  return { extraction, profile };
}

export async function applyReviewedExtraction(
  repository: ReviewRepository,
  review: LoadedReview,
  draft: ReviewedSections,
  selected: string[]
): Promise<OwnerProfile> {
  const entries = Object.entries(draft).filter(([key]) => selected.includes(key));
  const sections = Object.fromEntries(entries);
  if (!entries.length || !isReviewedSections(sections)) {
    throw new ApiError(422, {
      error: { code: 'VALIDATION_ERROR', message: 'The request could not be completed.' },
    });
  }
  const profile = await repository.apply(review.extraction.documentId, {
    expectedProfileRevision: review.profile.revision,
    sections,
  });
  if (
    profile.talentId !== review.profile.talentId ||
    profile.revision !== review.profile.revision + 1 ||
    profile.confirmation.status !== 'UNCONFIRMED'
  ) {
    throw invalidApiResponse();
  }
  return profile;
}
