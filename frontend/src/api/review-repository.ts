import { api } from './client.js';
import { isObject } from './contract-validation.ts';
import { invalidApiResponse } from './errors.js';
import {
  isExtraction,
  isOwnerProfile,
  type ApplyExtractionRequest,
  type Extraction,
  type OwnerProfile,
} from './review-contract.ts';

type ReadOptions = { signal?: AbortSignal };

export interface ReviewRepository {
  extraction(documentId: string, options: ReadOptions): Promise<Extraction>;
  profile(options: ReadOptions): Promise<OwnerProfile>;
  apply(documentId: string, input: ApplyExtractionRequest): Promise<OwnerProfile>;
}

type ReviewTransport = {
  extraction(documentId: string, options: ReadOptions): Promise<unknown>;
  profile(options: ReadOptions): Promise<unknown>;
  apply(
    documentId: string,
    revision: number,
    sections: ApplyExtractionRequest['sections']
  ): Promise<unknown>;
};

export function createReviewRepository(transport: ReviewTransport): ReviewRepository {
  return {
    async extraction(documentId, options) {
      const result = await transport.extraction(documentId, options);
      if (isObject(result) && (result.documentId !== documentId || result.status !== 'READY'))
        throw mismatchedExtraction();
      if (!isExtraction(result)) throw invalidApiResponse();
      return result;
    },
    async profile(options) {
      const profile = await transport.profile(options);
      if (!isOwnerProfile(profile)) throw invalidApiResponse();
      return profile;
    },
    async apply(documentId, { expectedProfileRevision, sections }) {
      const profile = await transport.apply(documentId, expectedProfileRevision, sections);
      if (!isOwnerProfile(profile)) throw invalidApiResponse();
      return profile;
    },
  };
}

export function mismatchedExtraction() {
  return invalidApiResponse(
    'The review result did not match this document or its ready state. Refresh its status before reviewing.'
  );
}

export const reviewRepository = createReviewRepository(api);
