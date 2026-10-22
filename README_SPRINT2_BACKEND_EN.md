# COMP3900 / COMP9900 — H18ABANANA

**🍌 Explainable Two-Sided Research Matching · Sprint 2 Backend Developer Specification**

Prepared: **2026-10-22**. Document version: **`0.2.1-draft`**.

This README follows the structure of the [Sprint 1 developer README](README_DEVELOPER_EN.md) and gives the Python backend team a Sprint 2 implementation and acceptance guide. Continue using **Flask, MySQL 8.4, PyMySQL and SQLAlchemy**, the existing document worker and the `/api/v1` API.

**API scope: no new HTTP endpoints.** Sprint 2 reuses existing method/path combinations, extending their fields, query parameters, validation and business logic where needed. Explicit reopening uses the existing opportunity update endpoint. Evaluation and test-data preparation use local tooling, not additional public APIs.

> **Document status:** Jira requirements and backend subtasks were read on 22 October 2026. Repository observations refer to local `main` at `f064daa`. This is a development specification, not a completion or test report. Items labelled **proposed** are integration decisions for review, not already implemented endpoints or Jira-mandated field names. The document version does not change the running API or the checked-in OpenAPI version.

## Contents

[[_TOC_]]

## Change Log

- **2026-10-22:** Confirmed the no-new-endpoints constraint. Explicit reopening is an optional, deliberate operation within the existing opportunity update request.
- **2026-10-22:** Created the Sprint 2 backend guide from all 12 sprint work items and their 12 backend subtasks. Added scope, existing-code gaps, data and API proposals, permissions, evaluation methods, integration cases and delivery requirements.

## 🫡 0. Aims — Sprint Goals

1. Enforce current-profile confirmation, explicit discovery consent, field visibility and private original-document access across every relevant API.
2. Support authorised combined search, optional opportunity source URLs, deadlines, automatic expiry and explicit reopening.
3. Explain research-team recommendations using specific permitted, confirmed profile evidence, including supported education, experience and research-output evidence.
4. Verify registration, user-ID login and independent sessions, and provide stable API codes for interface localisation.
5. Resolve the reported document-review failure using a reproduced cause and regression evidence.
6. Deliver versioned test inputs, a reproducible extraction/matching quality evaluation, a semantic-similarity comparison and a separate end-to-end test report.

## 🌈 1. Overview — Project and Scope

### 1.1 Sources and How to Use This Document

| Source | Purpose |
|---|---|
| [Jira backlog](https://unsw-comp3900-comp9900-26t3.atlassian.net/jira/software/projects/H18ABANANA/boards/103/backlog) and the supplied screenshot | Sprint membership, displayed dates and parent estimates |
| Jira parent descriptions and backend subtasks linked in section 2.1 | Required behaviour, acceptance criteria, dependencies and scope boundaries; read live on 2026-10-22 |
| [Sprint 1 developer README](README_DEVELOPER_EN.md) | Document structure and existing development conventions |
| [Sprint 1 API contract](docs/api/sprint-1-api-contract.md), [OpenAPI](docs/api/openapi.json), [endpoint index](docs/api/endpoint-index.json), [examples](docs/api/examples/index.json) | Current request/response baseline; unchanged operations retain their existing contract |
| [Backend README](backend/README.md), [document guide](docs/us09-documents.md), [MySQL migration guide](docs/mysql-migration.md) | Existing setup, worker, persistence and migration procedures |
| Local source and tests at `f064daa` | Evidence of existing implementation and specific gaps; source inspection does not prove runtime acceptance |

Read section 2.1 for task ownership boundaries, then sections 2.2–2.7 for implementation rules. Before integrating any proposed schema change, update the shared contract, OpenAPI, example index/fixtures and corresponding FE/BE tests together. `backend/src/shared/validation.py` validates requests against the checked-in OpenAPI, so adding a field only to Python or the UI is insufficient.

The original meeting notes referenced by Jira were not available in this checkout. This README does not invent meeting-approved sample counts, numerical quality targets, additional languages or submission dates.

### 1.2 Sprint 2 Boundaries

The supplied board shows **21–29 October 2026**, **12 parent work items** and **53 Story Points**. These are sprint planning details, not demonstration dates or grading weights. Backend subtasks retain their parent's estimate; do not count the points twice. The backend subtasks were unassigned when read; parent assignees are not backend assignments.

- **In scope:** US-10, US-11, US-13, US-14, US-15, US-16, US-18, US-19, US-20, US-21, BUG-35 and DATA-40.
- **US-13 is an experiment:** the required deliverable is a reproducible comparison and supported adopt/omit decision. Shipping embeddings is conditional on the findings; a working structured fallback is required.
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
| Documents | PDF/DOCX upload, worker, extraction state, review result and selected-section import | Reproduce BUG-35; correct a backend cause only if demonstrated; add regressions |
| Opportunities | Draft/create/edit/publish/list/detail and revision checks | Add optional source URL, deadline, type/filter support and explicit reopening with migrations |
| Matching | `tag-coverage-v1`, four statuses and per-requirement evidence based on skills/interests | Add supported education/experience/output mappings and preserve evidence permissions |
| Search | Opportunity routes currently consume `scope`, `page`, `pageSize`; matching routes consume pagination | Define, validate and apply combined filters before ranking/pagination |
| Evaluation | [US-06 synthetic matching evaluation](docs/testing/us06-evaluation.md) and existing tests | Add independent extraction/relevance labels and US-11/US-13 reports; old test results are not Sprint 2 results |
| Localisation | Frontend language catalogue; backend error codes, field paths and English messages | Fill any code/mapping gaps while preserving domain values and API compatibility |

The current opportunity model has no `sourceUrl`, deadline or opportunity-type field. Its persisted status is `DRAFT` or `PUBLISHED`. Requirement kinds are currently only `SKILL` and `INTEREST`. These are concrete schema gaps, not merely missing frontend labels.

## 🐶 2. Sprint 2 — Backend Functionality and Tests

### 2.1 Task — Sprint Requirements

| Story / task | Jira parent | Points | Backend subtask | Required backend outcome |
|---|---|---:|---|---|
| US-10 Confirmation and document privacy | [H18ABANANA-3](https://unsw-comp3900-comp9900-26t3.atlassian.net/browse/H18ABANANA-3) | 3 | [BE-42](https://unsw-comp3900-comp9900-26t3.atlassian.net/browse/H18ABANANA-42) | Use the current confirmed revision; enforce opt-in, permitted fields and owner-only originals on list/detail/direct requests |
| US-11 Extraction and matching quality | [H18ABANANA-4](https://unsw-comp3900-comp9900-26t3.atlassian.net/browse/H18ABANANA-4) | 5 | [BE-44](https://unsw-comp3900-comp9900-26t3.atlassian.net/browse/H18ABANANA-44) | Versioned evaluation runner, independently checked labels, defined measures, actual results and linked findings |
| US-13 Semantic interest matching evaluation | [H18ABANANA-6](https://unsw-comp3900-comp9900-26t3.atlassian.net/browse/H18ABANANA-6) | 8 | [BE-46](https://unsw-comp3900-comp9900-26t3.atlassian.net/browse/H18ABANANA-46) | Same-input structured/semantic comparison, costs and failure examples, adopt/omit decision and fallback |
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
| Reviewed import | Save only selected sections; omitted sections stay unchanged, explicit empty arrays clear sections. Every successful import increments the profile revision and clears confirmation |
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

### 2.3 Implementing Features — Sequence and Responsibilities

1. **Agree the contract deltas and test manifest:** BE-64 supplies starting-state data; agree filters, type codes, dates, reopening and evidence mappings.
2. **Verify shared foundations:** BE-42 and BE-50 cover confirmation, privacy, roles and sessions. BE-62 reproduces the review defect early because it blocks document workflows.
3. **Extend opportunity persistence/lifecycle:** BE-56 and BE-58 coordinate one migration and compatible create/update/detail responses.
4. **Implement authorised queries and evidence:** BE-48 uses the shared active-opportunity rule; BE-54 extends the evidence engine after permission filtering.
5. **Complete stable localisation contracts:** BE-60 checks new and existing errors with FE-1, including filter/expiry errors.
6. **Run evaluations and integration:** BE-44 evaluates quality; BE-46 compares semantic methods on the same labelled subset; BE-52 records end-to-end results and retests.

| Existing code area | Main backend work |
|---|---|
| `backend/src/features/auth/` and `backend/src/shared/security.py` | BE-50; authenticated user/role/session, CSRF and logout checks |
| `backend/src/features/profile/`, `privacy/` and `documents/` | BE-42/62; confirmation, access, document states and imports |
| `backend/src/features/opportunities/` and `backend/src/db/opportunity_read.py` | BE-56/58/48; persistence, validation, shared availability and queries |
| `backend/src/features/matching/` | BE-42/48/54/46; permitted evidence, filters, scores and optional semantic integration |
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

#### 2.4.2 US-11: Quality Evaluation

Evaluate extraction and matching separately from whether a browser workflow succeeds. Include education, research experience, skills, outputs and interests; also report courses because the existing extractor supports that section. Include incomplete documents, unconfirmed imports, unsupported claims and missing evidence.

**Proposed measurement rules:** agree and freeze the normalisation, matching thresholds and denominator rules before reporting results.

| Measure | Definition / reporting requirement |
|---|---|
| Extraction field correctness | For manually defined reference slots, `C / (C + I + M)`: correct values C, incorrect values I, missing values M. State exact-match/normalised-match rules per field |
| Extraction output precision | `C / (C + I + U)`, where U is extra unsupported output. Report unsupported outputs explicitly so hallucinated additions are not hidden by reference-slot accuracy |
| Requirement-status accuracy | Correct `MATCHED`/`PARTIAL`/`GAP`/`UNKNOWN` decisions divided by labelled requirements; report per-status errors |
| Matching precision@K | Relevant returned items / returned items in the first K results; fix K and the relevance definition in advance |
| Matching recall@K | Relevant returned items in the first K / all manually labelled relevant items in the eligible candidate pool |
| Coverage and limitations | Sample counts, incomplete/unjudgeable cases, error examples, dataset balance and known limitations; no extrapolation from a tiny sample to general system accuracy |

Define whether partially relevant examples count as relevant before computing binary precision/recall; retain the original partial label in the report. Eligibility is based on role, confirmation, visibility and opportunity availability. A system `UNKNOWN` status means missing permitted evidence, not automatically an irrelevant candidate. Unjudgeable gold labels must be reported separately with explicit exclusion counts. A zero denominator is **N/A**, not an invented 0% or 100%.

Report raw counts alongside percentages. Link incorrect outputs to improvement/defect records. The existing US-06 perfect synthetic-fixture results neither establish real-document extraction quality nor satisfy US-11's relevance evaluation.

#### 2.4.3 US-13: Semantic Similarity Experiment

Compare the structured baseline and embedding-based research-interest similarity on the **same representative, manually labelled inputs**, with the same eligibility rules and evaluation measures. Include equivalent interests expressed differently and clearly unrelated interests.

Record model/method/version, configuration, preprocessing, thresholds, random seed if relevant, data split, latency, resource/practical costs, benefits and incorrect matches. Keep tuning examples separate from final evaluation examples where feasible; document limitations when the dataset is too small.

Only current confirmed, permitted information may enter team-facing evaluation. Similarity cannot establish a qualification, skill, publication or experience claim. If adopted, separately version the algorithm and agree how semantic results appear in US-18 explanations; preserve the structured fallback when the component is unavailable. An evidence-backed decision to omit semantics satisfies the experiment requirement.

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
| `GET/PUT /me/profile`, `POST /me/profile/confirmation` | Current revision and explicit reconfirmation | Talent owner |
| `GET/PUT /me/privacy` | Persist opt-in/visible fields; apply on subsequent reads | Talent owner |
| `GET/POST /me/documents` | Existing list/upload and worker path | Talent owner |
| `GET /me/documents/{id}`, `GET /me/documents/{id}/extraction`, `GET /me/documents/{id}/file` | Correct owned-document state, suggestions and private file | Talent owner |
| `POST /me/documents/{id}/apply` | Atomic reviewed import, then separate confirmation | Talent owner + CSRF |
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
| Team talent matches for one owned opportunity | `q` | Search only allowed structured fields; hidden names, skills, experience or outputs must not affect inclusion |
| Team talent matches | `skillTagId`, `interestTagId` | Repeated tag parameters; validate tag kind and existence; skill matches require a confirmed visible positive claim |
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

US-21 uses stable error codes, field paths, enum values and existing `reasonCode` values to translate interface messages. Retain English fallback text. If different validation reasons on one field need separate translations, propose an additive field-level code and update schemas/clients together; do not parse unstable English prose as a permanent protocol.

Language changes must not mutate sessions, roles, profile/opportunity content, revisions, confirmation, privacy or scores. Do not translate stored user content or generated evidence summaries as part of this backend task. Backend tests verify stable codes/data; browser tests verify language persistence, fallback and readable layouts.

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

Verify two independent browser contexts/cookie jars. User A's logout or profile change must not change user B's session or data. A same-browser account change must clear private frontend caches; server requests always resolve their owner from the current session. A submitted previous user's ID cannot restore access.

Keep personalised responses `Cache-Control: no-store`. Any application-side match cache must account for profile, privacy and opportunity revisions, algorithm version **and deadline passage**; expiry can occur without a content edit. Recompute eligibility on each request rather than serving an expired or revoked result from a stale cache.

### 2.7 Matching Rules — Evidence, Statuses and Scores

#### 2.7.1 US-18 Evidence Extension

The current engine evaluates only skill and interest tags. `team_service.py` builds its matching snapshot from those two fields even though the visible profile can contain education, experience and outputs. BE-54 must extend the actual evaluation path and specify its supported comparisons.

| Evidence source | Required supported mapping / boundary |
|---|---|
| Skills | Reuse visible confirmed positive/negative claims and tag IDs; a negative claim can establish a gap |
| Research interests | Reuse confirmed permitted tags; any adopted semantic comparison describes interest similarity, not factual credentials |
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

Retain the existing baseline unless a reviewed algorithm change is documented: required weight 2, preferred weight 1; values MATCHED=1, PARTIAL=0.5, GAP=0, UNKNOWN=0. Score is `100 × earned weighted value / total weight`, rounded to two decimal places using the existing rule. Unknown weight percentage and required-gap count remain visible; no criteria yields null score/unknown percentage and `INSUFFICIENT_CRITERIA`.

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
| [QA-1 / H18ABANANA-51](https://unsw-comp3900-comp9900-26t3.atlassian.net/browse/H18ABANANA-51) Browser acceptance and shared examples | BE-44, BE-46, BE-52, BE-64 | One versioned dataset, separate workflow/quality reports, actual outcomes and linked retests |

Several original FE/QA child items are marked merged into these shared tasks. Do not count a merged child as evidence that its corresponding backend feature is complete.

**Document review sequence:** upload → poll owned document → once READY, read its extraction → review/correct/select sections → apply using the current profile revision → read the unconfirmed profile → explicit confirmation → refresh matching. No step requires voice recording. For BUG-35, capture the request/status/response and worker/document IDs before assigning a cause. If the APIs behave correctly, provide that evidence to FE rather than adding speculative recording-state logic.

**Opportunity sequence:** create/edit metadata → publish with valid requirements/deadline → active browsing and both matching directions → deadline boundary → excluded from active results, detail visibly expired → owner explicitly reopens through the existing PUT with valid deadline/content and `reopen: true` → visible in active results again. Saving a deadline without the flag remains an ordinary edit.

**Evidence/consent sequence:** confirm → opt in and select fields → team filters and reads evidence → talent hides a field or revokes consent → next list/detail reflects the new permission state.

### 2.9 Acceptance Criteria — Required Outcomes

These are acceptance targets, not passed test results. Record the actual result for each relevant case.

| Case | Related work | Required observable result |
|---|---|---|
| Fresh profile | US-10 | Private, unconfirmed and excluded from team discovery by default |
| Edit/import after confirmation | US-10, BUG-35 | New revision is unconfirmed; neither matching direction uses it until reconfirmed |
| Hidden-field isolation | US-10, US-14, US-18 | Changing a hidden field cannot affect team filtering, total, rank, score or returned evidence |
| Revoke discovery | US-10 | Next team list omits talent; previous detail request fails; owner workflow still works |
| Direct document access | US-10, BUG-35 | Owner can read/download; another talent/team cannot access file, extraction or apply by guessing IDs |
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
| Language independence | US-21 | Interface language changes preserve auth/domain values; API code/field mapping and English fallback work |
| Review success | BUG-35, US-16 | Correct READY document opens review, corrections import to its owner and later confirmation enables matching without recording |
| Review failure and conflict | BUG-35, US-16 | Pending/failed/missing/cross-user requests have defined errors; stale import cannot overwrite newer profile data |
| Data preparation/reset | DATA-40 | Manifest identifies starting state; repeatable setup has no duplicates; restore preserves unrelated records |
| Quality evaluation | US-11 | Versioned labels, raw counts, defined denominators, unsupported outputs and reproducible results/limitations |
| Semantic comparison | US-13 | Same-data comparison, costs/errors and supported adopt/omit decision; unavailable component falls back |
| Upgrade/persistence | All changed storage | Fresh and migrated MySQL preserve old data; new values survive refresh, re-login and service restart |

### 2.10 Dryrun — Pre-Demonstration Checks

1. Record the build, database/worker configuration, dataset version and test clock. Prepare two talent and two team accounts in an isolated test environment as a proposed minimum for access-isolation checks.
2. Exercise registration and ID re-login for both roles, plus independent sessions, invalid input and duplicate registration.
3. Save a manual profile, upload a supported test document, review/correct/import its suggestions and explicitly confirm. Reproduce and retest the reported BUG-35 sequence and a not-ready/failure path.
4. Create/publish an opportunity with source URL, type and deadline. Check URL removal, no-deadline records, combined filters and empty results.
5. Demonstrate team evidence for supported education, experience and outputs. Hide a field, then revoke discovery; verify lists, scores and direct details update.
6. Use controlled tests for before/exactly-at/after expiry. Demonstrate expired detail and explicit reopen; do not change the host clock or real users' records for the demonstration.
7. Switch the UI between English and Simplified Chinese and check stable API data/errors; record broader language coverage separately if tested.
8. Run the quality and semantic evaluations from their saved configurations. Record failures, fixes, retests and limitations independently of the UI walkthrough.

US-16 case records must include case/story ID, environment, starting state, steps, expected result, actual result, pass/fail/blocked status and evidence. Defect records need reproduction steps, affected component, severity, observed failure, practical investigation/fix suggestion and retest outcome. Mark an unknown root cause as unconfirmed. Do not mark a case passed because its implementation task is Done.

### 2.11 Sprint 2 Delivery — Delivery Checklist

- [ ] All 12 parent items have backend evidence or an explicitly recorded remaining limitation, linked through their existing BE subtasks.
- [ ] All Sprint 2 behaviour reuses existing HTTP method/path combinations; reopening extends the existing opportunity PUT, and evaluation/data tooling adds no public endpoints.
- [ ] New schemas, queries, errors, evidence mappings and reopening semantics are agreed with FE and reflected in OpenAPI, examples, endpoint index and tests.
- [ ] Source URLs, deadlines, type data and lifecycle markers have reviewed migrations and preserve existing records.
- [ ] Confirmation, consent, visibility, ownership and independent sessions are tested on list and direct-request paths.
- [ ] US-18 evaluates supported education/experience/output evidence, with no fabricated qualifications or document leakage.
- [ ] BUG-35 has a reproduced result, confirmed cause where found, successful/failure regressions and a linked retest record.
- [ ] DATA-40 delivers a versioned manifest and demonstrated isolated seed/restore procedure.
- [ ] US-11 delivers an actual extraction/matching quality report with counts, denominators, errors and limitations.
- [ ] US-13 delivers a reproducible comparison and adopt/omit decision with structured fallback.
- [ ] US-16 delivers a separate real integration/browser report, defects and retests; skips and mocks are clearly labelled.
- [ ] Startup, migration, test and evaluation commands are documented and reproducible; no secrets or private originals enter shared reports.

Suggested new artifact names for implementation are `docs/testing/sprint-2-dataset-manifest.json`, `docs/testing/sprint-2-quality-report.md`, `docs/testing/sprint-2-semantic-comparison.md` and `docs/testing/sprint-2-e2e-report.md`. These are **planned deliverables, not files created or evaluations executed by this README**. The manifest's exact schema and runner/seed command names must be supplied by BE-64/44/46 when implemented.

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

Add focused Sprint 2 tests for changed behaviour; existing suites alone do not certify new filters, deadlines or evidence mappings. BE-44/46/64 must publish their actual evaluation/seed commands once those runners exist rather than relying on hypothetical commands in documentation.

### 3.3 Contract Decisions to Record Before Integration

| Decision | Proposed direction in this README | Responsible work |
|---|---|---|
| Opportunity field names and compatibility | Nullable source URL/deadline/type; omission preservation on legacy updates | BE-56/58/48 + FE-4 |
| Type vocabulary | Proposed five codes in 2.2.2; confirm supported types | BE-48 + FE-4 |
| Date-range meaning and display zone | Deadline-based half-open ranges; UTC API, explicitly zoned UI | BE-48/58 + FE-4 |
| Expiry/reopening | Shared read-time predicate plus retained closure; explicit revision-checked `reopen` flag on the existing PUT | BE-58 + FE-4/5 |
| Expanded requirements and evidence | Explicit structured criteria and supported education/experience/output mappings | BE-54 + FE-4/5 |
| Semantic adoption | Decide after recorded same-dataset comparison; preserve baseline | BE-46/44/54 |
| Localised validation mapping | Reuse error/reason codes and field paths; add compatible codes only where needed | BE-60 + FE-1 |
| Dataset size and quality targets | Record agreed counts/thresholds before evaluation; do not invent client-approved targets | BE-64/44/46 + QA-1 |

This documentation change does not run application tests, perform migrations, change Jira status or claim Sprint 2 completion. Handover acceptance requires the actual implementation and recorded results above.
