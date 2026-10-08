# US-02 implementation and acceptance

Implemented on 2026-10-08 against the checked-in Sprint 1 contract `0.1.0-draft`,
operations 16–20 (H18ABANANA-10; frontend task 19, backend task 28). No public API
schema, response field or publication-state change is introduced.

## User workflow

1. Sign in with a provisioned research-team account and open **Opportunities**.
2. Choose **Create opportunity**, fill in the basic fields and save a draft.
3. Add requirements with stable IDs, labels, SKILL/INTEREST kinds,
   REQUIRED/PREFERRED importance and one or more vocabulary tags per requirement.
   Selected tags form an AND group. Switching kind clears incompatible selections.
4. Save and publish. Publication requires at least one valid requirement. Drafts
   appear only in their owner's list; published opportunities appear to both roles.
5. Owners may edit published content, retaining publication status and at least
   one requirement. Other teams receive read-only details through the published list.
6. On a stale revision, local input is preserved. Reload shows both versions;
   explicitly select the latest content or continue editing the local version,
   merge changes and save. The client never automatically retries a mutation.

## Maintenance boundaries

| Module | Responsibility |
| --- | --- |
| `backend/src/features/opportunities/routes.py` | HTTP adaptation, session/role/CSRF checks and transaction scope |
| `backend/src/features/opportunities/service.py` | Visibility, tag validity, version checking and lifecycle |
| `backend/src/features/opportunities/repository.py` | Ordered child replacement and batch public serialization |
| `backend/src/db/models.py` | Opportunity/requirement/tag tables, constraints, relationships and indexes |
| `backend/src/shared/pagination.py` | Reusable pagination validated with OpenAPI limits/defaults |
| `frontend/src/features/opportunities/OpportunitiesPage.jsx` | Lists, pagination, focus refresh and detail selection |
| `frontend/src/features/opportunities/OpportunityEditor.jsx` | Draft state, mutations, unsaved input and recovery |
| `frontend/src/features/opportunities/RequirementEditor.jsx` | Requirement controls and tag selection |
| `frontend/src/features/opportunities/OpportunityDetails.jsx` | Plain-text content and comparison display |
| `frontend/src/features/opportunities/fields.js` | Form labels, input limits and initial values |
| `frontend/src/app/workspace-config.jsx` | Composition with independently testable core pages |

To add content fields, update the shared contract/examples, database migration,
repository mapping, form metadata/detail display and integration tests together.
To change lifecycle rules, update the service and its tests. Future matching can
select `published_opportunities()` and read the current ordered requirement/tag
rows. US-02 creates no cached scores and does not implement personalized matching.

Requirement IDs are unique within their opportunity, not globally. Child order is
explicit, with unique position constraints and foreign keys. Writes replace
related rows in one transaction, acquiring `BEGIN IMMEDIATE` before revision
checks. No-op updates and repeated current-revision publication preserve timestamps
and revisions; stale revisions always return 409. Public responses omit ownership
and account information. Filtering occurs before pagination and total calculation.

## Existing installations

Run the existing `init-db` command from [the backend guide](../backend/README.md)
against the configured database. It adds three missing tables without modifying
US-01 tables or deleting existing data. Seed the vocabulary if needed, then restart
the backend and frontend. No new dependency or environment variable is required.

## Verification

From the repository root on Windows:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -rs --require-frontend
powershell -NoProfile -ExecutionPolicy Bypass -File .\frontend\run.ps1 check
```

On macOS/Linux:

```sh
.venv/bin/python -m pytest -q -rs --require-frontend
sh frontend/run.sh check
```

Focused checks: `python -m pytest backend/tests/test_us02.py -q` using the project's
virtual environment, and `npm run test:19` from `frontend/`.

| Evidence | Coverage |
| --- | --- |
| `backend/tests/test_us02.py` | Real SQLite: create/edit/publish, no-ops, stale revisions, visibility, CSRF, invalid input, ordered replacement, pagination, restarts, rollback, foreign keys and simultaneous saves/publications |
| `frontend/tests/task-19-opportunities.test.js` | Synthetic HTTP: editor behavior, stable IDs, tags, conflict comparison, lost creation response, unsaved navigation, discovery, lists and errors |
| `frontend/tests/us02-live.mjs` through pytest | Real HTTP/SQLite: React login, draft creation, AND requirements, reload, publishing, editing, conflicts, talent browsing and cross-team denial |
| Existing US-01 and frontend suites | Regression coverage for login, profile, independent core workspace, shared API, imports and production bundling |

Actual Windows verification on 2026-10-08: **120 backend/integration tests passed**
(including 49 US-02 backend cases and both real HTTP workflows), **68 frontend
tests passed**, production build passed, and the full frontend formatting check
passed. The initial Windows CRLF formatting failure was fixed by accepting the
file's existing line ending in Prettier; unrelated source files were not reformatted.
Browser inspection with synthetic fixtures also checked the opportunity list and
requirement editor at desktop and 390-pixel mobile width with no horizontal overflow.

The real HTTP tests simulate the DOM with jsdom; they do not establish browser
layout or production HTTPS behavior. Recommendation ranking, talent matching,
profile confirmation, privacy endpoints and document processing belong to other
stories. Published discovery here is the non-personalized US-02 list.
