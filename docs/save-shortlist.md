# Save opportunities and shortlist candidates

This feature is additive. No existing opportunity, profile, document, or privacy tables are changed.

## Talent

Open Recommended opportunities and choose Save Opportunity on a card or its detail dialog.
Saved opportunities in the navigation lists the signed-in talent's currently published saved opportunities.
Remove from Saved is idempotent. Records are stored in SQLite, independent of browser storage and sessions.
No profile confirmation is required by the save API; recommendations retain their existing confirmation gate.

## Research teams

Publish your own opportunity, open Discover talent, select that opportunity, and Add to Shortlist.
Use View Shortlisted Candidates or the Shortlisted candidates navigation entry to review/remove candidates.
Shortlists are scoped to the opportunity owner and are separate for each opportunity.
Match scores and explanations retain the existing algorithm and current field visibility rules.

## Privacy and persistence

The two new tables store only foreign-key relationships and creation timestamps. Composite primary keys prevent duplicates.
Each request checks session role; each shortlist request checks ownership of a published opportunity.
GET and PUT for candidates require current opt-in, active talent account and a currently confirmed profile.
List results apply these checks before counts, rankings and pagination; only current permitted fields enter scoring.
No original documents, document metadata, provenance, hidden fields, or copied profile snapshots are returned.

Opting out, becoming unconfirmed, or deactivating hides an existing candidate from every shortlist response.
The ID-only relationship is retained. If the talent later becomes eligible again it reappears with CURRENT visible fields.
DELETE can remove an association even after consent is withdrawn, without disclosing whether that candidate exists.
The frontend refreshes on entry, explicit refresh and window focus. Consent is enforced on every server request;
it cannot retroactively erase information a team already viewed or copied. There is no push-notification channel.

All writes use the existing BEGIN IMMEDIATE SQLite transaction and CSRF/Origin validation.
PUT adds idempotently; DELETE removes idempotently; responses are {"saved": true/false}.
GET/PUT of missing/inaccessible targets returns 404; malformed IDs return 422; wrong roles return 403.
API schemas and endpoint descriptions are in docs/api/openapi.json.

## Setup and review

Use this feature branch in an isolated development environment and a separate DATABASE_URL/DOCUMENT_STORAGE_DIR.
Run the project's supported setup script, then python -m flask --app backend.app init-db against that isolated database.
This adds the missing relationship tables without altering existing tables. The normal Docker entrypoint also calls init-db.
Do not point development commands at a shared database or reuse an existing team's Docker volume.
Use the existing launch instructions in README_DEVELOPER_EN.md for the frontend, API and document worker.

Manual checks:

1. Sign in as talent, save a published opportunity, reopen the application and sign in again: Saved opportunities persists.
2. Remove it, refresh and confirm it remains removed. A different talent must see only their own list.
3. As its owning team, shortlist an opted-in confirmed talent. Reopen the opportunity's shortlist and remove/add again.
4. Change the talent's shared fields: refresh the team view and verify hidden fields and evidence disappear.
5. Disable discoverability: refresh the team view and verify the candidate disappears; re-enable and verify current fields only.
6. Another team cannot list or change this shortlist. Private drafts cannot be saved or used for shortlisting.

## Automated coverage

Run python -m pytest backend/tests/test_collections.py for SQLite persistence, duplicate/concurrent writes,
foreign keys, authentication/CSRF, cross-user/team ownership, draft protection, IDs and current privacy checks.
Run the existing backend regression suite and frontend pnpm test, pnpm format:check, and pnpm build.
The existing US-05 real HTTP workflow now additionally exercises both collection UIs, removing entries,
navigation, application remount, logout/login, privacy revocation and real API reads against file-backed SQLite.
Run python -m pytest backend/tests/test_frontend_integration.py --require-frontend with frontend dependencies installed.
All these checks remain in the existing CI jobs. CI results, not this document, determine whether the branch passed.
