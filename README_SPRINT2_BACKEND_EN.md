# COMP3900 / COMP9900 — H18ABANANA

**🍌 Explainable Two-Sided Research Matching · Sprint 2 Backend Developer Specification**

Prepared: **2026-10-22**. Updated: **2026-10-23**. Document version: **`0.2.4-draft`**.

This README follows the structure of the [Sprint 1 developer README](README_DEVELOPER_EN.md) and gives the Python backend team a Sprint 2 implementation and acceptance guide. Continue using **Flask, MySQL 8.4, PyMySQL and SQLAlchemy**, the existing document worker and the `/api/v1` API.

**API scope: no new HTTP endpoints.** Sprint 2 reuses existing method/path combinations, extending their fields, query parameters, validation and business logic where needed. Explicit reopening uses the existing opportunity update endpoint. Evaluation and test-data preparation use local tooling, not additional public APIs.

> **Document status:** Jira requirements and backend subtasks were read on 22 October 2026. The initial backend baseline refers to `f064daa`; the frontend responsibility review uses the updated README and shared integration tests at `883f554`. This is a development specification, not a completion or test report. Items labelled **proposed** are integration decisions for review, not already implemented endpoints or Jira-mandated field names. The document version does not change the running API or the checked-in OpenAPI version.

**Additional user-requested scope, 2026-10-23:** support research-interest free text alongside existing shared tags and user-created personal interest tags. This is a recorded product decision, not a claim that Jira already specifies these fields or that existing frontend tasks implement them. Section 2.2.4 defines the behaviour; field names and limits remain proposed integration details.

**US-11 implementation scope clarified by the user, 2026-10-23:** complete backend resume extraction, returning tags and per-section free text plus an additional unified `resumeDescription`. Section 2.4.2 and the linked implementation guide describe this delivery. Historical sprint/Jira estimates are retained.

## Contents

[[_TOC_]]

## Change Log

- **2026-10-23:** Added free-text research interests and personal custom interest tags, including extraction/review, atomic saves through existing endpoints, visibility, semantic inputs, frontend coordination and acceptance cases.
- **2026-10-23:** Clarified US-13: implementing and running an embedding-based semantic matching experiment is mandatory; adopting it in the application recommendation flow depends on measured results. Defined tag baseline/filter/fallback roles and executable delivery evidence.
- **2026-10-22:** Aligned responsibilities with the updated frontend task 49/41/61 documentation. Reuse its UI workflows and shared integration tests; backend owns server guarantees and contributes evidence to QA's shared workflow report.
- **2026-10-22:** Confirmed the no-new-endpoints constraint. Explicit reopening is an optional, deliberate operation within the existing opportunity update request.
- **2026-10-22:** Created the Sprint 2 backend guide from all 12 sprint work items and their 12 backend subtasks. Added scope, existing-code gaps, data and API proposals, permissions, evaluation methods, integration cases and delivery requirements.

## 🫡 0. Aims — Sprint Goals

1. Enforce current-profile confirmation, explicit discovery consent, field visibility and private original-document access across every relevant API.
2. Support authorised combined search, optional opportunity source URLs, deadlines, automatic expiry and explicit reopening.
3. Explain research-team recommendations using specific permitted, confirmed profile evidence, including supported education, experience and research-output evidence.
4. Verify registration, user-ID login and independent sessions, and provide stable API codes for interface localisation.
5. Verify the server side of the existing document-review flow, fix only demonstrated backend defects and record regression evidence, including an explicit not-reproduced outcome where appropriate.
6. Implement and run embedding-based research-interest matching, compare it with the structured baseline on versioned labelled inputs and record the adoption decision. Deliver extraction/matching quality results and contribute backend evidence to QA-1's shared end-to-end report.
7. Preserve free-text research interests alongside shared and personal custom tags, with user review, explicit confirmation and consistent privacy throughout extraction, storage and matching.

## 🌈 1. Overview — Project and Scope

### 1.1 Sources and How to Use This Document

| Source | Purpose |
|---|---|
| [Jira backlog](https://unsw-comp3900-comp9900-26t3.atlassian.net/jira/software/projects/H18ABANANA/boards/103/backlog) and the supplied screenshot | Sprint membership, displayed dates and parent estimates |
| Jira parent descriptions and backend subtasks linked in section 2.1 | Required behaviour, acceptance criteria, dependencies and scope boundaries; read live on 2026-10-22 |
| User's follow-up decisions on 2026-10-23 | Free-text interests plus shared/custom tags; create personal tags during existing profile/review saves, with no new endpoints |
| [Sprint 1 developer README](README_DEVELOPER_EN.md) | Document structure and existing development conventions |
| [Frontend README: Sprint 2 task 49](frontend/README.md#sprint-2-account-and-language-module-task-49), [task 41](frontend/README.md#sprint-2-profile-and-privacy-safeguards-task-41) and [task 61](frontend/README.md#sprint-2-document-review-recovery-task-61) at `883f554` | Updated UI responsibilities and reusable integration coverage; this review does not rerun or certify their tests |
| [Sprint 1 API contract](docs/api/sprint-1-api-contract.md), [OpenAPI](docs/api/openapi.json), [endpoint index](docs/api/endpoint-index.json), [examples](docs/api/examples/index.json) | Current request/response baseline; unchanged operations retain their existing contract |
| [Backend README](backend/README.md), [document guide](docs/us09-documents.md), [MySQL migration guide](docs/mysql-migration.md) | Existing setup, worker, persistence and migration procedures |
| Local source and tests at `f064daa` | Evidence of existing implementation and specific gaps; source inspection does not prove runtime acceptance |

Read section 2.1 for task ownership boundaries, then sections 2.2–2.7 for implementation rules. Before integrating any proposed schema change, update the shared contract, OpenAPI, example index/fixtures and corresponding FE/BE tests together. `backend/src/shared/validation.py` validates requests against the checked-in OpenAPI, so adding a field only to Python or the UI is insufficient.

The original meeting notes referenced by Jira were not available in this checkout. This README does not invent meeting-approved sample counts, numerical quality targets, additional languages or submission dates.

### 1.2 Sprint 2 Boundaries

The supplied board shows **21–29 October 2026**, **12 parent work items** and **53 Story Points**. These are sprint planning details, not demonstration dates or grading weights. Backend subtasks retain their parent's estimate; do not count the points twice. The backend subtasks were unassigned when read; parent assignees are not backend assignments.

- **In scope:** US-10, US-11, US-13, US-14, US-15, US-16, US-18, US-19, US-20, US-21, BUG-35 and DATA-40.
- **US-13 requires a runnable semantic matching implementation and an executed comparison.** BE-46 must implement embedding-based research-interest similarity and evaluate it against the structured baseline. Only adoption in the application's recommendation flow is conditional on the findings. Keeping tag matching alone, writing a proposal or supplying a report without running the semantic approach does not complete US-13. Preserve the structured baseline for comparison and application fallback.
- **Additional interest-entry scope:** allow free text, shared interest tags and personal custom interest tags independently or together. Custom creation covers research interests only; it does not introduce custom skill tags, a global tag-management workflow or automatic public vocabulary expansion. Record the extra implementation work with the relevant FE/BE tasks without presenting it as an original Jira acceptance criterion or changing the historical estimate above.
- **US-19 stores a source link:** no automatic fetching, scraping, import or confirmation of Google, LinkedIn or university page content.
- **US-20 is proposed product scope derived from tutor questions:** implement the currently planned expiry/reopening behaviour, preserving records. Do not describe it as an explicitly confirmed client requirement or add permanent deletion.
- **US-15 preserves authorised roles:** no new multi-role account model or role-granting API is required.
- **US-21 concerns interface language:** Jira proposes English and Simplified Chinese initially. The local frontend already contains a broader language catalogue; that does not introduce a backend translation service, translation of user content or a language column in the database.
- **US-12 favourites is not in this sprint's 12-item scope.** Existing collection functionality must remain compatible, but its presence does not add another Sprint 2 story. US-17 is also not listed in this sprint.

### 1.3 Existing Baseline and Work Still Required

| Area | Present in the inspected checkout | Sprint 2 backend work |
|---|---|---|
| Accounts | Verified-email registration, both roles, email/ID login, sessions, logout and password reset | Audit atomicity, returned ID/role, cross-account isolation and permission failures |
| Confirmation/privacy | Whole-profile revisions, confirmation, opt-in, visible-field filtering and owner-only documents | Harden all new search/evidence paths and prove revocation and persistence |
| Research-interest input | Profile interests contain shared tag IDs only; document suggestions require recognised tag labels | Add optional text and personal tags, preserve unmatched interest text for review and migrate existing profiles compatibly |
| Documents | PDF/DOCX upload, worker, extraction state, review result and selected-section import; frontend task 61 now documents recovery and regression coverage | Reuse the existing reproduction/tests; audit server results, record not-reproduced outcomes and correct only demonstrated backend defects |
| Opportunities | Draft/create/edit/publish/list/detail and revision checks | Add optional source URL, deadline, type/filter support and explicit reopening with migrations |
| Matching | `tag-coverage-v1`, four statuses and per-requirement evidence based on skills/interests | Implement and evaluate embedding-based interest matching under BE-46; extend grounded education/experience/output evidence under BE-54; preserve permissions |
| Search | Opportunity routes currently consume `scope`, `page`, `pageSize`; matching routes consume pagination | Define, validate and apply combined filters before ranking/pagination |
| Evaluation | [US-06 synthetic matching evaluation](docs/testing/us06-evaluation.md) and existing tests | Implement US-11 extraction regression coverage and US-13 independent relevance labels/reports; old test results are not Sprint 2 results |
| Localisation | Frontend language catalogue; backend error codes, field paths and English messages | Fill any code/mapping gaps while preserving domain values and API compatibility |

The current opportunity model has no `sourceUrl`, deadline or opportunity-type field. Its persisted status is `DRAFT` or `PUBLISHED`. Requirement kinds are currently only `SKILL` and `INTEREST`. These are concrete schema gaps, not merely missing frontend labels.

### 1.4 Frontend Ownership and Shared Coverage

The same user story appears in both READMEs because it crosses the UI/API boundary. It is not a second implementation assignment. The updated frontend README explicitly documents tasks 49, 41 and 61; it is not a completion report for every Sprint 2 frontend task.

| Work | Frontend / QA responsibility to reuse | Backend responsibility retained here |
|---|---|---|
| FE-49 with BE-50: accounts | Password visibility, account-ID display, account details, switch-account controls, unsaved/pending guards and stale-workspace cleanup | Registration atomicity, stable returned ID/role, authenticated ownership, independent server sessions and session revocation |
| FE-49 with BE-60: language | Language selector, `banana.language` storage, dictionaries, translated UI/error display, fallback and layout/direction; each FE module owns its page copy | Preserve machine-readable codes/field paths and domain values; add a missing API code only when an agreed frontend case needs it. No second language framework or translation workstream |
| FE-41 with BE-42: confirmation/privacy | Focus/explicit refresh, draft preservation, stale-confirmation recovery, saved-state display and removal of stale UI results/dialogs | Current-confirmed-revision checks, opt-in/visible-field enforcement, private-document access and checks for new search/evidence paths; existing passing behaviour may need only audit evidence |
| FE-61 with BE-62: document review | Selected-document binding, review editor, acknowledgement, discard/pending guards, recovery actions and manual-entry navigation | Owned-document API responses, worker state, atomic import/revision handling and private storage; fix only an identified server failure |
| QA-51 with BE-52/64: test evidence | Browser acceptance, shared scenario/label review, UI observations, consolidated workflow defects and retests | Reusable fixtures/seed-restore tooling, API/database/worker checks and backend result sections in the same workflow report |
| Additional interest-entry scope (2026-10-23) | Profile text input, select/create-tag control and review/edit/remove interactions in existing screens | Text/tag persistence, normalisation, ownership, extraction suggestions, atomic import, confirmation/privacy and matching inputs |

**BUG-35 status:** frontend task 61 states that the original `not-recording` message has not reproduced in the current supported PDF/Word flow and its cause remains unverified. It documents recovery improvements and successful/failure-path test coverage. BE-62 must not assume an unresolved server defect or reimplement `DocumentsPage`, `ExtractionReview` or `ReviewRecovery`; reproduce the sequence through existing tests, record the actual outcome and investigate only evidenced server failures. Do not claim the original cause is fixed solely because the flow passes.

**Reuse existing tests:** `backend/tests/test_frontend_integration.py` already includes task `41` and `49` and registration cases. `backend/tests/test_us09_frontend_integration.py` already exercises PDF/DOCX review with the real worker and task `61` state/account cases. Their UI drivers are under `frontend/tests/`. A Python test harness in `backend/tests/` does not make its UI scenario a new backend-owned feature. BE-42/50/52/62 should run/link these cases and add only missing server assertions or coverage for new behaviour, rather than copying the same workflows and fixtures into another suite.

BE-44 owns the clarified resume tag/free-text extraction and reviewed-import implementation; BE-46 owns the runnable semantic implementation and its executed comparison. These are distinct from browser workflow testing. BE-64 packages the shared examples and independently reviewed labels for repeatable use instead of creating a competing dataset. Shared acceptance requirements below provide integration context and do not transfer frontend implementation to the backend team.

The added interest controls are new coordination work, not covered merely because FE-41/61 previously passed. Proposed coordination is BE-42 for profile/privacy, BE-62 for extraction/import and BE-46 for semantic inputs, with the owners of the existing profile and document-review UI. Keep this feature separate from investigation of BUG-35; no Jira assignment or completion status is changed by this README.

## 🐶 2. Sprint 2 — Backend Functionality and Tests

### 2.1 Task — Sprint Requirements

| Story / task | Jira parent | Points | Backend subtask | Required backend outcome |
|---|---|---:|---|---|
| US-10 Confirmation and document privacy | [H18ABANANA-3](https://unsw-comp3900-comp9900-26t3.atlassian.net/browse/H18ABANANA-3) | 3 | [BE-42](https://unsw-comp3900-comp9900-26t3.atlassian.net/browse/H18ABANANA-42) | Use the current confirmed revision; enforce opt-in, permitted fields and owner-only originals on list/detail/direct requests |
| US-11 Resume tags and free-text extraction (clarified scope) | [H18ABANANA-4](https://unsw-comp3900-comp9900-26t3.atlassian.net/browse/H18ABANANA-4) | 5 | [BE-44](https://unsw-comp3900-comp9900-26t3.atlassian.net/browse/H18ABANANA-44) | Implemented resume tags, source-grounded section text, unified description and atomic reviewed import with persistence/privacy |
| US-13 Semantic interest matching evaluation | [H18ABANANA-6](https://unsw-comp3900-comp9900-26t3.atlassian.net/browse/H18ABANANA-6) | 8 | [BE-46](https://unsw-comp3900-comp9900-26t3.atlassian.net/browse/H18ABANANA-46) | Implement and run embedding-based interest matching; compare actual outputs with the tag baseline on identical labelled examples; record costs, errors, application adoption/omission decision and fallback |
| US-14 Search and combined filters | [H18ABANANA-7](https://unsw-comp3900-comp9900-26t3.atlassian.net/browse/H18ABANANA-7) | 5 | [BE-48](https://unsw-comp3900-comp9900-26t3.atlassian.net/browse/H18ABANANA-48) | Authorised opportunity/talent filters with correct totals, ranks, expiry and privacy |
| US-15 Registration, login and role switching | [H18ABANANA-8](https://unsw-comp3900-comp9900-26t3.atlassian.net/browse/H18ABANANA-8) | 5 | [BE-50](https://unsw-comp3900-comp9900-26t3.atlassian.net/browse/H18ABANANA-50) | Stable ID and authoritative role, atomic registration, ID re-login and independent sessions |
| US-16 End-to-end workflows and defects | [H18ABANANA-17](https://unsw-comp3900-comp9900-26t3.atlassian.net/browse/H18ABANANA-17) | 5 | [BE-52](https://unsw-comp3900-comp9900-26t3.atlassian.net/browse/H18ABANANA-52) | Real API/database/worker regression evidence, failures, retests and limitations |
| US-18 Explain recommended talent | [H18ABANANA-36](https://unsw-comp3900-comp9900-26t3.atlassian.net/browse/H18ABANANA-36) | 5 | [BE-54](https://unsw-comp3900-comp9900-26t3.atlassian.net/browse/H18ABANANA-54) | Map individual requirements to confirmed shareable records, with statuses, reasons and available scores |
| US-19 Opportunity source URLs | [H18ABANANA-37](https://unsw-comp3900-comp9900-26t3.atlassian.net/browse/H18ABANANA-37) | 3 | [BE-56](https://unsw-comp3900-comp9900-26t3.atlassian.net/browse/H18ABANANA-56) | Owner-controlled optional HTTP/HTTPS URL, validation and add/edit/remove/reload persistence |
| US-20 Deadlines and expiry | [H18ABANANA-38](https://unsw-comp3900-comp9900-26t3.atlassian.net/browse/H18ABANANA-38) | 3 | [BE-58](https://unsw-comp3900-comp9900-26t3.atlassian.net/browse/H18ABANANA-58) | One time rule, automatic exclusion, labelled expired details and explicit authorised reopening |
| US-21 Interface language | [H18ABANANA-39](https://unsw-comp3900-comp9900-26t3.atlassian.net/browse/H18ABANANA-39) | 3 | [BE-60](https://unsw-comp3900-comp9900-26t3.atlassian.net/browse/H18ABANANA-60) | Stable errors/status/reason codes and field identifiers, readable fallbacks, unchanged domain data |
| BUG-35 Review Suggestion “not-recording” | [H18ABANANA-35](https://unsw-comp3900-comp9900-26t3.atlassian.net/browse/H18ABANANA-35) | 8 | [BE-62](https://unsw-comp3900-comp9900-26t3.atlassian.net/browse/H18ABANANA-62) | Trace document ownership/state/import, fix verified server defects and supply regression evidence |
| DATA-40 Prepare realistic inputs | [H18ABANANA-40](https://unsw-comp3900-comp9900-26t3.atlassian.net/browse/H18ABANANA-40) | 0 | [BE-64](https://unsw-comp3900-comp9900-26t3.atlassian.net/browse/H18ABANANA-64) | Versioned provenance/labels/start state and isolated repeatable seed/restore procedures |
| **Total** | **12 parent work items** | **53** | **12 backend subtasks** | **Implementation, evaluation and verifiable integration evidence** |

US-18's title mentions US-04, but its description explicitly concerns **research-team-to-talent recommendations**, extending US-05 and the requirement-level evidence work in US-04/US-08. Do not implement it solely on talent-to-opportunity pages.

### 2.2 Storing Data — Structures and States

#### 2.2.1 Existing Invariants to Preserve

| Object | Required behaviour |
|---|---|
| Talent profile | New profile is revision 0 and `UNCONFIRMED`; matching requires `confirmation_status == CONFIRMED` and `confirmed_revision == revision` |
| Confirmation | Retain Sprint 1 whole-profile confirmation. A real edit invalidates the entire current revision; reconfirm explicitly. Jira does not require new field-level confirmation storage |
| Privacy | New settings are `discoverable=false`, `visibleFields=[]`; privacy has its own revision. Privacy changes do not invalidate profile confirmation |
| Document | `QUEUED → PROCESSING → READY / FAILED`; READY means extraction finished, not profile approval. Original files and extraction results remain owner-only |
| Reviewed import | Save selected components and their documented shared-tag resolutions (2.2.4); preserve other omitted content. Empty arrays clear lists and `""` clears interest text. Every successful import increments the profile revision and clears confirmation |
| Opportunity | Preserve ownership, stable requirement IDs, ordered records, revision checks and valid publication prerequisites |
| Ordinary save | Check the expected revision inside the write transaction. Stale writes return 409; ordinary no-op writes preserve revision |
| Account/session | User ID and stored role determine access. A user-supplied ID or role never replaces authenticated ownership |

#### 2.2.2 Proposed Sprint 2 Opportunity Fields

These names and storage choices are **proposed**, to be agreed with FE before implementation. Add fields to existing opportunity models rather than creating a separate Sprint 2 opportunity store.

| API field / location | Proposed storage | Meaning and compatibility |
|---|---|---|
| `content.sourceUrl` | `source_url`, nullable text | Optional absolute HTTP/HTTPS URL; `null` removes it. Proposed limit: 2,048 characters |
| `content.deadlineAt` | `deadline_at`, nullable `UTCDateTime` | Offset-aware RFC3339 input, normalised to UTC; no deadline is `null` |
| `content.opportunityType` | `opportunity_type`, nullable string | Controlled type code. Proposed vocabulary: `PHD`, `MASTERS`, `RESEARCH_ASSISTANT`, `POSTDOC`, `OTHER`; the team must ratify the vocabulary before FE/BE integration |
| `availabilityStatus` on the returned opportunity | Derived response value | Proposed `DRAFT`, `ACTIVE`, `EXPIRED`; retain the existing persisted `status` field for publication state |
| Internal expiry marker | `expired_at`, nullable `UTCDateTime` | Retains an expired/closed state when an owner edits the deadline; cleared only by explicit reopening. Never treat this field as client-writable |

**Backward-compatible writes:** keep existing required content fields and full-replacement semantics. On create, omitted new optional fields default to `null`. On update, omitted new optional fields preserve their stored values; explicit `null` clears them. Document this limited compatibility exception so older clients cannot accidentally erase a newly stored source URL or deadline. Responses include the new nullable fields after the coordinated contract update. Update strict response validators and frontend consumers at the same time.

**Deadline semantics:** capture one server UTC time for each operation. A published opportunity is active only when it has no retained expiry marker and either `deadlineAt == null` or `now < deadlineAt`. At `now == deadlineAt` it is expired. Drafts never become active through a deadline change. An expired opportunity remains readable, with an expired label, to users already entitled to its published details; drafts remain owner-only.

The proposed expiry marker prevents this incorrect sequence: deadline passes → owner edits deadline into the future → opportunity silently becomes active. Before saving edits, atomically check the **old** deadline against the same server time and retain expiry if it has already occurred, even if no scheduler has visited the record. Saving a future/no deadline alone must not reopen it. An explicit `reopen: true` in the existing update request clears the marker only after ownership, revision, publication, requirements and deadline validation succeed. Updating the deadline and explicitly reopening may happen in the same transaction; no separate endpoint or preliminary save is required.

Reads must enforce the time predicate even if a worker or scheduled task has not updated the marker. A background expiry sweep is optional; availability must not depend on its timing. Do not permanently delete expired records.

#### 2.2.3 Evidence Models and Migrations

The existing `TeamEvidence` shape is `{field, recordId, valueSummary}`. It can identify education, research-experience and research-output records without disclosing a document ID, storage path or private provenance. The current matching implementation still needs explicit mappings from supported requirements to those records; expanding displayed evidence fields alone does not complete US-18.

- Preserve existing `SKILL`/`INTEREST` requirements and old records. Define any new requirement kinds, structured criteria, supported comparisons and validation rules with FE before extending `OpportunityRequirement` and its database constraints.
- Reuse stable profile record IDs. Generate evidence from the permitted current structured record, never from arbitrary generated text or an original-file URL.
- Use MySQL migrations for new columns, indexes and changed constraints. `init-db`/`create_all()` only creates missing tables; it does not alter existing tables.
- Backfill existing opportunities with no source URL, no deadline, no type and no expiry marker. Existing published opportunities therefore remain active.
- Test both a fresh database and an upgrade containing accounts, privacy settings, published opportunities and documents. Record migration order, verification and rollback/restore instructions.
- Use the existing transaction wrapper for revision and lifecycle writes. Slow extraction, embeddings and network/model calls stay outside write transactions. Keep API and worker schema versions compatible.
- Do not add multi-role tables, a translation database or a vector database solely because a Sprint 2 story mentions roles, languages or semantic evaluation.

#### 2.2.4 Research Interests — Free Text, Shared Tags and Personal Tags

Support all three representations together. Text does not need a matching tag, and tags do not require free text. Either representation can be sufficient input for the documented matching method; having neither means missing interest information, not an explicit negative claim.

| Proposed profile field | Shape and role | Compatibility |
|---|---|---|
| `content.researchInterests` | Existing array of shared `INTEREST` tag IDs; classification, explicit filters and structured baseline | Preserve the existing type and IDs; do not mix strings of arbitrary labels or personal IDs into this array |
| `content.researchInterestText` | Optional string describing research directions and context; primary semantic text input | Existing profiles default to `""`; proposed maximum 5,000 characters |
| `content.customInterestTags` | Optional array of personal `{id, label}` records, with server-generated stable IDs | Existing profiles default to `[]`; a new write item omits `id`, while later reads/edits use its returned ID |

**Save and creation rules:**

- Create, edit, remove and associate personal tags within the existing profile PUT or reviewed-document apply transaction. A normal profile PUT still includes the existing full required content and `expectedRevision`; an apply still uses `expectedProfileRevision`. No standalone tag-creation route is added.
- New companion fields are optional on writes: omission preserves their stored values, `""` clears text and `[]` clears personal tags. A supplied personal-tag array replaces that profile's personal selection. The existing `researchInterests` array keeps its current replacement semantics. Do not clear text/personal tags merely because an older client saves shared tags. Update response schemas and strict clients together.
- Normalise labels for exact deduplication using Unicode normalisation, trimming/collapsing whitespace and case-insensitive comparison; retain a readable display label. Proposed limits are 1–100 characters per personal label and at most 100 shared/personal tags combined. Reject blank/oversized entries with field-specific validation errors.
- Resolve against shared `INTEREST` tags first, then only this owner's personal tags. Reuse an exact shared match in `researchInterests`; otherwise reuse/create the owner's personal record. Return the canonical saved profile, including any shared-ID resolution. Do not alter the shared label or search another owner's private tags for duplicates. Similar meaning alone never merges labels automatically.
- For shared-ID resolution, start with the submitted shared-tag array, or the current array when an apply omits it, then add IDs resolved from accepted personal-label proposals. This is the only exception to preserving an omitted shared-tag list; it never removes an existing selection. A supplied empty shared list stays empty unless accepted labels resolve to shared tags. Return and display the resolved saved selection before profile confirmation.
- Ownership and revision checks happen before any creation. Deduplicate repeated submissions and enforce uniqueness on owner plus normalised label, including concurrent saves. A stale/invalid save creates no orphan tags or partial profile updates. Existing personal IDs are usable/editable only by their owner. Renaming/removing a personal tag must not affect another profile or the shared vocabulary.
- A real change to text or either tag collection increments the profile revision and invalidates whole-profile confirmation. Ordinary no-op saves preserve the revision; successful document imports retain their existing revision behaviour. All accepted content must be explicitly confirmed before matching uses it.

**Storage and privacy:** retain the shared `Tag`/`ProfileInterest` model for existing IDs; add owner-scoped personal-tag storage and a text field through migrations. Do not insert private labels into the existing global tag list. Keep source attribution for each imported component so a partial import does not overwrite the provenance of untouched content. Review applicable provenance/schema constraints together with the migration.

Use the existing `researchInterests` visibility setting as one group covering shared tags, text and personal tags; no new privacy control is required. Teams may see/use personal labels only through a currently confirmed, opted-in profile whose interest group is visible. `GET /tags` continues to return the shared vocabulary only. Hidden/unconfirmed personal labels must not appear in public suggestions, facets, counts, search results or evidence. Team responses expose permitted profile content, never original document IDs/paths or private extraction provenance.

**Document extraction and review:**

1. Reuse PDF/DOCX text reading. Preserve the source-grounded research-interest description even when no shared tag matches; do not discard it simply as an unrecognised tag.
2. Return text, recognised shared tags and proposed personal labels in the existing extraction result. The proposed companion keys are `suggestedSections.researchInterestText` and `suggestedSections.customInterestTags`; proposed new personal items contain a label without a persisted ID. Keep source references/snippets owner-only and preserve uncertainty warnings. Do not infer an interest solely from an unrelated qualification or employment record.
3. The existing review screen lets the user edit text, select/remove shared tags and accept/edit/reject personal suggestions. Suggesting a label creates no persistent tag or public vocabulary entry. Apply submitted components and the shared-ID resolutions above; omitted text/personal collections and unrelated sections retain their previous values.
4. Apply the accepted text/tags atomically to the unconfirmed profile, then require explicit confirmation. Generate usable matching embeddings from the confirmed permitted representation, not from an unreviewed extraction or the full private document.

**Matching inputs:** use confirmed free text as the primary semantic input, with shared/personal tag labels as documented supplementary context. For tag-only profiles, encode the available labels; never embed opaque IDs. Version the text-construction and combination rules and avoid double-counting the same concept. Do not require exact tag overlap before semantic comparison. The existing structured baseline continues to use shared IDs; report its missing coverage on text-only/custom-only examples rather than silently converting private labels into shared tags or dropping those examples. If semantic processing is unavailable, use the baseline and return `UNKNOWN` where no supported interest evidence remains; do not invent a match.

Build team embeddings only from the permitted projection. Key derived vectors/results by the relevant confirmed profile content, model/preprocessing version and visibility context; check current permission and confirmation on every use. Profile edits invalidate old derived inputs, while hiding interests or revoking discovery immediately prevents their use in team ranking/evidence. A model change requires regenerated compatible vectors. Text/tag interest similarity is not proof of skills, qualifications, publications or experience.

### 2.3 Implementing Features — Sequence and Responsibilities

1. **Agree the contract deltas and test manifest:** BE-64 supplies starting-state data; agree the additional interest fields/creation rules, filters, type codes, dates, reopening and evidence mappings. Implement the interest storage and extraction/import extensions with the existing profile/review owners before application integration.
2. **Verify shared foundations:** BE-42 and BE-50 audit confirmation, privacy, roles and sessions using the existing task 41/49 integration cases. BE-62 reuses task 61's review sequence and checks actual API/worker outcomes; the original reported error is not assumed to reproduce.
3. **Extend opportunity persistence/lifecycle:** BE-56 and BE-58 coordinate one migration and compatible create/update/detail responses.
4. **Implement authorised queries and evidence:** BE-48 uses the shared active-opportunity rule; BE-54 extends the evidence engine after permission filtering.
5. **Complete stable localisation contracts:** BE-60 checks new and existing errors with FE-1, including filter/expiry errors.
6. **Implement extraction and run semantic evaluation:** BE-44 delivers resume tags/free text and reviewed import; BE-46 builds a runnable embedding-based interest matcher and executes it alongside the structured baseline on the same labelled subset. Record whether the application adopts it and keep fallback working. BE-52 records end-to-end results and retests.

| Existing code area | Main backend work |
|---|---|
| `backend/src/features/auth/` and `backend/src/shared/security.py` | BE-50; authenticated user/role/session, CSRF and logout checks |
| `backend/src/features/profile/`, `privacy/` and `documents/` | BE-42/62 coordination; existing safeguards plus the additional text/personal-tag storage, suggestions and reviewed import |
| `backend/src/features/opportunities/` and `backend/src/db/opportunity_read.py` | BE-56/58/48; persistence, validation, shared availability and queries |
| `backend/src/features/matching/` | BE-42/48/54/46; permitted evidence, filters, scores and mandatory semantic experiment implementation; application integration follows the evaluation decision |
| `backend/src/db/models.py` and migration support | Coordinated schema changes and upgrade verification |
| `backend/src/shared/validation.py` and `docs/api/` | BE-60 and all changed public schemas, examples and error contracts |
| `backend/tests/` and evaluation/report artifacts | BE-64/44/46/52; isolated fixtures, measured results and regressions |

These are work areas, not assigned people. Reuse existing feature boundaries and shared database/access helpers rather than creating parallel auth, document or matching workflows.

### 2.4 Testing Guidelines — Data, Quality and Reproducibility

#### 2.4.1 DATA-40: Prepare Inputs Before Each Run

Use publicly available, owner-provided or otherwise authorised real examples for realistic workflow preparation. Shared evaluation artifacts must use synthetic or de-identified variants. Record provenance and intended use; do not attach original CV/transcript files or credentials to public reports.

Each dataset/run manifest must identify:

- Dataset version, stable example IDs, source, preparation steps, permitted use and private-original storage reference where applicable.
- Starting account roles, profile revisions/confirmation, opt-in and visible fields, opportunity publication/deadline states and the test clock.
- Expected extracted values and matching/relevance labels **checked before the run**, including partial, missing and unsupported evidence.
- Commit/configuration/worker/model versions, environment, setup procedure and the exact command used.
- An isolated seed/restore procedure: repeated preparation must not duplicate data; restoring the dataset must leave unrelated users unchanged.

Test fixtures belong in an explicitly scoped test database or dataset. No public seed/reset endpoint is required. Do not use the application's normal database as an evaluation reset target. Record actual sample counts; Jira does not supply an agreed minimum in the inspected descriptions.

Start from the synthetic CV, tags, contract examples and isolated setup already used by tasks 41/61 and the existing backend tests. QA-1 coordinates the shared examples and manual labels; BE-64 supplies versioning and machine-repeatable preparation/restore. Extend the shared dataset only for missing scenarios or evaluation coverage rather than duplicating the existing browser fixtures.

#### 2.4.2 US-11: Resume Tag and Free-Text Extraction

Implement the existing upload/worker/review/apply flow so the owner receives free-text skill titles/evidence and recognised research-interest tags alongside reviewable free text. The user also requested one unified description of the whole resume. See the [implemented fields, upgrade and test guide](docs/us11-resume-extraction.md) and [later free-text skill update](docs/free-text-skills.md).

- Return skill record IDs, free-text titles and supporting evidence without a skill-vocabulary requirement; return shared interest IDs recognised inside lists or paragraphs.
- Preserve source-grounded research-interest text even without a vocabulary match; propose short unmatched interest labels for explicit personal-tag review.
- Return `resumeDescription`, the whole resume's readable source text in one owner-only field. Preserve otherwise unrecognised sections and flag truncation; do not invent missing facts.
- Retain the existing course, experience and output descriptions. Reuse real PDF/DOCX reading, worker leases, authentication and document ownership.
- Review/apply only submitted components. Omitted components and their provenance persist; explicit empty strings/arrays clear them. Suggestions create no persistent tag.
- Resolve accepted exact shared/personal labels atomically, enforce owner isolation, combined limits and revision checks, then require separate confirmation.
- Share interest text/tags only under the existing confirmed, opted-in `researchInterests` visibility group. Keep the unified resume description and originals owner-only.
- Extend the checked-in OpenAPI and existing strict clients together. Use additive tables so old profiles, documents and existing table shapes survive upgrades.

Acceptance is demonstrated with functional extraction/import/persistence/privacy tests and reused real frontend HTTP/worker coverage. The separate US-13 semantic comparison retains its own implementation and evaluation responsibilities.

#### 2.4.3 US-13: Required Semantic Implementation and Evaluation

**BE-46 must deliver executable semantic matching code and actual comparison results.** The experiment itself requires no new public endpoint or immediate replacement of the application matcher. The separately requested interest-entry feature in section 2.2.4 does require changes to existing frontend profile/review controls.

1. Implement embedding-based research-interest similarity using a recorded model/method and configuration. Encode eligible interest text and opportunity research-area/interest text, then calculate similarity using a documented measure. Record how each input maps to its confirmed, permitted structured record or labelled evaluation example.
2. Execute both this semantic implementation and the existing structured/tag baseline on the **same representative, manually labelled talent and opportunity examples**, with the same eligibility rules, candidate pool and evaluation measures.
3. Include equivalent interests expressed differently, clearly unrelated interests, partial relevance and missing evidence. Record actual per-example outputs, aggregate quality measures, incorrect matches and measured runtime/resource costs.
4. Produce a supported decision to adopt or omit the semantic component **from the application recommendation flow**. Preserve the runnable experiment, configuration and results for reproduction regardless of that decision.

**Role of tags:** use section 2.2.4's text/shared/personal-tag inputs. Shared tags retain their structured baseline and explicit-ID filter roles; personal labels add user-defined interest context without entering the public vocabulary. Include text-only, shared-tag-only, personal-tag-only and combined examples on the same labelled candidate pool. Document the permitted input projection for each method and the baseline's coverage limitations. Preserve paraphrases and unrelated examples; equal tag IDs must not be a prerequisite for semantic comparison. Record supplementary-label handling so text/tag duplication cannot inflate the reported benefit.

Record model/method/version, configuration, preprocessing, thresholds, random seed if relevant, data split, latency, resource/practical costs, benefits and incorrect matches. Keep tuning examples separate from final evaluation examples where feasible; document limitations when the dataset is too small.

Only current confirmed, permitted information may enter team-facing evaluation, after opt-in and field-visibility checks. Similarity cannot establish a qualification, skill, publication or experience claim without supporting confirmed evidence. US-18 remains responsible for explanations grounded in permitted records.

If adopted in the application, separately version the algorithm, agree thresholds/score semantics and how results appear in US-18 explanations, and reuse the existing matching endpoints. Preserve structured fallback when the semantic component is unavailable or the evaluation finds no useful benefit. Application fallback does not waive the required experiment: if the semantic implementation has not run, record the comparison as incomplete, not passed. A decision to omit application integration satisfies US-13 only after the implemented semantic approach has been evaluated and the actual results support that decision.

Required handover evidence is the semantic implementation, dependency/model configuration, versioned input/label references, exact runnable comparison command, outputs from **both** approaches, measured results/limitations and adoption decision. A report alone, mock semantic scores or the unchanged tag engine are insufficient.

### 2.5 Sprint 2 Interface — API Specification

#### 2.5.1 Shared Conventions

- Retain `/api/v1`, camelCase JSON, uppercase enums, direct success objects and the existing error envelope.
- Use the opaque `h18_session` cookie, `credentials: 'include'`, allowed Origin checks and `X-CSRF-Token` on mutations. Successful login/registration rotates session credentials; clients use the returned CSRF token.
- Preserve `expectedRevision` for profile/privacy/opportunity writes and `expectedProfileRevision` for imports. Do not silently overwrite a conflict.
- Lists retain `{items, page, pageSize, total}`; defaults are page 1 and pageSize 20, with pageSize 1–100. Invalid values return 422. Empty/out-of-range pages return 200 with an empty array.
- Filter before counting and pagination. Matching lists retain summary and global rank within the filtered result set; details provide the requirement-level explanation.
- Normal opportunity browsing keeps `updatedAt DESC, id ASC`. Matching keeps score descending, unknown-weight percentage ascending, then ID ascending, with null scores last, unless a jointly versioned algorithm explicitly changes it.

#### 2.5.2 Reused and Extended Operations

All paths below are relative to `/api/v1`. **Every operation in this table already exists; Sprint 2 adds no HTTP method/path combinations.** The changes are extensions to their contracts and behaviour, not a claim that those extensions have been implemented.

| Method and path | Sprint 2 responsibility | Access |
|---|---|---|
| `GET /auth/session` | Stable `user.id`, stored `user.role`, current CSRF; anonymous returns `user: null` | Anonymous or signed in |
| `POST /auth/register/code`, `POST /auth/register` | Preserve verified-email flow, atomic role-bound creation and returned ID | Anonymous + CSRF |
| `POST /auth/login`, `POST /auth/logout` | ID/password return flow, correct session rotation/revocation | Existing auth rules |
| `GET /tags` | Shared vocabulary only; no personal labels or implicit tag creation | Signed in |
| `GET/PUT /me/profile`, `POST /me/profile/confirmation` | Extend content with interest text/personal tags; create/reuse personal tags during the atomic save; current revision and explicit reconfirmation | Talent owner |
| `GET/PUT /me/privacy` | Persist opt-in/visible fields; the existing interest setting covers text and both tag collections | Talent owner |
| `GET/POST /me/documents` | Existing list/upload and worker path | Talent owner |
| `GET /me/documents/{id}`, `GET /me/documents/{id}/extraction`, `GET /me/documents/{id}/file` | Correct owned-document state; interest text/shared/personal-tag suggestions; private originals and provenance | Talent owner |
| `POST /me/documents/{id}/apply` | Atomic selected-component import and accepted personal-tag resolution, then separate confirmation | Talent owner + CSRF |
| `GET /opportunities` | Active published browsing and combined filters; retain owner-only `scope=mine` | Signed in; team for mine |
| `POST /opportunities`, `PUT /opportunities/{id}` | Optional source URL, deadline and type; revision/lifecycle checks; PUT also accepts an explicit reopening request | Owner team + CSRF |
| `GET /opportunities/{id}` | New metadata and labelled expired details without new disclosure | Existing detail permissions |
| `POST /opportunities/{id}/publish` | Existing publication plus deadline validation; cannot bypass explicit reopening | Owner team + CSRF |
| `GET /me/recommendations` | Filtered active opportunities; current confirmed profile | Talent owner |
| `GET /me/opportunity-matches/{id}` | Current explanation; reject expired opportunity matching | Talent owner |
| `GET /opportunities/{id}/talent-matches` | Combined talent filters and permitted evidence/ranking for an active owned opportunity | Owner team |
| `GET /opportunities/{id}/talent-matches/{talentId}` | Shareable requirement evidence; recheck eligibility on direct access | Owner team |

No public evaluation, model-selection, database-reset, translation or arbitrary role-switch endpoint is required. Existing password-reset and collection routes remain compatible and outside the table's primary change scope.

#### 2.5.3 Proposed Search Parameters

Agree these names and limits with FE and add them to OpenAPI before use. Unknown query parameters on the extended search routes should produce a field-specific 422 rather than appear to filter successfully while being ignored.

| Route family | Proposed parameters | Meaning |
|---|---|---|
| Opportunity lists and talent recommendations | `q` | Trimmed case-insensitive substring search over title, university, discipline, research area and description; proposed maximum 200 characters |
| Opportunity lists and talent recommendations | `university`, `disciplineGroup`, `discipline`, `researchArea`, `opportunityType` | University/discipline/area use documented normalised exact text; group uses `STEM`/`BUSINESS`; type uses the agreed vocabulary |
| Opportunity lists and talent recommendations | `deadlineFrom`, `deadlineTo` | Offset-aware date-time bounds on `deadlineAt`, proposed half-open range `[from, to)`; no-deadline records excluded only when a deadline bound is supplied |
| Team talent matches for one owned opportunity | `q` | Search permitted profile fields, including visible confirmed interest text/personal labels; hidden data must not affect inclusion |
| Team talent matches | `skillTagId`, `interestTagId` | Explicit shared-vocabulary filters, not an automatic semantic candidate gate; validate kind/existence; skill matches require a confirmed visible positive claim. Personal labels are searchable through permitted `q`, not public tag-ID filters |
| All supported lists | `page`, `pageSize` | Existing strict pagination |

Proposed composition: **AND across different filters; OR within repeated values of the same supported multi-select filter**. Support repeated values for the five opportunity attribute filters and the two talent tag filters. `q`, dates, `scope` and pagination are single-valued; reject duplicates. Reject blank supplied filter values, malformed dates, reversed/equal bounded ranges and invalid enums. FE clears a filter by omitting its parameter and resets pagination to page 1.

Talent users browse only published active opportunities. `scope=mine` remains a team-owner management view that includes its drafts and expired records with explicit availability labels. A private draft is never made discoverable through search. Clearing filters returns the authorised baseline, not every stored record.

Do not search raw documents, extraction drafts or hidden fields. Apply the same permitted-data projection to filtering, totals, ranks, scores and explanations. Avoid returning autocomplete/facet counts derived from inaccessible records. Use parameterised queries; document text normalisation so MySQL and test behaviour agree.

#### 2.5.4 Proposed Opportunity Request Example

The following is a **complete proposed create body**, extending the existing content shape. All identifiers and content are synthetic; this is not accepted by the unchanged Sprint 1 schema.

```json
{
  "title": "Research assistant in data analysis",
  "university": "UNSW",
  "disciplineGroup": "STEM",
  "discipline": "Computer Science",
  "researchArea": "Research data analysis",
  "description": "Synthetic Sprint 2 opportunity for integration testing.",
  "requirements": [
    {
      "id": "req_python",
      "label": "Python experience",
      "kind": "SKILL",
      "importance": "REQUIRED",
      "tagIds": ["skill_python"]
    }
  ],
  "sourceUrl": "https://example.org/research/opportunity",
  "deadlineAt": "2026-10-29T06:00:00Z",
  "opportunityType": "RESEARCH_ASSISTANT"
}
```

Create still returns 201 and an owned draft. For an update, place the complete content in the existing `{expectedRevision, content}` envelope; the optional proposed `reopen` flag is described below. Detail/create/update responses retain their existing metadata and return the extended `content` plus proposed `availabilityStatus`.

Validate `sourceUrl` as an absolute HTTP/HTTPS URL with a valid host; reject malformed values and schemes such as `javascript:`, `data:` and `file:`. Do not require the URL to be publicly fetchable, limit it to university domains or fetch it to check its content. Google and LinkedIn links are supported within the same validation rules. A missing/null URL produces no source-link UI. FE opens the saved destination separately while preserving the opportunity page.

Reject dates without an offset and invalid calendar/time values. Serialize accepted times as UTC RFC3339. FE must show the deadline with an explicit zone; do not interpret a date-only input silently in the API server's local zone. Keep test clocks fixed so the sample's deadline does not make a future test nondeterministic.

#### 2.5.5 Explicit Reopening Through the Existing Update Endpoint

Reuse **`PUT /api/v1/opportunities/{id}`**. The proposed request extension adds optional boolean `reopen` beside `expectedRevision` and `content`; omitted or `false` means ordinary editing. This flag records an explicit owner action, is not stored as opportunity content and is not accepted on create. The frontend sends it only when the owner chooses to reopen, not whenever a deadline is edited.

Complete synthetic example, assuming the owner has read revision 4 and the test clock is before the submitted deadline:

```json
{
  "expectedRevision": 4,
  "reopen": true,
  "content": {
    "title": "Research assistant in data analysis",
    "university": "UNSW",
    "disciplineGroup": "STEM",
    "discipline": "Computer Science",
    "researchArea": "Research data analysis",
    "description": "Synthetic Sprint 2 opportunity for integration testing.",
    "requirements": [
      {
        "id": "req_python",
        "label": "Python experience",
        "kind": "SKILL",
        "importance": "REQUIRED",
        "tagIds": ["skill_python"]
      }
    ],
    "sourceUrl": "https://example.org/research/opportunity",
    "deadlineAt": "2026-10-29T06:00:00Z",
    "opportunityType": "RESEARCH_ASSISTANT"
  }
}
```

Check ownership and revision, validate the complete proposed content and evaluate expiry using one server time. With `reopen: true`, require an already published opportunity, valid publication requirements and a resulting deadline in the future or `null`. Apply the content changes and reopening atomically; if any check fails, neither change is saved. Return the existing 200 opportunity response and increment the revision once for the combined change. With no reopening flag, a previously expired opportunity stays expired even if its saved deadline becomes valid.

A stale revision returns `409 REVISION_CONFLICT`. Proposed errors are `409 OPPORTUNITY_NOT_PUBLISHED` for reopening a draft and `422 VALIDATION_ERROR` on `content.deadlineAt` for a deadline at/before now. An already active opportunity with unchanged content and its **current** revision is a no-op, including when `reopen: true`; real content changes still increment its revision. `/publish` on an expired published record must not silently clear its expiry marker. Test concurrent updates and reopen requests through the same PUT route.

Extend `OpportunityWrite` and its examples/validation without changing the endpoint path or HTTP method. Existing `{expectedRevision, content}` requests remain ordinary edits.

#### 2.5.6 Errors and Localisation

Preserve the current envelope and readable English fallback messages:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Check the submitted fields.",
    "fieldErrors": [
      {
        "field": "content.sourceUrl",
        "message": "Use an absolute HTTP or HTTPS URL."
      }
    ]
  },
  "requestId": "req_sprint2_example"
}
```

| Condition | Contract behaviour |
|---|---|
| Missing/expired session | 401 using the existing authentication error code |
| Wrong role, failed CSRF or disallowed Origin | 403 using existing security codes |
| Missing or inaccessible document, profile or opportunity | 404 `NOT_FOUND`; do not reveal another user's record existence |
| Stale revision | 409 `REVISION_CONFLICT` with `currentRevision` in the existing error structure |
| Current talent profile unconfirmed | 409 `PROFILE_UNCONFIRMED` on owner matching |
| Document queued/processing | 409 `EXTRACTION_NOT_READY` |
| Document failed | 422 `EXTRACTION_FAILED` |
| Invalid URL, deadline, type, query or field | 422 `VALIDATION_ERROR` with field paths |
| Expired opportunity passed to a matching endpoint | **Proposed:** 409 `OPPORTUNITY_EXPIRED`, after ordinary authorisation checks |

FE-49 and the owning frontend feature modules translate interface messages using stable error codes, field paths, enum values and existing `reasonCode` values. BE-60 preserves that contract and readable English server fallback text; it does not implement dictionaries, language persistence or display-time translation. If different validation reasons on one field need separate translations, propose an additive field-level code only for an identified gap and update schemas/clients together. Reuse the current frontend mappings instead of replacing its language framework.

Language changes must not mutate sessions, roles, profile/opportunity content, revisions, confirmation, privacy or scores. Do not translate stored user content or generated evidence summaries as part of this backend task. Backend tests verify stable codes/data; browser tests verify language persistence, fallback and readable layouts.

#### 2.5.7 Proposed Interest Review Request — Existing Apply Endpoint

This complete **proposed** body for `POST /me/documents/{id}/apply` contains synthetic content; `interest_machine_learning` represents an existing shared tag in the test fixture. The new fields require coordinated schema updates and are not accepted by the unchanged Sprint 1 schema.

```json
{
  "expectedProfileRevision": 4,
  "sections": {
    "researchInterests": ["interest_machine_learning"],
    "researchInterestText": "I want to use machine learning to analyse medical images and support disease diagnosis.",
    "customInterestTags": [
      {"label": "AI for rare-disease imaging"}
    ]
  }
}
```

The new personal label deliberately has no client-created ID. After ownership/revision validation, the backend reuses an exact shared/owner-local match or creates one owner-local record, saves the accepted content atomically and returns the canonical profile with stable IDs and `UNCONFIRMED` status. Duplicate submission must not create duplicate tags; a stale revision fails without creating anything. User confirmation remains a separate existing operation.

For manual editing, use the same three fields under `content` in the existing `PUT /me/profile`, alongside its required full profile content and `expectedRevision`. Reads return resolved `{id, label}` personal entries; an owner includes the ID to edit/retain an existing entry and omits it to request creation. Treat unowned/nonexistent personal IDs consistently without exposing another user's labels. Returning a canonical shared-tag match never renames the shared vocabulary.

Update `ProfileContent`, `ProfileSections`, extraction suggestions, uncertainty/provenance mappings, permitted team projections and associated examples/validators together. Keep privacy's selectable field as `researchInterests` for the whole group. Reject unsupported extra keys; do not weaken strict validation merely to accept the extension. This is an extension of existing operations, not an additional tag endpoint.

### 2.6 Authorisation — Sessions, Roles and Privacy

The backend must apply the following order to team discovery:

```text
Authenticate team → authorise ownership of the selected opportunity
→ verify published and active opportunity
→ select opted-in talent with the current confirmed profile revision
→ project only fields the talent permits the team to view
→ apply search/filters → evaluate evidence and scores
→ sort → count and paginate → return only the permitted representation
```

Direct match-detail requests repeat the checks. Revoking discovery excludes a talent from the next list and causes old team-detail requests to return 404. Hiding a field removes its effect on search, score and evidence; an explanation must not disclose that a hidden claim exists. Originals remain owner-only even when every structured profile field is visible.

Talent owners may match their own confirmed profiles without opting into reverse discovery. Privacy changes alone do not change their profile confirmation. An opted-in confirmed profile with no visible fields may retain the existing anonymous/UNKNOWN representation in an unfiltered team list, but hidden data cannot make it pass a selected filter.

Use the stored account role, not a login-form role or query parameter. Registration returns a stable `user.id` and `user.role`; `/auth/session` exposes them for the account page. A single-role account changes workflows by signing into an appropriately authorised account; no client role toggle can grant new privileges.

Verify two independent cookie jars using the shared integration tests. User A's logout or profile change must not change user B's session or data. FE-49 owns clearing the mounted workspace and private frontend caches on account changes; backend requests always resolve their owner from the current session. A submitted previous user's ID cannot restore access.

Keep personalised responses `Cache-Control: no-store`. Any application-side match cache must account for profile, privacy and opportunity revisions, algorithm version **and deadline passage**; expiry can occur without a content edit. Recompute eligibility on each request rather than serving an expired or revoked result from a stale cache.

### 2.7 Matching Rules — Evidence, Statuses and Scores

#### 2.7.1 US-18 Evidence Extension

The baseline engine compares free-text skill titles with existing criterion names
and evaluates shared interest tags. This describes existing code, not the complete
Sprint 2 matching target. BE-46 must implement and run the semantic interest
comparison in section 2.4.3. Separately, `team_service.py` currently builds its
matching snapshot from those two fields even though the visible profile can
contain education, experience and outputs; BE-54 must extend the evidence
evaluation path and specify its supported comparisons.

| Evidence source | Required supported mapping / boundary |
|---|---|
| Skills | Reuse visible confirmed positive/negative claims and tag IDs; a negative claim can establish a gap |
| Research interests | Use confirmed permitted free text and shared/personal tag labels from 2.2.4; retain shared IDs for baseline/filtering/fallback. Application semantic integration follows the measured decision; interest similarity alone does not establish factual credentials |
| Education | Map an explicit supported qualification/discipline criterion to the corresponding permitted education record and ID |
| Research experience | Map explicit supported experience criteria to a permitted stored research-experience record; a vague keyword is not proof of duration or expertise |
| Research outputs | Map explicit supported output criteria to a permitted stored output record; do not invent publications, authorship, quality or external verification |
| Unsupported criteria | Return `UNKNOWN` with a reason; document the unsupported case instead of inferring it from a high overall score |

Before implementation, specify criterion types, comparison operators and the evidence needed for full/partial satisfaction. Coordinate any requirement-schema extension and migration with the opportunity editor. Jira mandates grounded evidence, but does not prescribe the new enum names or an NLP model. Simply adding profile text beside the old tag score does not fulfil the requirement mapping.

For every supported result, return the requirement, status, stable reason code, readable reason and evidence referring to existing permitted records. Preserve the team evidence whitelist and remove all file/provenance identifiers. Recompute after profile/requirement/visibility changes. Examples must cover education, experience and outputs, not only Python tags.

#### 2.7.2 Four Statuses and Existing Baseline

| Status | Meaning |
|---|---|
| `MATCHED` | All supported criteria for that requirement have confirmed permitted evidence |
| `PARTIAL` | Some supported criteria have evidence, but the whole requirement is not established |
| `GAP` | Confirmed permitted evidence explicitly establishes an unmet requirement; missing information alone is insufficient |
| `UNKNOWN` | Evidence is missing, unconfirmed, inaccessible or the criterion is unsupported; no invented supporting evidence |

Keep the existing structured baseline reproducible for US-13 comparison and fallback: required weight 2, preferred weight 1; values MATCHED=1, PARTIAL=0.5, GAP=0, UNKNOWN=0. Its score is `100 × earned weighted value / total weight`, rounded to two decimal places using the existing rule. Unknown weight percentage and required-gap count remain visible; no criteria yields null score/unknown percentage and `INSUFFICIENT_CRITERIA`. These are the baseline's rules, not a requirement to calculate semantic similarity from tag overlap. Record semantic similarity separately during evaluation; any integration into application ranking/statuses requires a documented score/threshold contract supported by the results.

Extend and version the algorithm when adding new evaluation semantics; do not label changed evidence logic as the unchanged `tag-coverage-v1`. A high score is never independent proof of an unsupported qualification. Owner and team scores may differ because the team has a smaller permitted evidence set.

### 2.8 Working in Parallel — Collaboration and Integration

Use the **current Sprint 2 Jira groupings**, which differ from the old Sprint 1 FE numbering:

| FE / QA task | Backend partners | Integration agreement |
|---|---|---|
| [FE-1 / H18ABANANA-49](https://unsw-comp3900-comp9900-26t3.atlassian.net/browse/H18ABANANA-49) Account/workspace and languages | BE-50, BE-60 | Returned ID/role, logout/session behaviour, error translation mapping |
| [FE-2 / H18ABANANA-41](https://unsw-comp3900-comp9900-26t3.atlassian.net/browse/H18ABANANA-41) Confirmation/privacy | BE-42 | Revision, confirmation errors, visible-field and revocation behaviour |
| [FE-3 / H18ABANANA-61](https://unsw-comp3900-comp9900-26t3.atlassian.net/browse/H18ABANANA-61) Document review | BE-62 | Owned document ID, processing state, extraction/apply requests and actual failing response |
| [FE-4 / H18ABANANA-47](https://unsw-comp3900-comp9900-26t3.atlassian.net/browse/H18ABANANA-47) Opportunity search/link/deadline UI | BE-48, BE-56, BE-58 | Query semantics, type vocabulary, source URL, zoned deadline, expired details and explicit reopen |
| [FE-5 / H18ABANANA-53](https://unsw-comp3900-comp9900-26t3.atlassian.net/browse/H18ABANANA-53) Talent filters/explanations | BE-48, BE-54 | Permitted filters, requirement model, evidence shape, status/score consistency |
| [QA-1 / H18ABANANA-51](https://unsw-comp3900-comp9900-26t3.atlassian.net/browse/H18ABANANA-51) Browser acceptance and shared examples | BE-44, BE-46, BE-52, BE-64 | QA coordinates one workflow report; BE contributes API/worker/data results and separately owns quality/semantic reports using the shared dataset |
| Additional interest-entry scope; existing profile/review UI owners | Proposed BE-42/62/46 coordination | FE owns text input, shared/custom tag selection and review interactions. BE owns storage, label resolution, suggestions, permissions and semantic inputs. Add these deltas to the relevant task plans; existing FE-41/61 coverage does not certify them |

Several original FE/QA child items are marked merged into these shared tasks. Do not count a merged child as evidence that its corresponding backend feature is complete.

For FE-4/5, frontend owns filter controls, forms, source-link opening, deadline/expired labels, reopen controls and evidence presentation. Backend owns filtering, persistence, expiry decisions, permissions and evidence computation. The response/query proposals in section 2.5 are shared contract inputs, not backend assignments to build those screens.

**Document review sequence:** upload → poll owned document → once READY, read its extraction → review/correct/select sections → apply using the current profile revision → read the unconfirmed profile → explicit confirmation → refresh matching. No step requires voice recording. For BUG-35, capture the request/status/response and worker/document IDs before assigning a cause. If the APIs behave correctly, provide that evidence to FE rather than adding speculative recording-state logic.

**Interest-entry sequence:** type or review a source-grounded interest description → select shared tags and add/edit/remove personal labels → save selected content through the existing profile/apply route → display canonical tags and saved text → explicitly confirm → use permitted text/labels in the semantic experiment or adopted application matcher. Hiding the interest group or revoking discovery immediately removes all its inputs from subsequent team matching. FE extends the existing screens; BE does not build a second editor.

**Opportunity sequence:** create/edit metadata → publish with valid requirements/deadline → active browsing and both matching directions → deadline boundary → excluded from active results, detail visibly expired → owner explicitly reopens through the existing PUT with valid deadline/content and `reopen: true` → visible in active results again. Saving a deadline without the flag remains an ordinary edit.

**Evidence/consent sequence:** confirm → opt in and select fields → team filters and reads evidence → talent hides a field or revokes consent → next list/detail reflects the new permission state.

### 2.9 Acceptance Criteria — Required Outcomes

These are shared acceptance targets, not passed test results or a list of frontend features to implement in BE. Backend records API/database/worker outcomes; FE/QA records controls, rendering, navigation and browser observations. Reuse the existing task 41/49/61 tests for covered cases and add coverage only for an identified gap or new behaviour.

| Case | Related work | Required observable result |
|---|---|---|
| Fresh profile | US-10 | Private, unconfirmed and excluded from team discovery by default |
| Edit/import after confirmation | US-10, BUG-35 | New revision is unconfirmed; neither matching direction uses it until reconfirmed |
| Hidden-field isolation | US-10, US-14, US-18 | Changing a hidden field cannot affect team filtering, total, rank, score or returned evidence |
| Revoke discovery | US-10 | Next team list omits talent; previous detail request fails; owner workflow still works |
| Direct document access | US-10, BUG-35 | Owner can read/download; another talent/team cannot access file, extraction or apply by guessing IDs |
| Text/shared/personal-tag combinations | Additional interest scope | Text-only, shared-only, personal-only and combined inputs save/reload; no tag is mandatory for text; existing tag-only profiles remain valid |
| Personal-tag creation and isolation | Additional interest scope | Exact duplicates resolve to shared/owner-local records; repeated/concurrent saves create no duplicates; stale/invalid saves leave no partial records; another owner's ID cannot be used or edited |
| Label normalisation and scope | Additional interest scope | Whitespace/case variants reuse a label, semantic neighbours are not automatically merged, invalid labels fail clearly and private labels never enter `GET /tags` |
| Interest extraction and partial import | Additional interest scope | Source-grounded unmatched text is preserved; unaccepted label suggestions create no tags; omitted text/personal fields persist, explicit empty values clear them and accepted shared-ID resolution is shown before confirmation |
| Interest confirmation and visibility | Additional interest scope, US-10 | Text/tag edits invalidate confirmation and old derived inputs; hidden or revoked interests affect neither team search/rank nor evidence, including cached results |
| Interest input coverage and fallback | Additional interest scope, US-13 | Same candidate pool includes text-only/custom-only cases; no exact-ID semantic gate; baseline limitations and `UNKNOWN` fallback outcomes are recorded |
| URL lifecycle | US-19 | Add/edit/remove/reload works; no URL stays usable; invalid schemes fail; unrelated owner cannot write |
| URL independence | US-19 | Saving a URL makes no external fetch and adds no evidence or confirmation |
| Deadline boundaries | US-20 | Fixed-clock tests before, exactly at and after deadline agree across browsing, search and both matching directions |
| Optional deadline and details | US-20 | No deadline remains supported; expired published detail is labelled; owner record persists; private drafts stay private |
| Reopen and concurrency | US-20 | Ordinary deadline PUT cannot reopen; PUT with `reopen: true` and valid content reopens atomically; stale/non-owner/invalid requests save no changes |
| Combined opportunity filters | US-14 | University, discipline/area, type and date filters compose; clear restores authorised active results |
| Talent filters | US-14 | Requirements and supported skill/interest queries use only confirmed visible fields; hidden fields do not become search side channels |
| Empty results and pagination | US-14 | 200 empty list, correct permitted total, stable ordering/rank; invalid queries fail clearly |
| Evidence extension | US-18 | Strong, partial, explicit unmet and missing-evidence cases map to real permitted education/experience/output records |
| Evidence refresh | US-18 | Saved profile/requirement/privacy changes alter subsequent explanations correctly; no fabricated facts |
| Account return flow | US-15 | Both roles register, receive IDs, log out and sign in with ID/password to saved data |
| Invalid/duplicate registration | US-15 | Clear structured error; no partial account or duplicate profile/privacy records |
| Session/role isolation | US-15 | Two independent users remain isolated; forged role denied; account switch cannot retain access to prior private data |
| Language independence | US-21 | Backend preserves codes, field paths, fallback server text and domain values; FE/QA verifies selector, persistence, translation and layout |
| Review success | BUG-35, US-16 | Backend returns the owned READY result, imports corrections atomically and requires later confirmation; FE-61 owns opening/recovery/editor behaviour and its existing regressions |
| Review failure and conflict | BUG-35, US-16 | Pending/failed/missing/cross-user requests have defined errors; stale import cannot overwrite newer profile data |
| Data preparation/reset | DATA-40 | Manifest identifies starting state; repeatable setup has no duplicates; restore preserves unrelated records |
| Resume extraction | US-11 | Tags, section free text and an owner-only unified description survive reviewed atomic import/reload; source grounding, privacy and revision checks hold |
| Semantic comparison | US-13 | Runnable embedding implementation has executed on the same labelled examples as the baseline; actual outputs, costs/errors and application adopt/omit decision are reproducible; fallback works |
| Upgrade/persistence | All changed storage | Fresh and migrated MySQL preserve old data; new values survive refresh, re-login and service restart |

### 2.10 Dryrun — Pre-Demonstration Checks

This is a **joint FE/QA/BE walkthrough**, not an additional backend UI work package. FE/QA drives the browser steps and consolidates the US-16 report; BE prepares isolated data, runs the shared integration/API/worker checks and supplies server evidence. BE owns the quality/semantic evaluation in step 8. Do not duplicate the existing task 41/49/61 walkthroughs as a separate acceptance suite.

1. Record the build, database/worker configuration, dataset version and test clock. Prepare two talent and two team accounts in an isolated test environment as a proposed minimum for access-isolation checks.
2. Exercise registration and ID re-login for both roles, plus independent sessions, invalid input and duplicate registration.
3. Reuse FE-41/61's manual-profile, upload, review/correct/import and explicit-confirmation flow, adding text/shared/personal-tag cases from 2.9. Verify unmatched text retention, tag acceptance/rejection, saved canonical IDs and confirmation/privacy refresh. Separately record the actual BUG-35 result and a not-ready/failure path; retain a not-reproduced outcome when appropriate.
4. Create/publish an opportunity with source URL, type and deadline. Check URL removal, no-deadline records, combined filters and empty results.
5. Demonstrate team evidence for supported education, experience and outputs. Hide a field, then revoke discovery; verify lists, scores and direct details update.
6. Use controlled tests for before/exactly-at/after expiry. Demonstrate expired detail and explicit reopen; do not change the host clock or real users' records for the demonstration.
7. Switch the UI between English and Simplified Chinese and check stable API data/errors; record broader language coverage separately if tested.
8. Run the quality evaluation and execute both the implemented semantic matcher and structured baseline from their saved configurations on the same labelled examples. Record actual outputs, costs, failures and the application adoption decision independently of the UI walkthrough. A tag-only run does not complete US-13.

US-16 case records must include case/story ID, environment, starting state, steps, expected result, actual result, pass/fail/blocked status and evidence. Defect records need reproduction steps, affected component, severity, observed failure, practical investigation/fix suggestion and retest outcome. Mark an unknown root cause as unconfirmed. Do not mark a case passed because its implementation task is Done.

### 2.11 Sprint 2 Delivery — Delivery Checklist

- [ ] All 12 parent items have backend evidence or an explicitly recorded remaining limitation, linked through their existing BE subtasks.
- [ ] All Sprint 2 behaviour reuses existing HTTP method/path combinations; reopening extends the existing opportunity PUT, and evaluation/data tooling adds no public endpoints.
- [ ] New schemas, queries, errors, evidence mappings and reopening semantics are agreed with FE and reflected in OpenAPI, examples, endpoint index and tests.
- [ ] Source URLs, deadlines, type data and lifecycle markers have reviewed migrations and preserve existing records.
- [ ] Additional interest text/personal-tag fields and migrations preserve existing shared IDs and old-client omission behaviour; exact deduplication, owner isolation and atomic save/import are verified.
- [ ] Extraction retains source-grounded interest text without a tag match; personal suggestions create nothing until accepted. Confirmed text/shared/personal inputs and derived embeddings follow the existing interest visibility group.
- [ ] FE profile/review controls for the additional interest scope are explicitly coordinated and covered as new work; backend supplies schemas, canonical saves and permission checks without taking over UI implementation.
- [ ] Confirmation, consent, visibility, ownership and independent sessions are tested on list and direct-request paths.
- [ ] US-18 evaluates supported education/experience/output evidence, with no fabricated qualifications or document leakage.
- [ ] BE-62 links the existing FE-61/shared regression evidence and records actual API/worker outcomes, any demonstrated server fix and retest, or an explicit not-reproduced outcome with the original cause still unverified.
- [ ] DATA-40 delivers a versioned manifest and demonstrated isolated seed/restore procedure.
- [ ] US-11 delivers working resume tag/free-text extraction, a unified owner-only description, compatible persistence and passing review/import/privacy regressions.
- [ ] BE-46 delivers runnable embedding-based research-interest matching code, model/dependency configuration and an exact comparison command.
- [ ] US-13 records actual semantic and structured-baseline outputs on the same versioned labelled examples, including equivalent wording, unrelated interests, errors, metrics and measured costs. Mock scores or a tag-only run do not pass.
- [ ] US-13 records an evidence-backed application adoption/omission decision and working structured fallback. Omitting application integration does not remove the requirement to implement and execute the semantic experiment.
- [ ] BE-52 contributes API/database/worker results and links reused integration cases in the single US-16 report coordinated by QA-1; FE/QA supplies browser observations. Quality/semantic reports remain separate, and skips/mocks are clearly labelled.
- [ ] Frontend-owned controls, translation dictionaries, refresh/draft guards and review recovery remain with their FE tasks; backend changes address server guarantees or demonstrated gaps without duplicating those implementations or tests.
- [ ] Startup, migration, test and evaluation commands are documented and reproducible; no secrets or private originals enter shared reports.

Suggested artifact names are `docs/testing/sprint-2-dataset-manifest.json` (BE-64 with QA's shared inputs), [the US-11 implementation guide](docs/us11-resume-extraction.md) (BE-44), `docs/testing/sprint-2-semantic-comparison.md` (BE-46) and `docs/testing/sprint-2-e2e-report.md` (QA-1 coordination with BE-52 result sections). These are **planned deliverables, not files created or evaluations executed by this README**. Reuse an equivalent existing shared report rather than creating a second one. The manifest's exact schema and runner/seed command names must be supplied by BE-64/44/46 when implemented.

## 3. Backend Setup, Verification and Handover

### 3.1 Start the Existing Stack

For the full frontend/API/MySQL/document-worker environment, follow the [integrated Docker guide](docs/docker-integration.md). From the repository root with Docker running Linux containers:

```sh
docker compose up --build --detach --wait --wait-timeout 180
```

The frontend defaults to `http://127.0.0.1:5173`; the backend host port defaults to 8000 but may be overridden by the existing root `.env`. Preserve that file and the existing Compose project name/volumes. Check configured service health rather than assuming a machine-specific port. SMTP configuration is needed for real email registration/reset; see the [registration guide](docs/us01-registration.md).

For a backend-only stack, retain the [Sprint 1 Docker backend workflow](README_DEVELOPER_EN.md#3-docker-backend-guide). New Sprint 2 column changes require their explicit migration before updated services run; rebuilding an image or rerunning `init-db` is not a schema migration.

### 3.2 Development and Existing Verification Commands

For native development, use the existing [backend setup instructions](backend/README.md). First-time setup uses `setup.ps1` on Windows or `sh setup.sh` on macOS/Linux. Docker-only startup does not require the host virtual environment.

After native dependencies are installed, run from the repository root:

**Windows:**

```powershell
.\.venv\Scripts\python.exe -m pytest -q -rs --require-frontend
powershell -NoProfile -ExecutionPolicy Bypass -File .\frontend\run.ps1 test
```

**macOS / Linux:**

```sh
.venv/bin/python -m pytest -q -rs --require-frontend
sh frontend/run.sh test
```

`--require-frontend` makes missing real HTTP integration dependencies a failure rather than a silent skip. The existing integration harness uses real HTTP and the React app in jsdom; it does not by itself prove Chrome layout, link opening, the Vite proxy or production HTTPS behaviour. Run the browser acceptance cases separately.

The default backend tests use isolated temporary SQLite databases. MySQL acceptance uses the existing `--run-mysql` option and `MYSQL_TEST_DATABASE_URL` pointing to a **dedicated disposable database whose name ends in `_test`**. That fixture clears tables: never point it at the normal application database. Include real MySQL migration and persistence checks for changed storage. Real container testing is available through the existing `--run-docker` option; do not describe mocked Docker tests as a successful container deployment.

Add focused Sprint 2 tests for changed behaviour; existing suites alone do not certify interest text/personal tags, new filters, deadlines or evidence mappings. BE-44 publishes its extraction regression commands; BE-46/64 must publish their actual evaluation/seed commands once those runners exist rather than relying on hypothetical commands in documentation.

### 3.3 Contract Decisions to Record Before Integration

| Decision | Proposed direction in this README | Responsible work |
|---|---|---|
| Additional interest data and inline creation | Preserve shared-ID array; add optional text and owner-local `{id, label}` tags; omission preservation and exact shared/owner-local resolution through existing saves | Proposed BE-42/62 coordination + profile/review FE owners |
| Interest visibility and semantic input | One `researchInterests` privacy group; primary free text plus documented label context; shared catalog stays unchanged; version input construction and invalidate derived data | BE-42/46/48/54 + profile/review FE owners |
| Opportunity field names and compatibility | Nullable source URL/deadline/type; omission preservation on legacy updates | BE-56/58/48 + FE-4 |
| Type vocabulary | Proposed five codes in 2.2.2; confirm supported types | BE-48 + FE-4 |
| Date-range meaning and display zone | Deadline-based half-open ranges; UTC API, explicitly zoned UI | BE-48/58 + FE-4 |
| Expiry/reopening | Shared read-time predicate plus retained closure; explicit revision-checked `reopen` flag on the existing PUT | BE-58 + FE-4/5 |
| Expanded requirements and evidence | Explicit structured criteria and supported education/experience/output mappings | BE-54 + FE-4/5 |
| Semantic implementation and application adoption | Runnable embedding experiment and executed same-data comparison are mandatory; decide application integration from measured results and preserve baseline/fallback | BE-46/44/54 |
| Localised validation mapping | Reuse error/reason codes and field paths; add compatible codes only where needed | BE-60 + FE-1 |
| Dataset size and quality targets | Record agreed counts/thresholds before evaluation; do not invent client-approved targets | BE-64/44/46 + QA-1 |

US-11 implementation and verification are recorded in its linked guide. Other Sprint 2 work requires its own implementation and recorded acceptance evidence; this guide does not change Jira status or claim completion of the whole sprint.
