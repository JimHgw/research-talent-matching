# COMP3900 / COMP9900 — H18ABANANA

**🍌 Explainable Two-Sided Research Matching · Sprint 1 Developer Specification and Docker Guide**

An explainable bidirectional matching system for research talent and research opportunities in Australian universities.

For the one-command Docker backend (Flask + Gunicorn + SQLite in one container with persistent storage), see [section 3: Docker Backend Guide](#3-docker-backend-guide). For frontend and backend containers together, use [the integrated Docker guide](docs/docker-integration.md). Docker workflows do not require installing the host development environment.

## Contents

[[_TOC_]]

## Change Log

- **2026-10-10**: Added the US-01 verified-email registration supplement for TALENT and RESEARCH_TEAM, six-digit email codes and email/ID login. See [registration API and SMTP configuration](docs/us01-registration.md).

- **2026-10-10**: Added the complete English Docker backend guide, including setup, one-command builds and startup, account provisioning, frontend integration, configuration, persistent storage, troubleshooting and the dated Docker verification record.
- **2026-10-10**: Implemented US-05 team discovery using current consent and confirmed profiles, shared-field matching, deterministic pagination and reduced team evidence. Included the owner privacy endpoints required for the end-to-end flow. See [US-05 implementation and acceptance](docs/us05-implementation.md).
- **2026-10-08**: Implemented US-02 opportunity management end to end: five Flask endpoints, normalized SQLite tables, team editing/publication, published discovery and explicit conflict comparison in React. See [US-02 implementation and acceptance](docs/us02-implementation.md). Matching remains separate work.
- **2026-10-07**: Implemented US-01 using Flask, SQLite and SQLAlchemy ORM, integrated with the current React frontend. See [backend setup and verification](backend/README.md) for executable commands and the six implemented routes. Other user stories below remain a development specification.
- **2026-10-06**: Organised the complete Sprint 1 developer specification using the aims, iteration tasks, data design, interfaces, testing and acceptance structure of `README_1531.md`; covers US-01–US-09 and 24 HTTP operations.
- **2026-10-06**: Confirmed SQLite + SQLAlchemy ORM; added a proposed physical schema, type mappings and concurrent-write rules.
- **2026-10-06**: The original contract used provisioned-account login. The 2026-10-10 US-01 supplement now adds public email registration; account-name synchronisation remains outside the contract.

> **Document status:** Sections 0–2 are the Sprint 1 development specification, not an implementation completion report. The corresponding API version is `0.1.1-draft`. Proposed interface defaults still require team review; their testing and acceptance checklists describe work to be performed, not tests that have already passed. Section 3 documents the implemented Docker workflow and its explicitly dated verification results.

### Current US-01 Implementation

The current repository provides verified-email registration for both roles in `backend/src/features/auth/registration.py`, and email/ID login, session restoration and logout in `backend/src/features/auth/routes.py`, shared tags and owner-only profile reads/writes in `backend/src/features/profile/routes.py`, and database models/transactions in `backend/src/db/`. Reusable access checks, validation and repository paths live in `backend/src/shared/`. The existing frontend uses these endpoints directly. New talent accounts start with an empty revision-0 profile, no confirmation and private settings. Profile saving uses full replacement, detects stale revisions, preserves no-ops and persists across restarts.

Follow [the backend README](backend/README.md) to initialise SQLite, seed tags, configure SMTP for registration (or provision accounts) and start port 8000 alongside Vite on port 5173. `backend/tests/test_us01.py` and `backend/tests/test_us01_registration.py` check the backend; `backend/tests/test_frontend_integration.py` exercises the current React pages against a real HTTP service when Node and frontend dependencies are installed. Backend dependency manifests and the environment example are also under `backend/`. Profile confirmation, privacy endpoints, documents and matching are separate contributions and are not supplied by US-01.

### Current US-02 Implementation

Research teams can create revision-1 drafts, replace complete content, publish and edit their published opportunities. Both roles can browse published opportunities; only owners can read drafts or modify their own opportunities. `backend/src/features/opportunities/` separates HTTP routes, business rules and persistence, backed by three normalized tables in `backend/src/db/models.py`. `frontend/src/features/opportunities/` supplies the list, editor, requirement controls and details. Stale writes return 409 and the UI preserves local input for explicit comparison. No-op saves and repeated publication preserve revisions. Existing installations run `init-db` again to add the new tables. Tests and maintenance notes are in the [US-02 implementation record](docs/us02-implementation.md).

### Current US-05 Implementation

Teams can discover talent for their own published opportunities and read requirement-level explanations. `backend/src/features/matching/team_repository.py` filters eligible profiles and selects visible fields before the shared matching engine runs; `team_service.py` returns only team-visible evidence. Consent, profile and opportunity changes take effect on the next request. The existing privacy UI now persists settings through owner-only endpoints, with an independent revision and no change to profile confirmation. The discovery UI refreshes on entry, focus or explicit refresh, supports anonymous results and clears stale details. US-03 confirmation and US-04 owner recommendations were already present and are reused. No database migration or API contract change is required. See [the implementation and test record](docs/us05-implementation.md).

## 🫡 0. Aims — Sprint Goals

1. Deliver working frontend and backend workflows for research talent and research teams.
2. Save manual input and user-reviewed document extraction results as structured talent profiles.
3. Implement both talent-to-opportunity and opportunity-to-talent matching, displaying requirements, evidence and statuses individually.
4. Use only the current confirmed profile revision for matching, applying discovery consent and field visibility before team-facing matching.
5. Develop the JavaScript frontend and Python backend against a shared API contract, validating key workflows with reproducible tests.

## 🌈 1. Overview — Project and Scope

### 1.1 Project Background

A research talent's education, courses, research experience, skills, research interests and outputs are often spread across CVs, transcripts and personal descriptions. Research teams need to compare this information against opportunity requirements. This system structures information on both sides to support bidirectional discovery and traceable matching explanations.

The original project focuses on the Australian Go8 university research environment. Following the allocation agreed at the client meeting on 2026-09-30 and the current contract, the BANANA prototype uses two discipline groups: **STEM / BUSINESS**. Matching helps users discover research opportunities; it does not constitute an admission decision, application submission or credential verification.

### 1.2 Sources and How to Use This Document

| Source | Use in this document |
|---|---|
| User-provided screenshot of the [Jira backlog](https://unsw-comp3900-comp9900-26t3.atlassian.net/jira/software/projects/H18ABANANA/boards/103/backlog) | Identifies the nine Sprint 1 parent stories, estimates and dates; this document records the screenshot's scope and does not claim to report live Jira status |
| [Sprint 1 API contract](docs/api/sprint-1-api-contract.md) | Detailed reference for endpoint paths, fields, permissions, errors, states and matching rules |
| [OpenAPI](docs/api/openapi.json), [endpoint index](docs/api/endpoint-index.json), [example index](docs/api/examples/index.json) | Machine-readable interfaces and integration fixtures; the endpoint index includes the implementation subtask associations recorded in the contract |
| `client_meeting_0930.txt` | Client context, discipline allocation, explanation requirements and the manual-entry fallback for the first demonstration |
| Project 109 specification PDF | Background on structured profiles, bidirectional discovery, evidence-based explanations and human review |
| `README_1531.md` | Reference for document organisation and interface presentation; its technology stack, assessment weights, submission commands and iteration schedule do not apply |

Read this document first to understand the sprint tasks, then implement individual endpoints and models using sections 4 and 6 of the contract. This is a developer guide to that contract. Any protocol change must update the contract, OpenAPI, examples and tests together, rather than changing only the README or one implementation.

### 1.3 Sprint 1 Boundaries

This sprint supports provisioned and verified-email `TALENT` and `RESEARCH_TEAM` accounts; one research-team account represents one team. Talent can maintain and confirm profiles, control field visibility and view opportunity recommendations. Research teams can manage their own opportunities and discover talent whose information may be shared.

This sprint excludes password reset, complex identity switching, favourites, semantic vector matching and advanced filters. It also does not add opportunity deletion, unpublishing, team membership management, application or admissions workflows. Implement only US-01–US-09 below; later sprints are not detailed here.

**Document extraction remains part of Sprint 1.** The meeting allowed temporary manual entry for Demo 1 if extraction was not ready, but Jira includes US-09 in this sprint. Retain the complete upload, extraction, review and import workflow. An upload button or static extraction fixture alone does not complete US-09. If the demonstration uses the fallback, clearly record the unfinished work.

## 🐶 2. Sprint 1 — Basic Functionality and Tests

### 2.1 Task — Sprint Requirements

The screenshot shows Sprint 1 running from **3 October to 15 October**, with **9 work items and 36 Story Points**. Points estimate effort; they are not assessment weights or completion percentages. All items in the screenshot are in To Do.

| Story | Jira | Points | Required behaviour for this sprint |
|---|---|---:|---|
| US-01 User Login and Talent Profile Creation | [H18ABANANA-9](https://unsw-comp3900-comp9900-26t3.atlassian.net/browse/H18ABANANA-9) | 3 | Verified-email registration for both roles, email/ID login, sessions and logout; talent can read, edit and save their own structured profiles |
| US-02 Create and Manage Research Opportunities | [H18ABANANA-10](https://unsw-comp3900-comp9900-26t3.atlassian.net/browse/H18ABANANA-10) | 3 | Teams can create drafts, edit, publish and view their own opportunities; published opportunities can be discovered |
| US-03 Review and Confirm Talent Profile Information | [H18ABANANA-11](https://unsw-comp3900-comp9900-26t3.atlassian.net/browse/H18ABANANA-11) | 2 | Users review and confirm the current profile, then reconfirm after content changes |
| US-04 View Recommended Opportunities and Matching Explanations | [H18ABANANA-13](https://unsw-comp3900-comp9900-26t3.atlassian.net/browse/H18ABANANA-13) | 5 | Talent can view ranked opportunity recommendations and requirement-level explanations |
| US-05 Discover Matching Research Talent | [H18ABANANA-12](https://unsw-comp3900-comp9900-26t3.atlassian.net/browse/H18ABANANA-12) | 3 | Teams can view permitted talent lists and explanations for their own published opportunities |
| US-06 Test the Sprint 1 Profile and Matching Flows | [H18ABANANA-14](https://unsw-comp3900-comp9900-26t3.atlassian.net/browse/H18ABANANA-14) | 4 | Test profile, matching, privacy and upload workflows using synthetic or de-identified data, and record actual results |
| US-07 Manage Profile Privacy and Field Visibility | [H18ABANANA-15](https://unsw-comp3900-comp9900-26t3.atlassian.net/browse/H18ABANANA-15) | 3 | Talent actively choose whether to be discoverable and which profile fields teams may view and use for matching |
| US-08 Requirement-Level Matching Results and Evidence | [H18ABANANA-1](https://unsw-comp3900-comp9900-26t3.atlassian.net/browse/H18ABANANA-1) | 5 | Display candidate information, evidence, reasons and Matched / Partial / Gap / Unknown for each requirement |
| US-09 Resume / Transcript Upload and Information Extraction | [H18ABANANA-2](https://unsw-comp3900-comp9900-26t3.atlassian.net/browse/H18ABANANA-2) | 8 | Upload a CV or transcript, query extraction status, review and correct suggestions, import selected sections, then confirm the profile |
| **Total** | **US-01–US-09** | **36** | **26 HTTP operations and their corresponding frontend workflows** |

US-04 and US-05 reuse the matching rules from US-08, but scores may differ between directions because viewing permissions differ. US-06 spans all features and adds no public testing or database-reset endpoint.

### 2.2 Storing Data — Structures and States

#### 2.2.1 Logical Models

The following describes data responsibilities, not existing database tables or directories. **This project has selected SQLite + SQLAlchemy ORM**; the HTTP contract retains its existing structure. Section 2.2.4 proposes the physical schema. Saved data must be retrievable, with revision checks and updates handled transactionally.

| Data | Public structure or key fields | Internal responsibility |
|---|---|---|
| User / Session | `user: {id, displayName, email, role}` or `null`; `csrfToken` | Store accounts, roles and server-side sessions; login credentials must not appear in business response JSON |
| Tag / TagList | `id`, `label`, `kind`, `disciplineGroups`; list shape `{items}` | Shared vocabulary for skills and interests; tag kinds are `SKILL` / `INTEREST` |
| Profile | `talentId`, `revision`, `content`, `confirmation`, `origins`, `updatedAt` | Associate the talent account with profile content, revision, confirmation and provenance |
| Privacy | `revision`, `discoverable`, `visibleFields`, `updatedAt` | Associate settings with the talent account; privacy revisions are independent of profile revisions |
| Document / Extraction | File metadata and processing status; `suggestedSections`, `uncertainFields`, `warnings`, `reviewRequired` | Associate files with their uploader and store originals privately; keep extraction suggestions separate from the saved profile |
| Opportunity | `id`, `revision`, `status`, `content`, `createdAt`, `updatedAt` | Store team ownership internally; clients cannot assign ownership or publication status |
| OwnerMatch / TeamMatch | Opportunity or talent information, `summary`, individual `requirements`, `evaluatedAt` | Calculate using the current confirmed revision and access permissions; invalidate caches when profiles, privacy or opportunities change |

All **eight fields of `ProfileContent` are required**:

| Field | Type and meaning |
|---|---|
| `displayName` | String, at most 100 characters; an empty string is allowed in a draft |
| `disciplineGroup` | `STEM` / `BUSINESS` / `null` |
| `education` | Education records: `id`, `institution`, `qualification`, `discipline`, `startYear`, `endYear` |
| `courses` | Course records: `id`, `name`, `code`, `description`; `code` allows up to 200 characters, or `null` if unknown |
| `researchExperience` | Experience records: `id`, `title`, `organisation`, `description` |
| `skills` | Skill claims: `tagId`, `claim`, `evidenceText`; claim is `HAS` / `DOES_NOT_HAVE` |
| `researchInterests` | Array of `INTEREST` tag IDs |
| `researchOutputs` | Output records: `id`, `title`, `type`, `url`, `description` |

Each of the six arrays allows at most 100 items. Required fields, nullability, lengths and enum constraints for nested records are defined in [ProfileContent](docs/api/sprint-1-api-contract.md#model-profilecontent) and its associated models. The backend generates top-level resource IDs. The frontend may generate stable IDs for education, course, experience, output and requirement records; preserve them during editing and do not substitute array indices.

**Storage structures and response structures are different.** The server needs internal data such as ownership and session records, but must not return database objects directly to the browser. In particular, do not send complete talent profiles to research teams and rely on the frontend to hide fields.

#### 2.2.2 States and Revisions

| Object or operation | Initial state / transition rules |
|---|---|
| Provisioned talent profile | `revision=0`, `displayName=""`, `disciplineGroup=null`, six empty arrays; `UNCONFIRMED`, with confirmation revision and time set to `null` |
| Privacy settings | `revision=0`, `discoverable=false`, `visibleFields=[]` |
| Ordinary profile / privacy / opportunity PUT | Check `expectedRevision` atomically; increment by 1 only for actual changes; an exact no-op preserves the revision |
| Profile content change | Reset to `UNCONFIRMED`, clear `confirmedRevision` and `confirmedAt`, and stop matching against the previously confirmed content |
| Profile confirmation | Require a non-empty name and at least one non-empty academic / research array; set `confirmedRevision=revision` without incrementing the content revision; repeated confirmation preserves the original confirmation time |
| Privacy change | Affects only the privacy revision and subsequent team access; does not invalidate profile confirmation |
| Document processing | `QUEUED → PROCESSING → READY / FAILED`; READY means only that extraction has completed |
| Importing reviewed extraction results | Check `expectedProfileRevision`; every successful import increments the profile revision and invalidates confirmation, even if values are identical |
| Research opportunity | Created as `DRAFT, revision=1`; publication changes it to `PUBLISHED` and increments the revision; repeating publication with the current revision does not increment it again |
| Editing a published opportunity | Remains `PUBLISHED`; must retain at least one valid requirement; subsequent matching uses the new content |

Revision conflicts return `409 REVISION_CONFLICT` with the current revision, without overwriting newer data. The frontend preserves local input, reloads and compares; it must not silently retry an overwrite.

#### 2.2.3 Confirmed Database Technology and Configuration

**SQLite is the database; SQLAlchemy ORM maps Python models to tables and generates parameterised SQL.** Using an ORM still requires explicit columns, primary and foreign keys, unique constraints, relationships and transactions. API JSON models do not replace database design.

- Persist runtime data in a SQLite file on disk. The suggested development URL is `sqlite+pysqlite:///./data/h18abanana.db`, read from environment configuration with relative paths resolved against the project root. Do not commit database files or uploaded originals to Git.
- Use SQLAlchemy 2.x-style `DeclarativeBase`, `Mapped`, `mapped_column` and `relationship`; pin the actual dependency version in the backend dependency manifest.
- Each HTTP request and background extraction task creates its own ORM Session. Do not share it across requests, threads or tasks. An ORM Session is a database unit of work, distinct from the login-session table.
- Enable `PRAGMA foreign_keys=ON` on every database connection, including schema-initialisation connections, and verify that it returns 1 at startup. Declaring SQLite foreign keys alone does not guarantee runtime enforcement; see the [SQLite foreign-key documentation](https://www.sqlite.org/foreignkeys.html).
- Configure real transaction BEGIN behaviour rather than relying on Python sqlite3's legacy transaction mode. Set a bounded lock wait, suggested at five seconds. A busy database is not a revision conflict and must not always return 409. Follow the [SQLAlchemy SQLite documentation](https://docs.sqlalchemy.org/en/20/dialects/sqlite.html) for connection and transaction configuration.

Implement SQLite connection options against the project's pinned Python / SQLAlchemy versions. Perform extraction and other slow operations outside write transactions, opening a short transaction to commit results.

#### 2.2.4 Proposed Tables and ORM Mappings

**The technology choice is confirmed. The following table names, fields and storage layout describe the proposed full Sprint 1 design.** The implemented US-01 subset is defined in `backend/src/db/models.py` using typed SQLAlchemy 2.x mappings and child-to-parent relationships. The proposal below is not a migration or an exact inventory of the current schema. Internal columns use `snake_case`; response serialisation uses the contract's `camelCase` fields.

Type conventions: business IDs use `String(64)`; counts, revisions and positions use `Integer`; flags use `Boolean`; ordinary long text uses `Text`; timestamps use `DateTime`. Convert timestamps to UTC before writing, store consistently as timezone-naive UTC values in SQLite, then explicitly restore UTC on reading and serialise as RFC3339. Never interpret them as local time. Only columns marked `?` below are nullable. PK means primary key, FK foreign key, and UQ unique constraint.

| Table / ORM class | Columns and types | Relationships, constraints and purpose |
|---|---|---|
| `users` / `User` | `id` ID PK; `email`, `email_normalized`, `password_hash`, `display_name`, `role` text; `is_active` boolean; `created_at`, `updated_at` timestamps | `email_normalized` UQ; role limited to TALENT/RESEARCH_TEAM. Proposed provisioning and login policy: trim email whitespace and use lowercase for lookup; store password hashes only |
| `auth_sessions` / `AuthSession` | `token_hash` text PK; `user_id` ID? FK; `csrf_token` text; `created_at`, `expires_at` timestamps; `revoked_at` timestamp? | user_id → users.id, null for anonymous sessions; store a login-token digest rather than its raw value; index user_id and expires_at |
| `talent_profiles` / `TalentProfile` | `talent_id` ID PK; `user_id` ID FK UQ; `display_name` text; `discipline_group` text?; `education`, `courses`, `research_experience`, `research_outputs` JSON arrays; `revision` integer; `confirmation_status` text; `confirmed_revision` integer?; `confirmed_at` timestamp?; `updated_at` timestamp | user_id → users.id, one profile per talent; revision defaults to 0 and is non-negative; discipline limited to STEM/BUSINESS/null; four display-oriented sections retain ordered JSON, with skills and interests linked to tags separately |
| `privacy_settings` / `PrivacySettings` | `talent_id` ID PK/FK; `revision` integer; `discoverable` boolean; `updated_at` timestamp | talent_id → talent_profiles.talent_id, one-to-one; revision defaults to 0, discoverable to false |
| `privacy_visible_fields` / `PrivacyVisibleField` | `talent_id` ID FK; `field` text | Composite PK `(talent_id, field)`; talent_id → privacy_settings.talent_id; CHECK limits field to the eight ProfileField values; no rows means `visibleFields=[]` |
| `tags` / `Tag` | `id` ID PK; `label`, `kind` text | kind limited to SKILL/INTEREST; shared vocabulary, without substituting user-entered display text for relationship keys |
| `tag_discipline_groups` / `TagDisciplineGroup` | `tag_id` ID FK; `discipline_group` text | Composite PK `(tag_id, discipline_group)`; tag_id → tags.id; discipline limited to STEM/BUSINESS |
| `profile_skills` / `ProfileSkill` | `talent_id`, `tag_id` ID FK; `claim`, `evidence_text` text; `position` integer | Composite PK `(talent_id, tag_id)`; references profiles and tags respectively; claim limited to HAS/DOES_NOT_HAVE; position non-negative, determining response-array order |
| `profile_interests` / `ProfileInterest` | `talent_id`, `tag_id` ID FK; `position` integer | Composite PK `(talent_id, tag_id)`; references profiles and tags respectively; position non-negative, determining response-array order |
| `documents` / `Document` | `id` ID PK; `talent_id` ID FK; `kind`, `file_name`, `media_type`, `storage_key`, `status` text; `size_bytes` integer; `error` JSON?; `created_at`, `updated_at` timestamps | talent_id → talent_profiles.talent_id; storage_key UQ locates a private file; kind limited to CV/TRANSCRIPT, status to the four processing states, size_bytes to 1–10485760; file contents are not stored in this table |
| `extractions` / `Extraction` | `document_id` ID PK/FK; `suggested_sections` JSON object; `uncertain_fields`, `warnings` JSON arrays | document_id → documents.id; at most one successful extraction result per document, with no row required during processing; Document supplies status and the serialiser supplies `reviewRequired=true` |
| `profile_origins` / `ProfileOrigin` | `talent_id` ID FK; `field`, `source_type` text; `document_id` ID? FK | Composite PK `(talent_id, field)`; references profile and document; field limited to the six academic sections; MANUAL requires document_id=null, USER_REVIEWED_DOCUMENT requires a document; service layer verifies matching ownership |
| `opportunities` / `Opportunity` | `id` ID PK; `owner_user_id` ID FK; `revision` integer; `status`, `title`, `university`, `discipline_group`, `discipline`, `research_area`, `description` text; `created_at`, `updated_at` timestamps | owner_user_id → users.id; revision starts at 1 and is ≥1, status limited to DRAFT/PUBLISHED; discipline limited to STEM/BUSINESS; service layer verifies the publisher's team role |
| `opportunity_requirements` / `OpportunityRequirement` | `opportunity_id` ID FK; `id` ID; `label`, `kind`, `importance` text; `position` integer | Composite PK `(opportunity_id, id)`; opportunity_id → opportunities.id; kind limited to SKILL/INTEREST, importance to REQUIRED/PREFERRED; position non-negative, preserving requirement order |
| `requirement_tags` / `RequirementTag` | `opportunity_id`, `requirement_id`, `tag_id` IDs; `position` integer | Composite PK `(opportunity_id, requirement_id, tag_id)`; composite FK to opportunity_requirements; tag_id FK → tags.id; position non-negative, preserving tagIds order |

All business columns are NOT NULL unless marked `?`. SQLite's `String(n)` does not replace length validation. Declare `CheckConstraint`, `UniqueConstraint` and `ForeignKeyConstraint`, and enforce contract lengths, ID formats, nested JSON structures, array limits and duplicate-record rules in request validation.

Use CHECK constraints for confirmation consistency: UNCONFIRMED requires null confirmation revision and time; CONFIRMED requires both non-null and confirmed_revision=revision. A FAILED Document requires error; other states require error=null. The service layer checks cross-table business rules inside the transaction, including tag kinds, talent / team roles, source-document ownership and at least one requirement before publication.

Use `JSON` with callable `list` defaults for the four profile arrays and `dict` for extraction objects. Assign complete new values when updating rather than relying on detection of in-place nested-list mutations. Combine related rows on reading to reconstruct the contract's six arrays; a new profile must return `[]` for all six.

Suggested indexes: `documents(talent_id, created_at, id)`, `opportunities(owner_user_id, updated_at, id)`, `opportunities(status, updated_at, id)` and `privacy_settings(discoverable, talent_id)`. Also index FK columns not covered by a PK / UQ prefix. Ordered child tables have unique constraints on `(parent key, position)`; replace arrays by deleting old relationship rows and inserting replacements within the same transaction.

Do not create a permanent match-result / score table in this sprint; calculate from currently authorised data first, avoiding stale scores being treated as facts. Accounts, profiles, documents and opportunities have no public deletion workflow, so FKs restrict deletion by default. Do not configure ORM cascades that delete independent resources by default. Define cleanup order and file handling when deletion is introduced.

#### 2.2.5 Write Transactions and SQL Semantics

Profile content, related arrays, provenance, revision and confirmation state must commit or roll back together. Provision a talent's User, TalentProfile and PrivacySettings in one transaction; a provisioned team account does not receive a talent profile. Background extraction must also save Extraction and change Document to READY in one transaction.

Use short, service-controlled write transactions, acquiring the SQLite write transaction (`BEGIN IMMEDIATE`) before reads, authorisation and revision comparison. This prevents ordinary no-op saves, confirmation and publication from interleaving with another write. Only the database transaction adapter should begin the transaction, once; do not issue BEGIN inside an already active ORM transaction. Implement the integration for the pinned driver version. All write paths follow the same convention, while read transactions maintain a consistent data snapshot.

The following parameterised SQL illustrates updating the profile revision **after determining that the current content actually changes**. It is not a complete save function; other field, child-table and provenance updates belong in the same transaction:

```sql
UPDATE talent_profiles
SET display_name = :display_name,
    revision = revision + 1,
    confirmation_status = 'UNCONFIRMED',
    confirmed_revision = NULL,
    confirmed_at = NULL,
    updated_at = :updated_at
WHERE talent_id = :talent_id
  AND user_id = :current_user_id
  AND revision = :expected_revision;
```

Execute the equivalent conditional update through the ORM with bound parameters and check the affected-row count. Return 409 only when authorisation succeeds, the resource exists and its revision is actually stale; not every zero-row update is a revision conflict. Ordinary no-op PUT preserves the revision; imports always increment it; confirmation preserves the content revision; initial draft publication increments the opportunity revision.

Do not directly enable an ORM strategy that increments the public revision on every UPDATE, because confirmation would incorrectly increment it. If using `version_id_col`, explicitly handle these business differences; automatic checks also do not cover all bulk updates. See the [SQLAlchemy version-counter documentation](https://docs.sqlalchemy.org/en/20/orm/versioning.html).

Add database acceptance checks: persistence after restart, foreign keys enabled on every connection, duplicate emails / skill relationships rejected, invalid confirmation combinations rejected, no partial writes after transaction failure, and two independent connections unable to overwrite successfully using the same stale revision. Manage empty-database initialisation separately from subsequent migrations; `create_all()` does not replace migrations of existing tables.

### 2.3 Implementing Features — Sequence and Responsibilities

Work in small, verifiable features, completing one end-to-end workflow before extending another:

1. Agree on the contract defaults and prepare provisioned talent / team accounts, shared tags, synthetic profiles and opportunity data.
2. Implement sessions, login and permissions, followed by manual profile saving, confirmation and privacy settings.
3. Implement opportunity creation, editing and publication, then connect talent recommendations and team discovery.
4. Implement US-08 statuses, evidence, scoring and sorting; apply privacy before team-facing scoring.
5. Connect document upload, asynchronous extraction and reviewed imports, retaining manual entry.
6. Execute US-06 acceptance cases, fix defects and prepare the complete Demo 1.

| Module | Main endpoint numbers | Frontend responsibility | Python backend responsibility |
|---|---|---|---|
| FE-1 Layout and login | 01–03 | Login page, session restoration, logout and account-cache cleanup | Sessions, authentication, role and CSRF checks |
| FE-2 Profiles, review and privacy | 04–09, 14 | Forms, review and confirmation, conflict prompts, visible-field selection | Validation, storage, revision control, confirmation and privacy |
| FE-3 Opportunity management | 04, 16–20 | Create / edit forms, draft and publication pages | Team ownership, full replacement and publication prerequisites |
| FE-4 Bidirectional matching and explanations | 21–24 | Ranked lists, requirement-level explanations and empty states | Permission filtering, four statuses, evidence, scores and sorting |
| FE-5 Documents and extraction review | 10–15, followed by 05–07 | Upload, status polling, corrections and selected-section previews | Private files, extraction processing, provenance and atomic imports |

This table divides responsibilities; it does not assign work to named team members. Backend modules may separate authentication, profiles, opportunities, documents and matching; the team chooses filenames and frameworks. The authentication module may retain the name `auth.py`, while HTTP routing should remain separate from pure matching rules and storage details.

### 2.4 Testing Guidelines — Testing Principles

- **Test behaviour.** Check responses, state transitions, permissions and subsequent reads without depending on internal function or table names.
- **Cover success, failure and boundaries.** Test empty profiles and lists, repeated confirmation, revision conflicts, unknown fields, duplicate IDs, incorrect tag types, incorrect roles and unauthorised resource access.
- **Isolate tests.** Use independent data or controlled setup for each test; resets belong only in the test environment, with no public `/clear` endpoint.
- **Verify each layer.** Use deterministic unit tests for matching rules, API tests for requests, responses and permissions, and browser integration tests for complete user workflows and cache cleanup.
- **Fixtures are inputs, not proof of passing tests.** The [34 JSON fixtures](docs/api/examples/index.json) support mocks and protocol checks. Real authentication, persistence, file processing and permissions still require backend integration tests.
- **Record reproducible results.** US-06 records must include at least the story ID, initial data, steps, expected result, actual result, pass / fail status, associated defect and retest result.

### 2.5 Sprint 1 Interface — API Specification

#### 2.5.1 Shared Conventions

- All paths below omit the common `/api/v1` prefix. JSON uses UTF-8, `camelCase` fields and the specified enum spelling and case.
- All business IDs match `^[A-Za-z0-9_-]{1,64}$`; timestamps are UTC RFC3339 strings.
- Successful responses return the business object directly, without a `data` / `success` wrapper; 204 has no response body.
- Required fields that allow `null` must still be present. Reject unknown fields, duplicate record IDs and incorrect types. Render plain text as text.
- Every POST / PUT includes `X-CSRF-Token`; the backend checks both the session and allowed Origin.
- Request bodies default to `application/json`; uploads use `multipart/form-data`; original-file downloads return binary data.
- Pagination defaults to `page=1`, `pageSize=20`; page must be at least 1 and pageSize an integer from 1–100. Invalid values return 422.
- Paginated responses use `{items, page, pageSize, total}`. No results or a page beyond the last page returns 200 with `items: []`; total counts only accessible records.
- Opportunities sort by `updatedAt` descending, then ID ascending; documents sort by `createdAt` descending, then ID ascending. Matching order is defined in 2.7.
- After a timeout, read the current state before deciding whether to retry a POST. This version provides no `Idempotency-Key` or creation deduplication guarantee.

The following follows README_1531's function, parameter, return and error format. Numbering matches the contract, and model names refer to section 6 of the contract. Shared errors are listed in 2.5.6; the tables also highlight key business errors. Follow each endpoint link for its complete status-code list.

#### 2.5.2 Sessions, Tags, Talent Profiles and Privacy

| Number / endpoint and purpose | Request parameters or body | Success response | Permissions and key errors |
|---|---|---|---|
| [01](docs/api/sprint-1-api-contract.md#api-01) `GET /auth/session`: read session and CSRF token | None | **200 Session**: `{user, csrfToken}` | Anonymous access allowed; logged-out users receive `user=null`, not 401 |
| [02](docs/api/sprint-1-api-contract.md#api-02) `POST /auth/login`: log in using email or account ID | `{identifier, password}` or legacy `{email, password}`; obtain anonymous CSRF first | **200 Session**, with a new Cookie | Invalid credentials: 401 `INVALID_CREDENTIALS`; rate limit: 429 |
| [25](docs/api/sprint-1-api-contract.md#api-25) `POST /auth/register/code`: send six-digit email code | `{email}`; anonymous session, CSRF and allowed Origin | **202 RegistrationCodeResponse**: `{expiresAt, resendAfterSeconds}` | Email in use: 409; cooldown/limits: 429; delivery unavailable: 503 |
| [26](docs/api/sprint-1-api-contract.md#api-26) `POST /auth/register`: create verified account | `{email, code, password, displayName, role}`; same session and CSRF | **201 Session**, new cookie and server-assigned `user.id` | Both roles; invalid/expired code: 422; email in use: 409; exhausted attempts: 429 |
| [03](docs/api/sprint-1-api-contract.md#api-03) `POST /auth/logout`: log out | No request body | **204**, revokes session and clears Cookie | Either signed-in role |
| [04](docs/api/sprint-1-api-contract.md#api-04) `GET /tags`: read shared tags | Optional query: `kind=SKILL/INTEREST` | **200 TagList**: `{items}`, without pagination | Either signed-in role; invalid parameters: 422 |
| [05](docs/api/sprint-1-api-contract.md#api-05) `GET /me/profile`: read own profile | None | **200 Profile** | TALENT owner; a new profile returns its initial object, not 404 |
| [06](docs/api/sprint-1-api-contract.md#api-06) `PUT /me/profile`: save complete profile | **ProfileWrite**: `{expectedRevision, content}`, including all eight content fields | **200 Profile** | TALENT owner; stale revision: 409; invalid content: 422 |
| [07](docs/api/sprint-1-api-contract.md#api-07) `POST /me/profile/confirmation`: confirm current profile | **RevisionRequest**: `{expectedRevision}` | **200 Profile** | TALENT owner; stale revision: 409; unmet confirmation prerequisites: 422 |
| [08](docs/api/sprint-1-api-contract.md#api-08) `GET /me/privacy`: read privacy settings | None | **200 Privacy** | TALENT owner |
| [09](docs/api/sprint-1-api-contract.md#api-09) `PUT /me/privacy`: save privacy settings | **PrivacyWrite**: `{expectedRevision, discoverable, visibleFields}` | **200 Privacy** | TALENT owner; stale revision: 409; invalid / duplicate fields: 422 |

Login `password` accepts 1–200 characters; registration passwords require 8–200. Login takes exactly one of `identifier` (email or ID) and legacy `email`. Registration selects TALENT or RESEARCH_TEAM and issues an independent ID. See the [US-01 supplement](docs/us01-registration.md) for verification limits and SMTP setup. During login, the server reads the role from the account; the login request cannot select it. `visibleFields` accepts only the eight ProfileContent fields in 2.2, with no authorisation for email, original files or individual skill records.

Profile PUT performs **full replacement**: include unedited content, and use `[]` to clear a section. Actually changed academic sections receive `MANUAL` provenance and `documentId=null`; unchanged sections retain their provenance. Do not accept client-supplied confirmation state or fabricated provenance.

#### 2.5.3 Document Upload, Extraction, Review and Import

| Number / endpoint and purpose | Request parameters or body | Success response | Permissions and key errors |
|---|---|---|---|
| [10](docs/api/sprint-1-api-contract.md#api-10) `GET /me/documents`: list own documents | Query: `page`, `pageSize` | **200 DocumentPage** | TALENT owner; metadata only, with no public download URLs |
| [11](docs/api/sprint-1-api-contract.md#api-11) `POST /me/documents`: upload and start extraction | FormData: `file` + `kind=CV/TRANSCRIPT` | **202 Document**, initially `QUEUED` | TALENT owner; too large: 413; unsupported format: 415; rate limit: 429 |
| [12](docs/api/sprint-1-api-contract.md#api-12) `GET /me/documents/{documentId}`: read processing status | Path: `documentId` | **200 Document** | Document owner; missing / another user's document: 404 |
| [13](docs/api/sprint-1-api-contract.md#api-13) `GET /me/documents/{documentId}/extraction`: read review suggestions | Path: `documentId` | **200 Extraction** | Document owner; pending extraction: 409 `EXTRACTION_NOT_READY`; failed extraction: 422 `EXTRACTION_FAILED` |
| [14](docs/api/sprint-1-api-contract.md#api-14) `POST /me/documents/{documentId}/apply`: import reviewed content | Path: `documentId`; **ApplyExtractionRequest**: `{expectedProfileRevision, sections}` | **200 Profile**, with a new revision and unconfirmed state | Document owner; revision conflict / not ready: 409; failed extraction / invalid sections: 422 |
| [15](docs/api/sprint-1-api-contract.md#api-15) `GET /me/documents/{documentId}/file`: download original file | Path: `documentId` | **200 binary file** | Document owner; teams cannot download; missing / another user's document: 404 |

Uploads accept non-empty **PDF / DOCX files, up to 10 MiB (10,485,760 bytes)**, excluding legacy `.doc`. The backend validates actual content, format and size, rather than checking the extension alone. The frontend must not manually set Content-Type when using FormData.

Poll status every two seconds while the page is open, stopping at READY / FAILED. After 60 seconds, pause automatic polling and offer manual refresh. A frontend timeout must not change the backend status to FAILED. A status response of 200 + FAILED successfully reports a failed processing state; requesting the failed extraction result instead returns 422.

Extraction always returns `reviewRequired` as `true`. Put uncertain information in `uncertainFields` (`UNKNOWN` / `NOT_RECOGNISED`); do not automatically infer positive or negative skill claims.

Imported `sections` may select only the six academic / research arrays and must contain at least one section: **replace submitted sections only, preserve omitted sections, and clear a section when explicitly given `[]`**. Users may correct suggestions. To merge existing skills, the frontend combines them by tagId, lets the user review them, then submits the complete skills array. Record `USER_REVIEWED_DOCUMENT` provenance after import and require a separate confirmation.

Store original files privately and recheck ownership on every download. Use the correct media type, `Content-Disposition: attachment` and `X-Content-Type-Options: nosniff`. Preserve manual entry after extraction failure. This sprint has no dedicated retry endpoint; a new upload starts a new attempt.

#### 2.5.4 Research Opportunity Management

| Number / endpoint and purpose | Request parameters or body | Success response | Permissions and key errors |
|---|---|---|---|
| [16](docs/api/sprint-1-api-contract.md#api-16) `GET /opportunities`: list opportunities | Query: `scope=published/mine`, default published; `page`, `pageSize` | **200 OpportunityPage** | Either signed-in role; mine is team-only, otherwise 403 |
| [17](docs/api/sprint-1-api-contract.md#api-17) `POST /opportunities`: create a draft | **OpportunityContent**, submitted directly as the content object | **201 Opportunity**, `DRAFT, revision=1` | RESEARCH_TEAM; server assigns ID and ownership |
| [18](docs/api/sprint-1-api-contract.md#api-18) `GET /opportunities/{opportunityId}`: read opportunity details | Path: `opportunityId` | **200 Opportunity** | Signed-in users may read published content; drafts are owner-team-only, otherwise 404 |
| [19](docs/api/sprint-1-api-contract.md#api-19) `PUT /opportunities/{opportunityId}`: replace complete content | Path: `opportunityId`; **OpportunityWrite**: `{expectedRevision, content}` | **200 Opportunity** | Owner team; another team: 404; stale revision: 409; invalid content: 422 |
| [20](docs/api/sprint-1-api-contract.md#api-20) `POST /opportunities/{opportunityId}/publish`: publish | Path: `opportunityId`; `{expectedRevision}` | **200 Opportunity**, `PUBLISHED` | Owner team; stale revision: 409; no valid requirements: 422 |

`OpportunityContent` must include `title`, `university`, `disciplineGroup`, `discipline`, `researchArea`, `description` and `requirements`. Drafts may have `requirements=[]`, but basic text fields are still required. Published opportunities must retain at least one valid requirement.

Each requirement includes `id`, `label`, `kind=SKILL/INTEREST`, `importance=REQUIRED/PREFERRED` and `tagIds`. Allow at most 50 requirements, with 1–20 unique tags of the correct kind per requirement. Tags within a requirement form an **AND** group. Do not independently add fields such as opportunity type, funding or timing merely because the original project mentions them; they are absent from this contract.

#### 2.5.5 Bidirectional Matching and Requirement-Level Explanations

| Number / endpoint and purpose | Request parameters | Success response | Permissions and key errors |
|---|---|---|---|
| [21](docs/api/sprint-1-api-contract.md#api-21) `GET /me/recommendations`: personal opportunity ranking | Query: `page`, `pageSize` | **200 RecommendationPage** | TALENT owner; current profile unconfirmed: 409 `PROFILE_UNCONFIRMED` |
| [22](docs/api/sprint-1-api-contract.md#api-22) `GET /me/opportunity-matches/{opportunityId}`: personal match explanation | Path: `opportunityId` | **200 OwnerMatch** | TALENT owner; unconfirmed: 409; unpublished / missing opportunity: 404 |
| [23](docs/api/sprint-1-api-contract.md#api-23) `GET /opportunities/{opportunityId}/talent-matches`: talent ranking | Path: `opportunityId`; query: `page`, `pageSize` | **200 TalentMatchPage** | Owner of the published opportunity; unpublished / another team's opportunity: 404 |
| [24](docs/api/sprint-1-api-contract.md#api-24) `GET /opportunities/{opportunityId}/talent-matches/{talentId}`: visible talent information and explanations | Path: `opportunityId`, `talentId` | **200 TeamMatch** | Owner of the published opportunity; talent opted out / current profile unconfirmed: 404 |

`RecommendationPage.items` contains `rank, opportunity, summary`; `TalentMatchPage.items` contains `rank, talent, summary`. Details return the complete `requirement`, `status`, `reasonCode`, `reason` and `evidence` for each item. The frontend displays individual results, not just an overall score.

The talent owner's details use **OwnerEvidence**: `field, recordId, valueSummary, confirmedRevision, sourceType, documentId`. Teams receive **TeamEvidence**: only `field, recordId, valueSummary`. Talent information uses **VisibleProfile**: `{talentId, fields}`, omitting hidden keys entirely.

#### 2.5.6 Errors — Shared Error Format

```json
{
  "error": {
    "code": "REVISION_CONFLICT",
    "message": "Reload the latest resource before saving.",
    "fieldErrors": [],
    "currentRevision": 4
  },
  "requestId": "req_demo_001"
}
```

The frontend branches on `error.code`, not message wording. `fieldErrors` is always present; `currentRevision` is included only for revision conflicts. Field paths use a format such as `content.education[0].institution`.

| HTTP | error.code | Frontend action |
|---|---|---|
| 400 | `BAD_REQUEST` | Request cannot be parsed; preserve input and show the failure |
| 401 | `UNAUTHENTICATED` / `INVALID_CREDENTIALS` | Clear expired-session caches and return to login; use a generic message for invalid credentials |
| 403 | `FORBIDDEN` / `CSRF_INVALID` | Deny unauthorised access; after a CSRF error, reread the session and let the user retry without automatically replaying a mutation |
| 404 | `NOT_FOUND` | Resource is missing or inaccessible; refresh the list |
| 405 | `BAD_REQUEST` | HTTP method is unsupported; use a documented method listed in the `Allow` response header |
| 409 | `REVISION_CONFLICT` / `PROFILE_UNCONFIRMED` / `EXTRACTION_NOT_READY` | Compare revisions, request profile confirmation or wait for extraction, respectively |
| 413 | `UPLOAD_TOO_LARGE` | Explain the 10 MiB limit |
| 415 | `UNSUPPORTED_FILE_TYPE` / `UNSUPPORTED_MEDIA_TYPE` | Select a supported file or correct the request media type |
| 422 | `VALIDATION_ERROR` / `EXTRACTION_FAILED` | Display field errors or offer manual entry |
| 429 | `RATE_LIMITED` | Stop repeated requests and ask the user to try later |
| 500 | `INTERNAL_ERROR` | Preserve input and requestId for investigation |

Do not return stack traces, database errors, server paths, passwords or session credentials. Convert Python framework validation errors to the same structure. `Document.error` contains only ErrorDetail, without a nested requestId.

### 2.6 Authorisation — Sessions, Roles and Privacy

#### 2.6.1 Cookie Sessions

```text
GET /auth/session       → Create / read anonymous session and return csrfToken
POST /auth/login        → Include Cookie + CSRF; rotate both after login
GET /auth/session       → Return current User; session ID remains in Cookie only
POST /auth/logout       → Revoke server session, clear Cookie and return 204
```

The cookie is named `h18_session`, with `HttpOnly; SameSite=Lax; Path=/` and no Domain attribute. Use Secure on HTTPS; local HTTP may omit it. Browser requests use `credentials: 'include'`. Replace the CSRF token after successful login; never put the login session value in localStorage, URLs or JSON.

`user.id` and `talentId` identify resources and cannot replace authentication; `csrfToken` is not a login credential either. The backend determines the current account, role and resource owner from the session, rather than trusting client-supplied owner, role or confirmation state. Session expiry and account provisioning are implementation configuration; this contract does not prescribe fixed values.

Private endpoints return 401 without a valid session, 403 for an incorrect role and 404 for missing or inaccessible resources. Personalised responses use `Cache-Control: no-store`. Clear frontend profile, document and recommendation caches when logging out or signing in as another account.

#### 2.6.2 Filter Permissions Before Calculating Team Matches

Process team requests in this order:

1. Verify that the team owns the published opportunity.
2. Exclude talent with `discoverable=false` or an unconfirmed current revision.
3. Select the information permitted by `visibleFields` for this request.
4. Generate statuses, scores and explanations using only those fields, then sort, paginate and calculate total.
5. Recheck every detail request and invalidate stale result caches after profile, opportunity or privacy changes.

Hidden fields must not affect team-visible scores, rankings or explanations. Use a generic "insufficient evidence" explanation for both missing and hidden evidence; do not say "this user hid Python". Display anonymous talent when `displayName` is not visible. Even with `visibleFields=[]`, a currently confirmed talent who permits discovery may appear anonymously with UNKNOWN results.

Owner recommendations may use the talent's complete confirmed profile, even when `discoverable=false`. Team responses must never expose login email, original filenames, document IDs, download links, raw extracted text or provenance information. Revoking discovery affects subsequent requests: the talent disappears from the next list, and an old detail URL returns 404. Refetch when entering, refreshing or refocusing the team page.

### 2.7 Matching Rules — Statuses, Evidence and Ranking

This sprint uses algorithm version `tag-coverage-v1`. Evaluate SKILL / INTEREST tags using only **the current confirmed information authorised for this request**. Do not independently infer skills from free-text course or project descriptions.

Evaluate each AND requirement in this priority order:

| Priority | Condition | API status / display label | reasonCode |
|---:|---|---|---|
| 1 | Any requested skill has an explicit `DOES_NOT_HAVE` claim | `GAP` / Gap | `EXPLICIT_NEGATIVE_CLAIM` |
| 2 | Every tag has affirmative evidence | `MATCHED` / Matched | `ALL_TAGS_SUPPORTED` |
| 3 | Some tags have affirmative evidence and the rest are unknown | `PARTIAL` / Partial | `SOME_TAGS_SUPPORTED` |
| 4 | No usable affirmative or explicit negative evidence | `UNKNOWN` / Unknown | `INSUFFICIENT_EVIDENCE` |

For Python+SQL, having Python and explicitly not having SQL produces GAP; having Python with SQL unknown produces PARTIAL; no information for either produces UNKNOWN. Missing uploads, omitted skills or hidden skills must not automatically become GAP. Unconfirmed profiles do not enter matching.

MATCHED / PARTIAL cite actual supporting evidence; GAP cites the explicit negative claim; UNKNOWN has `evidence=[]`. When `evidenceText` is empty, cite only the confirmed tag claim without inventing experience. Interest evidence.recordId uses tagId.

```text
Requirement weight w: REQUIRED = 2, PREFERRED = 1
Status value v: MATCHED = 1, PARTIAL = 0.5, GAP = 0, UNKNOWN = 0

score = round_half_up(100 × sum(w × v) / sum(w), 2)
unknownWeightPercent = round_half_up(100 × sum(w for UNKNOWN requirements) / sum(w), 2)
requiredGapCount = count(requirements where importance=REQUIRED and status=GAP)
```

The backend uses decimal half-up rounding to two places; the frontend displays the returned values. When total weight is zero, return `null` for both percentages and `evaluationStatus=INSUFFICIENT_CRITERIA`, never NaN. Normal evaluations use `EVALUATED`. Publication rejects empty requirements; this branch protects against legacy data.

Sort by **score descending → unknownWeightPercent ascending → object ID ascending**, placing null scores last. Paginate after sorting. `rank` is global and does not restart on each page. REQUIRED increases weight and contributes to requiredGapCount; this sprint does not automatically exclude talent because of a GAP.

The contract's four-status example has Python REQUIRED as MATCHED, Python+SQL REQUIRED as PARTIAL, interviews PREFERRED as GAP and R PREFERRED as UNKNOWN. It produces **score=50, unknownWeightPercent=16.67, requiredGapCount=0**. If the talent shares only their name, all four team-facing results are UNKNOWN, with score=0 and unknownWeightPercent=100. Scores represent evidence coverage, not admission probability.

### 2.8 Working in Parallel — Collaboration and Integration

The frontend builds mocks using [OpenAPI](docs/api/openapi.json) and the [fixtures](docs/api/examples/index.json), while the backend implements the same protocol. The server is authoritative for identity, confirmation, evidence selection, permission filtering and scoring. The frontend requests `/api/v1`; a development proxy forwards requests to Python while preserving Origin. The team configures the actual listening address.

Use a separate branch and Merge Request for each feature where practical, linking the Jira item and relevant test results. Coordinate API changes by updating the contract version, OpenAPI, examples and tests on both sides together. Before locking the version, review defaults in contract section 1.3, including cookie sessions, whole-profile confirmation, the 10 MiB upload limit and scoring weights.

**Manual profile workflow:**

```text
Read session → Talent login → Read tags and profile
→ PUT complete profile → User review → POST confirmation of current revision
→ GET recommendations → GET requirement-level match explanations
```

**Document extraction workflow:**

```text
Upload → Query processing status → Read extraction suggestions once READY
→ User selects, corrects and reviews the sections to replace
→ Read current profile revision → apply import → Review and confirm profile again
→ Refetch recommendations
```

**Team discovery and privacy workflow:**

```text
Talent confirms profile → Actively enables discoverable and selects visible fields
Team login → Read own opportunities → Create draft → Edit → Publish
→ Read talent rankings and explanations
Talent revokes discovery → Team refresh no longer lists the talent; old details return 404
```

IDs, emails and passwords in fixtures are fictional, not provisioned test accounts. Fixtures illustrate individual requests / responses; do not assume that all revisions form a continuous database history. Use the revision actually read when making requests.

### 2.9 Acceptance Criteria — Required Outcomes

These are Sprint 1 functional acceptance criteria; COMP1531 grading weights and MR-count requirements do not apply.

| Acceptance case | Related stories | Required observable result |
|---|---|---|
| Anonymous sessions, registration and email/ID login | US-01 | Anonymous session returns 200 + user=null; private requests return 401; both roles log in correctly; login rotates the session and logout invalidates it |
| Profile initialisation and saving | US-01 | New profile starts at revision 0, unconfirmed and not discoverable; saved content survives refresh; full replacement preserves unedited fields |
| Review, repeated confirmation and reconfirmation | US-03 | Empty profiles cannot be confirmed; repeated confirmation preserves revision / original confirmation time; actual edits cause recommendations to return 409 until reconfirmed |
| Concurrent saves | US-01, US-02, US-07 | Profiles, privacy and opportunities reject stale revisions with 409; newer data remains intact; ordinary no-op saves preserve the revision |
| Opportunity lifecycle | US-02 | Talent cannot view drafts or receive them as recommendations; publication requires requirements; owner teams can edit published content and other teams cannot modify it |
| Talent recommendations | US-04 | Use the current confirmed profile and published opportunities; disabling discoverable does not affect owner recommendations; no opportunities returns 200 with an empty list |
| Team discovery | US-05 | Only currently confirmed, opted-in talent appear; no visible fields may still produce anonymous UNKNOWN results; total is calculated after permission filtering |
| Four statuses and evidence | US-08 | The four-status fixture matches 2.7; explicit negative claims take priority; missing data is not GAP; UNKNOWN has no evidence; no invented course / project facts |
| Ranking, pagination and boundaries | US-04, US-05, US-08 | Deterministic ordering, continuous rank across pages, invalid pagination returns 422 and out-of-range pages are empty; zero requirements safely return null scores |
| Privacy changes | US-07 | Privacy-only changes preserve profile confirmation; hiding skills changes team scores and explanations, and hidden keys are omitted from responses |
| Discovery revocation and caching | US-05, US-07 | The next list excludes the talent and old details return 404; opportunity / profile / privacy changes do not leave stale results in use |
| Original-file access | US-07, US-09 | Uploaders can download; other talent and teams are denied; team responses contain no email, file or provenance information |
| Upload and processing | US-09 | PDF / DOCX acceptance returns 202 with queryable status; oversized files return 413, unsupported formats 415; READY or FAILED can be observed |
| Uncertain or failed extraction | US-09 | No automatic confirmation or profile overwrite; manual entry remains available; stopping automatic polling after 60 seconds does not imply backend failure |
| Reviewed imports | US-03, US-09 | Replace selected sections only, preserve omitted ones and clear explicit empty arrays; imports increment revision and require reconfirmation; stale imports return 409 |
| Authentication, CSRF and account changes | US-01, US-07 | Mutations without CSRF / with an incorrect Origin are rejected; knowing an ID cannot bypass permissions; account changes leave no previous-account cache |
| Protocol and errors | US-06 and related stories | Paths, fields, enums and response statuses match the contract; every error follows the shared structure without leaking internal information |
| Test records and defect retesting | US-06 | Record reproducible steps and actual results; link failures to Jira and record retests after fixes |

### 2.10 Dryrun — Pre-Demonstration Checks

The repository contains the runnable US-01 Flask backend, React frontend, dependency manifests, setup scripts and automated tests. Follow the [backend setup and verification guide](backend/README.md) and [frontend README](frontend/README.md) for environment installation, database initialisation, account provisioning, startup and test commands. On Windows, run the repository-root `setup.ps1`; on macOS/Linux, install Python 3.12+ and Node.js 22.13+ with npm, then run `sh setup.sh`. Both entry points install project dependencies and verify both suites with required real HTTP integration (`pytest --require-frontend`). The two Windows installer tests may skip on macOS/Linux; the real HTTP test must pass. Do not put real passwords in the README.

For a Docker backend, use [section 3](#3-docker-backend-guide) instead of the host backend installation steps above. The existing host setup is still needed when developing or running the frontend locally.

Current real-backend verification covers both-role email registration, SMTP delivery to a local test server, email/ID login, sessions, tags, manual profiles, confirmation, opportunity management, owner recommendations, privacy and US-05 team discovery. Document upload/extraction remains unimplemented. The full Sprint 1 checks below are acceptance targets; passing the current suites does not complete those targets. Frontend tests using synthetic responses must be distinguished from the real HTTP integration tests.

Before the demonstration, complete these steps:

1. Initialise isolated test data, including at least two independent talent accounts and two team accounts to verify cross-account and cross-team access.
2. Use a talent account to save a manual profile, confirm it, view recommendations and inspect requirement-level explanations.
3. Upload test PDF / DOCX files and demonstrate processing, review and correction, import and reconfirmation; also check manual entry after failure.
4. Use a team account to create and publish an opportunity, then view talent rankings and visible information.
5. Change talent field visibility and demonstrate changes to team scores and explanations; then revoke discovery and verify that old details are inaccessible.
6. Check concurrent stale saves, all four match statuses, empty lists, oversized files, unauthorised access and cache cleanup after logout.
7. Record actual results under US-06 and clearly identify mocks, incomplete features or temporary fallbacks in the demonstration.

Useful fixtures:

| Scenario | Repository fixtures |
|---|---|
| Saving, confirmation and privacy | [profile-write.json](docs/api/examples/profile-write.json), [confirm-request.json](docs/api/examples/confirm-request.json), [privacy-write.json](docs/api/examples/privacy-write.json) |
| Opportunity creation | [opportunity-create.json](docs/api/examples/opportunity-create.json) |
| Extraction and import | [extraction-ready.json](docs/api/examples/extraction-ready.json), [apply-extraction-request.json](docs/api/examples/apply-extraction-request.json) |
| Four match statuses | [owner-match-four-statuses.json](docs/api/examples/owner-match-four-statuses.json) |
| Team results with hidden skills | [team-match-hidden-skills.json](docs/api/examples/team-match-hidden-skills.json) |
| Conflict and unconfirmed-profile errors | [error-revision-conflict.json](docs/api/examples/error-revision-conflict.json), [error-unconfirmed.json](docs/api/examples/error-unconfirmed.json) |

### 2.11 Sprint 1 Delivery — Delivery Checklist

- [ ] Frontend behaviour and corresponding backend endpoints for US-01–US-09 are implemented, with traceable MR, test or demonstration evidence in Jira.
- [ ] All 26 HTTP operations match the `0.1.1-draft` contract or a version updated jointly by the team.
- [ ] Manual talent entry, reviewed document imports, team opportunity management and bidirectional explanations can be demonstrated.
- [ ] Confirmation, privacy, ownership, revision-conflict and session rules have passed actual tests.
- [ ] US-06 records cover successful flows, errors, boundaries, permissions and defect retesting.
- [ ] Actual installation, startup, data initialisation and test commands are included in the operating instructions.
- [ ] Demonstration data contains no unauthorised real personal information; accounts and secrets are supplied through appropriate channels.
- [ ] Documentation clearly identifies completed work, known limitations, mocks and manual fallbacks without marking planned features as complete.

The Jira screenshot's 15 October date is the sprint end date. Official demonstration dates, submission channels and course deadlines follow course and team announcements; this document does not infer additional deadlines.

## 3. Docker Backend Guide

The root Compose configuration can now run frontend and backend containers
together. See [the integrated Docker guide](docs/docker-integration.md) for the
shared network, startup, verification and data-volume preservation. The
`docker-backend.sh` / `docker-backend.ps1` launchers below still start only the
backend. Their `down` action removes the whole Compose project's containers and
network, including its frontend if running, while preserving the data volume.

The backend uses **Flask + SQLAlchemy + SQLite**, with **Gunicorn** serving the Flask application inside the container. The launcher builds the backend image and starts the container automatically. The backend accesses SQLite directly; PostgreSQL, MySQL and a separate database container are not required.

Sections 0–2 above contain the sprint requirements, data models and interface specification. For native development without Docker, see [backend/README.md](backend/README.md).

### 3.1 Prerequisites

- **Windows / macOS:** Install and start [Docker Desktop](https://docs.docker.com/desktop/). On Windows, use **Linux containers** mode.
- **Linux:** Install and start Docker Engine, install the Docker Compose plugin, and ensure your user can access Docker.
- Use a recent Compose version that supports `docker compose up --wait --wait-timeout`.
- The first build requires internet access to download the Python base image and backend dependencies.
- The default host port is `8000`. Stop any existing native Flask server using that port, or change the port as described in section 3.5.

To run only the Docker backend, you do not need to run `setup.ps1` / `setup.sh` first or install Python, Node.js or Python dependencies on the host. Frontend development still uses the existing host setup process.

### 3.2 Build and Start with One Command

Run the appropriate command from the repository root.

**Windows PowerShell:**

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\docker-backend.ps1
```

**macOS / Linux:**

```sh
sh docker-backend.sh
```

You can also invoke the script by its absolute path from another directory. The launcher locates the repository relative to its own location and supports paths containing spaces.

The default action is `up`. The launcher performs these steps:

1. Checks Docker, Compose and the Linux container environment.
2. Builds the `banana-backend:local` image using `backend/Dockerfile`.
3. Creates or reuses the named SQLite data volume and starts one `backend` container.
4. Runs `init-db` and `seed-tags` through the Flask CLI during container startup, then serves the Flask application through Gunicorn.
5. Waits up to 120 seconds for the health check to pass. Image build time is separate from this readiness timeout.

After a successful start, the launcher displays the published address. The default health check URL is:

```text
http://127.0.0.1:8000/healthz
```

The normal response is `{"status":"ok"}`. This endpoint checks the service and database connection without creating accounts or sessions; database access failures return HTTP 503. A 404 response from `/` is expected: this image serves the backend API and does not include frontend pages.

If the build, initialisation or health check fails, the launcher returns a nonzero exit status and does not report a successful start. A failed health check can leave the container running or restarting. Use the `logs` action to investigate and `stop` if necessary.

The published port binds only to the host's `127.0.0.1` address. Inside the container, Gunicorn listens on `0.0.0.0:8000` and loads `backend.app:create_app()`, with no development debugger or automatic reload. The default HTTP and port settings are intended for **local development and demonstrations**. Production deployment also requires HTTPS and trusted reverse-proxy configuration.

Flask handles routes, business logic and database access. Gunicorn receives HTTP requests, serves the application and manages worker processes. The Docker build automatically installs a pinned Gunicorn version from `backend/requirements-docker.txt`; no manual installation is needed. Gunicorn runs only inside the Linux container and is not added to the Windows host development dependencies. Native development can continue to use `flask run`. See [Flask's Gunicorn deployment guide](https://flask.palletsprojects.com/en/stable/deploying/gunicorn/).

The initial configuration uses **1 worker and 4 threads** in a single container to keep resource usage modest. SQLite write transactions retain the existing serialised write lock; adding threads does not allow multiple simultaneous SQLite write transactions. Gunicorn sends access and error logs to the container logs. When stopping the container, Compose allows 35 seconds for the default graceful shutdown process to finish.

### 3.3 Create Login Accounts

Initialisation creates missing tables and controlled vocabulary tags. **It does not create default accounts or passwords.** A new data volume starts with a fresh database and does not automatically import accounts from the host's `data/h18abanana.db` file. An existing volume is reused when the container is recreated.

After startup succeeds, run the following commands from the repository root. They are the same in PowerShell and macOS / Linux terminals:

```sh
docker compose exec backend python -m flask --app backend.app provision-user --email talent@example.test --display-name "Demo Talent" --role TALENT
docker compose exec backend python -m flask --app backend.app provision-user --email team@example.test --display-name "Demo Team" --role RESEARCH_TEAM
```

Each command prompts for a password twice without displaying the input. Duplicate email addresses are rejected. Accounts remain in the data volume after stopping or recreating the container, so you do not need to provision them again.

### 3.4 Connect the Existing Frontend

The backend image does not include the frontend. For first-time native development, follow the existing setup instructions and run `setup.ps1` on Windows or `sh setup.sh` on macOS / Linux. Then start the frontend in another terminal.

**Windows:**

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\frontend\run.ps1 dev
```

**macOS / Linux:**

```sh
sh frontend/run.sh dev
```

Open `http://127.0.0.1:5173` and sign in using an account created in section 3.3. By default, Vite forwards `/api` to `http://127.0.0.1:8000`, which works with the Docker backend. Keep the same browser hostname throughout a session rather than switching between `localhost` and `127.0.0.1`.

### 3.5 Customise Ports and Environment Variables

No environment file is required for the defaults. To customise the configuration, copy the repository-root `.env.example` to `.env` in the same directory:

```powershell
# Windows
Copy-Item .env.example .env
```

```sh
# macOS / Linux
cp .env.example .env
```

| Variable | Default | Meaning |
| --- | --- | --- |
| `BACKEND_PORT` | `8000` | Host port; the container still listens on port 8000 |
| `COOKIE_SECURE` | `false` | Use false for local HTTP and true for HTTPS deployments |
| `ALLOWED_ORIGINS` | `http://127.0.0.1:5173,http://localhost:5173` | Comma-separated allowed frontend origins, without trailing slashes |

Run the launcher again after changing the configuration. For example, with `BACKEND_PORT=8001`, the health check URL becomes `http://127.0.0.1:8001/healthz`. Also set `API_PROXY_TARGET=http://127.0.0.1:8001` in `frontend/.env.local` and restart the frontend.

The launcher explicitly reads `.env` from the **repository root** if it exists, otherwise `.env.example`. It does not read an unrelated `.env` from the terminal's current directory. Environment variables already exported in the terminal take precedence. `backend/.env.example` remains a reference for native backend startup and is not loaded automatically by this launcher.

Compose fixes `DATABASE_URL` to `sqlite:////app/data/h18abanana.db` so that the database is stored in the persistent volume. Do not supply a host Windows database path in the container configuration. `ALLOWED_ORIGINS` controls CSRF validation; it does not enable cross-origin CORS. The frontend continues to access the API through Vite's same-origin proxy.

### 3.6 Build, Stop and Inspect Logs

| Action | Windows: arguments to `docker-backend.ps1` | macOS / Linux: arguments to `docker-backend.sh` |
| --- | --- | --- |
| Build and start / update | No arguments, or `-Action up` | No arguments, or `up` |
| Build the image without starting a container | `-Action build` | `build` |
| Show status | `-Action status` | `status` |
| Follow recent logs | `-Action logs` | `logs` |
| Stop the container | `-Action stop` | `stop` |
| Remove containers and networks while keeping the data volume | `-Action down` | `down` |

For example, to build only the image:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\docker-backend.ps1 -Action build
```

```sh
sh docker-backend.sh build
```

To share the built image with another person, export it:

```sh
docker image save --output banana-backend.tar banana-backend:local
```

The recipient can import the image and start it using the Compose configuration from the same project version, without rebuilding:

```sh
docker image load --input banana-backend.tar
docker compose up --no-build --detach --wait --wait-timeout 120 backend
```

The exported image contains backend code and Python dependencies. It does not contain database records, accounts or host environment files. Back up the data separately.

### 3.7 Persistence and Updates

- There is one backend service. SQLite has no separate server process or database container.
- The default Compose project name is `banana-backend`. Its default data volume is `banana-backend_backend_data`, mounted at `/app/data`. Keep the same project name to reuse the data. Multiple checkouts on the same Docker engine also operate on this same project by default.
- Running the launcher again reuses the volume. `init-db` creates only missing tables, and loading identical tags again does not overwrite existing data.
- Changes to existing table structures still require explicit migrations. If existing tags conflict with the seed definitions, startup fails; review the differences instead of trying to fix the conflict by recreating the container.
- `stop`, the launcher's `down` action and image rebuilds preserve the data. **Do not run `docker compose down -v` or delete the volume unless you intentionally want to erase the database.**
- The volume survives container replacement, but it is not a backup. Stop the backend before backing up the volume, or use the SQLite backup API. Avoid copying a database file while it is being written.
- The host's `data/`, virtual environment, frontend dependencies and environment files are excluded from the image. Existing host data is not automatically copied or overwritten.
- Source code is copied into the image rather than mounted live. After backend code changes, run the launcher again to rebuild the image. Keep a single backend instance by default.

If you customise the project name with `COMPOSE_PROJECT_NAME`, use the same value for startup, account management, logs and shutdown. A new project name creates a separate data volume.

### 3.8 Troubleshooting and Verification

| Symptom | Action |
| --- | --- |
| Docker command not found | Install Docker Desktop / Engine, ensure `docker` is on PATH, and reopen the terminal |
| Docker reports that WSL is not installed | Run `wsl --install --no-distribution` in an administrator PowerShell terminal; after installation, save your work, restart Windows and open Docker Desktop |
| Cannot connect to Docker | Start Docker Desktop / Engine; on Linux, check the current user's Docker access permissions |
| Linux containers are required | Switch Docker Desktop to Linux containers mode |
| Compose does not support `--wait` | Update Docker Desktop or the Compose plugin |
| Port 8000 is already in use | Stop the existing native backend or change the port as described in section 3.5 |
| Image or dependency downloads fail | Check Docker networking, proxy settings and registry access, then retry |
| Health check times out or initialisation fails | Use `logs` to inspect the failure; do not delete the data volume as a default troubleshooting step |
| Frontend login fails | Confirm that an account has been registered or provisioned, the proxy port matches, the frontend Origin is allowed, and local HTTP uses `COOKIE_SECURE=false` |

The code-level regression tests continue to use isolated temporary SQLite files and do not modify host or container application data. These commands use the host development environment installed by the existing setup scripts:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

```sh
.venv/bin/python -m pytest -q
```

`backend/tests/test_docker_backend.py` checks launcher failure handling, path resolution, repeatable initialisation and the health endpoint. Its Docker commands use test doubles, so these tests alone do not prove that a real image can be built. Actual Docker acceptance should include running the launcher, provisioning and signing in to an account, saving a profile, running `down`, and starting again to confirm that the account and profile persist.

#### Docker Verification Record: 2026-10-10

The following checks were completed on Windows with Docker Desktop running Linux containers:

- The launcher built `banana-backend:local` successfully. Gunicorn started, the container became `healthy`, and a host request to `/healthz` returned `{"status":"ok"}`.
- An account was provisioned in a separate temporary Compose project. Real HTTP requests verified login, profile saving and HTTP 409 for stale writes.
- After removing the temporary project's container and network while retaining its data volume, startup restored the original account, session and saved profile. Signing out and signing in again also succeeded.
- Cleanup removed only that temporary project and its test volume. No test accounts were written into the default project's data volume.
- The Windows launcher was corrected to select one command when both `docker.exe` and `docker` are found. All 9 related PowerShell launcher regression tests passed.

This verification covered the backend image and SQLite persistence. It did not include a containerised frontend or a production HTTPS deployment.
