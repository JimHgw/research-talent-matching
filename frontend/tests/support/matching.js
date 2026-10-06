// Test double only. Never import this module from application code.
import { tags } from './seed.js';

export function isConfirmed(profile) {
  return (
    profile.confirmation.status === 'CONFIRMED' &&
    profile.confirmation.confirmedRevision === profile.revision
  );
}

export function visibleProfile(profile, privacy) {
  return {
    talentId: profile.talentId,
    fields: Object.fromEntries(
      privacy.visibleFields.map((key) => [key, structuredClone(profile.content[key])])
    ),
  };
}

// This deterministic baseline simulates the agreed Python service in demo mode.
export function evaluate(opportunity, profile, allowedFields = null) {
  const owner = allowedFields === null;
  const content = owner
    ? profile.content
    : Object.fromEntries(allowedFields.map((key) => [key, profile.content[key]]));
  const requirements = opportunity.content.requirements.map((requirement) => {
    const field = requirement.kind === 'SKILL' ? 'skills' : 'researchInterests';
    const claims = requirement.tagIds.map((id) =>
      requirement.kind === 'SKILL'
        ? content.skills?.find((s) => s.tagId === id)
        : content.researchInterests?.includes(id)
          ? { tagId: id, claim: 'HAS', evidenceText: '' }
          : undefined
    );
    const negative = claims.filter((c) => c?.claim === 'DOES_NOT_HAVE');
    const positive = claims.filter((c) => c?.claim === 'HAS');
    const status = negative.length
      ? 'GAP'
      : positive.length === claims.length
        ? 'MATCHED'
        : positive.length
          ? 'PARTIAL'
          : 'UNKNOWN';
    const reasonCode = {
      GAP: 'EXPLICIT_NEGATIVE_CLAIM',
      MATCHED: 'ALL_TAGS_SUPPORTED',
      PARTIAL: 'SOME_TAGS_SUPPORTED',
      UNKNOWN: 'INSUFFICIENT_EVIDENCE',
    }[status];
    const reason = {
      GAP: 'The profile explicitly reports not having a requested skill.',
      MATCHED: 'Confirmed claims support every tag in this requirement.',
      PARTIAL: 'Some requested tags are supported; the remaining tags have insufficient evidence.',
      UNKNOWN: `There is insufficient ${owner ? 'confirmed' : 'shared'} evidence for this requirement.`,
    }[status];
    const origin = profile.origins.find((o) => o.field === field) || {
      sourceType: 'MANUAL',
      documentId: null,
    };
    const evidence = (negative.length ? negative : positive).map((c) => {
      const label = tags.find((t) => t.id === c.tagId)?.label || c.tagId;
      const value = {
        field,
        recordId: c.tagId,
        valueSummary:
          c.evidenceText || `User confirmed ${c.claim === 'HAS' ? '' : 'not having '}${label}.`,
      };
      return owner
        ? {
            ...value,
            confirmedRevision: profile.revision,
            sourceType: origin.sourceType,
            documentId: origin.documentId,
          }
        : value;
    });
    return { requirement, status, reasonCode, reason, evidence };
  });
  let total = 0,
    covered = 0,
    unknown = 0;
  for (const result of requirements) {
    const weight = result.requirement.importance === 'REQUIRED' ? 2 : 1;
    total += weight;
    covered += weight * { MATCHED: 1, PARTIAL: 0.5, GAP: 0, UNKNOWN: 0 }[result.status];
    if (result.status === 'UNKNOWN') unknown += weight;
  }
  return {
    requirements,
    summary: {
      score: total ? Math.round((10000 * covered) / total) / 100 : null,
      unknownWeightPercent: total ? Math.round((10000 * unknown) / total) / 100 : null,
      requiredGapCount: requirements.filter(
        (r) => r.status === 'GAP' && r.requirement.importance === 'REQUIRED'
      ).length,
      evaluationStatus: total ? 'EVALUATED' : 'INSUFFICIENT_CRITERIA',
      algorithmVersion: 'tag-coverage-v1',
    },
  };
}

export function rank(items, idFor) {
  return items
    .sort(
      (a, b) =>
        (b.summary.score ?? -1) - (a.summary.score ?? -1) ||
        (a.summary.unknownWeightPercent ?? 101) - (b.summary.unknownWeightPercent ?? 101) ||
        idFor(a).localeCompare(idFor(b))
    )
    .map((item, index) => ({ rank: index + 1, ...item }));
}
