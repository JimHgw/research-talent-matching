import { invalidApiResponse } from './errors.js';
import {
  arrayOf,
  isObject,
  nullable,
  numberBetween,
  objectOf,
  oneOf,
  optional,
  revision,
  string,
  type Validated,
} from './contract-validation.ts';

const score = nullable(numberBetween(0, 100));
const similarity = numberBetween(-1, 1);
const availability = oneOf('AVAILABLE', 'MISSING_EVIDENCE', 'UNAVAILABLE');
const relevance = oneOf('RELEVANT', 'PARTIAL', 'UNRELATED', 'UNKNOWN');

const isMatchSummary = objectOf({
  score,
  unknownWeightPercent: score,
  requiredGapCount: revision,
  evaluationStatus: oneOf('EVALUATED', 'INSUFFICIENT_CRITERIA'),
  algorithmVersion: oneOf(
    'tag-coverage-v1',
    'skill-title-interest-tags-v2',
    'academic-evidence-v3'
  ),
  recommendationScore: optional(score),
  rankingAlgorithmVersion: optional(oneOf('hybrid-interest-v1', 'requirement-semantic-v1')),
  semanticInterest: optional(
    objectOf({
      status: availability,
      similarity: nullable(similarity),
      score,
      relevance,
      weight: numberBetween(0, 1),
      modelVersion: oneOf('minilm-interest-onnx-v1', 'multilingual-minilm-requirements-onnx-v1'),
    })
  ),
  semanticRequirements: optional(
    objectOf({
      status: availability,
      totalWeight: revision,
      modelVersion: oneOf('multilingual-minilm-requirements-onnx-v1'),
    })
  ),
});
export type MatchSummary = Validated<typeof isMatchSummary>;

const isRequirementScoring = objectOf({
  score: numberBetween(0, 100),
  weight: oneOf(1, 2),
  contribution: numberBetween(0, 100),
  method: oneOf(
    'EXACT',
    'SEMANTIC',
    'STRUCTURED',
    'EXPLICIT_GAP',
    'MISSING_EVIDENCE',
    'UNAVAILABLE'
  ),
  similarity: nullable(similarity),
  relevance,
  matches: arrayOf(
    objectOf({
      field: oneOf(
        'skills',
        'researchInterests',
        'researchInterestText',
        'customInterestTags',
        'education',
        'researchExperience',
        'researchOutputs'
      ),
      recordId: nullable(string),
      text: string,
      criterion: string,
      similarity,
    })
  ),
});
export type RequirementScoring = Validated<typeof isRequirementScoring>;

export function requireMatchPage(value: unknown) {
  if (
    !isObject(value) ||
    !Array.isArray(value.items) ||
    !value.items.every(
      (item: unknown) =>
        isObject(item) &&
        isMatchSummary(item.summary) &&
        (item.rank === undefined || (revision(item.rank) && item.rank > 0))
    )
  ) {
    throw invalidApiResponse();
  }
  return value;
}

export function requireMatchDetail(value: unknown) {
  if (
    !isObject(value) ||
    !isMatchSummary(value.summary) ||
    !arrayOf(objectOf({ scoring: optional(isRequirementScoring) }))(value.requirements)
  ) {
    throw invalidApiResponse();
  }
  return value;
}

export function usesRequirementRanking(summary: MatchSummary) {
  return (
    summary.rankingAlgorithmVersion === 'requirement-semantic-v1' || !!summary.semanticRequirements
  );
}

export function primaryMatchScore(summary: MatchSummary) {
  if (usesRequirementRanking(summary)) {
    return {
      label: 'Weighted score / 100',
      name: 'Recommendation score',
      value: summary.recommendationScore ?? null,
    };
  }
  if (
    summary.rankingAlgorithmVersion === 'hybrid-interest-v1' ||
    summary.semanticInterest ||
    summary.recommendationScore !== undefined
  ) {
    return {
      label: 'ranking / 100',
      name: 'Recommendation score',
      value: summary.recommendationScore ?? null,
    };
  }
  return { label: 'coverage / 100', name: 'Evidence coverage', value: summary.score };
}
