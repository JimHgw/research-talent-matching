import {
  arrayOf,
  dateTime,
  id,
  isObject,
  nullable,
  objectOf,
  oneOf,
  optional,
  revision,
  string,
  type Validated,
} from './contract-validation.ts';

const year = nullable(
  (value: unknown): value is number => revision(value) && value >= 1900 && value <= 2200
);
const personalTagFields = { label: string, description: optional(string) };
const personalTagInput = objectOf({ ...personalTagFields, id: optional(id) });
const sectionFields = {
  education: arrayOf(
    objectOf({
      id,
      institution: string,
      qualification: string,
      discipline: string,
      startYear: year,
      endYear: year,
    })
  ),
  courses: arrayOf(objectOf({ id, name: string, code: nullable(string), description: string })),
  researchExperience: arrayOf(
    objectOf({ id, title: string, organisation: string, description: string })
  ),
  skills: arrayOf(objectOf({ id, title: string, evidenceText: string })),
  researchInterests: arrayOf(id),
  researchOutputs: arrayOf(
    objectOf({
      id,
      title: string,
      type: oneOf('PUBLICATION', 'PROJECT', 'OTHER'),
      url: nullable(string),
      description: string,
    })
  ),
  researchInterestText: string,
  customInterestTags: arrayOf(personalTagInput),
  resumeDescription: string,
};

const section = (value: unknown): value is keyof typeof sectionFields =>
  string(value) && Object.hasOwn(sectionFields, value);
const sectionValues = objectOf(sectionFields);
export type ReviewedSections = Partial<Validated<typeof sectionValues>>;

export function isReviewedSections(value: unknown): value is ReviewedSections {
  return (
    isObject(value) &&
    Object.entries(value).every(([key, item]) => section(key) && sectionFields[key](item))
  );
}

export type ApplyExtractionRequest = {
  expectedProfileRevision: number;
  sections: ReviewedSections;
};

export const isExtraction = objectOf({
  documentId: id,
  status: oneOf('READY'),
  suggestedSections: isReviewedSections,
  warnings: arrayOf(string),
  uncertainFields: arrayOf(
    objectOf({ field: section, status: oneOf('UNKNOWN', 'NOT_RECOGNISED'), reason: string })
  ),
  reviewRequired: oneOf(true),
});
export type Extraction = Validated<typeof isExtraction>;

const isConfirmation = objectOf({
  status: oneOf('UNCONFIRMED', 'CONFIRMED'),
  confirmedRevision: nullable(revision),
  confirmedAt: nullable(dateTime),
});
export type Confirmation = Validated<typeof isConfirmation>;

const isProfileShape = objectOf({
  talentId: id,
  revision,
  confirmation: isConfirmation,
  content: objectOf({
    ...sectionFields,
    displayName: string,
    disciplineGroup: nullable(oneOf('STEM', 'BUSINESS')),
    researchInterestText: optional(string),
    customInterestTags: optional(arrayOf(objectOf({ ...personalTagFields, id }))),
    resumeDescription: optional(string),
  }),
  origins: arrayOf(
    objectOf({
      field: section,
      sourceType: oneOf('MANUAL', 'USER_REVIEWED_DOCUMENT'),
      documentId: nullable(id),
    })
  ),
  updatedAt: dateTime,
});
export type OwnerProfile = Validated<typeof isProfileShape>;

export function isOwnerProfile(value: unknown): value is OwnerProfile {
  if (!isProfileShape(value)) return false;
  const { status, confirmedRevision, confirmedAt } = value.confirmation;
  return status === 'CONFIRMED'
    ? confirmedRevision !== null && confirmedRevision <= value.revision && confirmedAt !== null
    : confirmedRevision === null && confirmedAt === null;
}
