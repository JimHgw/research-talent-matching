# Banana frontend

JavaScript, React and Vite frontend with login/navigation, profile editing,
confirmation, privacy controls, document upload/review and US-02 opportunities.
Talent accounts start at My profile. Both roles have an Opportunities page;
teams can create, edit and publish their own opportunities, while signed-in
users can browse published opportunities.

All application screens use the Python HTTP API. Synthetic services and data
exist only under `tests/`; normal development and demonstrations use the real
backend. There is no automatic mock fallback in application code.

## Local tests after setup

Use the existing repository-root `setup.sh` (macOS/Linux) or `setup.ps1` (Windows)
to install project dependencies as described below. There is no separate frontend
installer. Setup uses pnpm 11.25.0 and the committed `pnpm-lock.yaml`; it requires
Node 22.13+ with npm. Node 24 LTS is also supported.

If you installed Node inside the existing Python virtual environment using
nodeenv, activate that environment before running commands. From the repository
root on macOS/Linux:

```sh
. .venv/bin/activate
node --version
npm --version
cd frontend
npm run check
```

Activation is only needed to expose your locally installed tools. The frontend
tests, build and visual test service themselves run with Node in an ordinary
terminal, without Codex or a running Python backend. `npm run` executes existing
project scripts; it does not install dependencies or create a second lockfile.
Keep the full repository checkout: test fixtures also live in `docs/api/` beside
`frontend/`.

`npm run check` runs all frontend tests, builds the production bundle, and checks
formatting. It stops with a nonzero exit status if any step fails. Passing these
checks verifies the frontend in isolation; real backend integration is a separate
check described below.

If `node` or `npm` is not found, activate your environment or correct your PATH.
If `run.sh` reports a missing saved toolchain, complete setup successfully to
create `.venv/toolchain.json`. A Node 22.12 installation can run already-installed
frontend dependencies but cannot run the pinned pnpm installer; upgrade Node to
22.13+ before rerunning setup.

## Run with the Python backend

On Windows, first run the repository-root installer before starting development:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File ..\setup.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\run.ps1 dev
```

These commands run from `frontend/`. Setup installs the Python and JavaScript
dependencies and verifies both test suites. `run.ps1` uses the saved local
toolchain, so it works in a fresh terminal without globally installed pnpm.
See [first-time setup](../backend/README.md#first-step-after-cloning-install-the-development-environment).

On macOS/Linux, install Python 3.12+ and Node.js 22.13+ with npm on PATH,
then run these commands from `frontend/`:

```sh
sh ../setup.sh
sh run.sh dev
```

Setup installs the pnpm version pinned in `package.json` inside `.venv/node-tools/`
and records the local Node/pnpm paths in `.venv/toolchain.json`. Both launchers
use those paths, work from other directories and preserve arguments containing
spaces. They do not depend on Codex or a global pnpm installation. Rerun setup if
you move the checkout or replace Node. Recreate `.venv/` and `node_modules/` when
changing operating systems. If you manually manage dependencies instead, use
the pinned pnpm version directly (`pnpm install --frozen-lockfile`, `pnpm dev`).
Copy `.env.example` to `.env` only if you need to change the proxy defaults.

Open the URL printed by Vite (normally `http://127.0.0.1:5173`). Start the team's
Python service separately using the [backend setup](../backend/README.md). Requests use
`/api/v1`, cookies and `X-CSRF-Token` according to the
[API contract](../docs/api/sprint-1-api-contract.md). The development proxy forwards
`/api` to `http://127.0.0.1:8000`; edit `API_PROXY_TARGET` in `.env` and restart Vite
if the backend uses another address. Never put secrets in public `VITE_*` values.
Production must also route `/api` to Python or configure a backend origin with
the appropriate cookie/CORS policy. An unavailable backend shows an error.

The current backend supplies sessions, login/logout, tags, manual profile
reads/saves, US-03 profile confirmation, all five US-02 opportunity operations,
owner recommendations, privacy settings and US-05 team discovery. The discovery
page shows only published opportunities owned by the team, backend ranks and
permitted profile fields/evidence. It refreshes on entry, window focus or
**Refresh talent**. Document endpoints remain unimplemented.

## Frontend in Docker

Use [the integrated Docker guide](../docs/docker-integration.md) to start Nginx
and the Python backend together on their shared Compose network. The browser
continues to request `/api/v1`; Nginx forwards it to `backend:8000`.
[The frontend-only guide](docker/README.md) remains available for a backend running
on the host. Local development and tests remain available through the commands below.

## Automated checks

From `frontend/`, use these commands on macOS, Linux or Windows:

```sh
npm run check
```

To run just one stage, use `npm test`, `npm run build`, or `npm run format:check`.
For focused checks, use `npm run test:18` for login/navigation,
`npm run test:19` for opportunities, `npm run test:21` for profile/privacy, or `npm run test:22` for documents. Focused
checks do not replace the full suite, which also covers shared code and contracts.
After full-stack setup, `sh run.sh check` or `./run.ps1 check` are alternatives
that use the saved toolchain.

- `tests/api.test.js`: the shared client/contract, including all 29 operations,
  request payloads, pagination, CSRF, multipart upload, downloads and errors.
- `tests/task-18-shell.test.js`: login/logout, unavailable service and mobile navigation.
- `tests/task-19-opportunities.test.js`: creation, requirement editing, publication,
  version comparison, uncertain network outcomes, role-specific controls and lists.
- `tests/task-21-profile-privacy.test.js`: edits, confirmation, conflicts and privacy.
- `tests/task-22-documents.test.js`: upload failures, extraction review and import.
- `tests/task-21-mutations.test.js`: pending profile/privacy writes freeze inputs,
  reject duplicate submissions, preserve returned revisions and block navigation.
- `tests/task-22-mutations.test.js`: pending uploads/imports protect controls,
  navigation and dialog dismissal.
- `tests/contribution.test.js`: the core workspace configuration works independently
  of opportunity and matching pages; a tag outage does not block privacy or sign out.
- `tests/architecture.test.js`: import resolution and module dependency boundaries.
- `tests/runner.test.js`: the command works from another directory (including paths
  with spaces), reports failing tests, and rejects an empty task selection.
- `tests/build.test.js`: production build and styles, with no test helpers,
  synthetic credentials, fixtures, jsdom or unregistered matching pages.

The standard frontend tests use isolated synthetic responses. Shared contract tests
and their fixtures cover more API operations than the current pages.
jsdom interaction tests do not verify CSS layout or the Python backend.

For real HTTP integration, run the repository-root Python test suite after installing
frontend dependencies. `backend/tests/test_frontend_integration.py` runs
`tests/us01-live.mjs`, `tests/us02-live.mjs`, `tests/us03-live.mjs`, `tests/us05-live.mjs` and
`tests/us19-live.mjs` against a temporary Python service and SQLite database.
The actual React pages exercise login, complete profile fields, stable record IDs,
saving, reload, conflicts, logout and account isolation. The US-03 flow checks
explicit confirmation, edit invalidation and recovery from a stale revision.
The US-02 flow creates/publishes/edits an opportunity, preserves requirement IDs,
compares conflicting versions, browses as talent and checks another team's access.
The US-19 flow covers the alternative team editor and its conflict recovery.
The US-05 flow uses an independent talent session while the team page is open to
verify field hiding, anonymous results, revoked consent and unconfirmed edits.
It also verifies opt-in through the actual privacy page and all four match statuses.
Use `.venv/bin/python -m pytest -q -rs --require-frontend` on macOS/Linux, or
`.\.venv\Scripts\python.exe -m pytest -q -rs --require-frontend` on Windows.
The flag fails if Node/jsdom is missing instead of accepting a skipped integration
test. macOS/Linux may still skip the two Windows-only installer tests.

## Isolated visual checks without Python

```sh
npm run test:ui
```

Open `http://127.0.0.1:5174`. Use `talent@example.test` or `new@example.test` with
password `Demo1234!`. `team@example.test` uses the same test password and opens
the account shell with Opportunities navigation. These accounts are synthetic test fixtures.

For phone/tablet layouts, open `http://127.0.0.1:5174/tests/viewport.html`.
It loads the same application in 390 × 844 and 768 × 844 frames. Check navigation,
forms and dialogs. Extraction returns fixed suggestions in this test harness.
Stop with Control+C; fixture changes disappear on restart. This is an explicit
test service, not the normal development or demonstration backend.

## Acceptance with the real backend

Use backend-created accounts and a disposable database with synthetic documents.
Run the normal frontend with `npm run dev` (or the configured full-stack launcher).

| Flow           | Check                                                                                                                      |
| -------------- | -------------------------------------------------------------------------------------------------------------------------- |
| Sign in        | Valid/invalid credentials, session after reload, logout and failed logout.                                                 |
| Profile        | Saved values survive reload; edits require confirmation of the new revision.                                               |
| Confirmation   | Only the current saved revision can be explicitly confirmed.                                                               |
| Unsaved edits  | Keep editing preserves input; discarding leaves without saving.                                                            |
| Conflict       | Concurrent stale edits show a conflict and do not silently overwrite data.                                                 |
| Opportunities  | Team drafts, stable requirement IDs, publish validation, published edits, talent browsing and cross-team restrictions.     |
| Privacy        | Discovery and field visibility settings save and survive reload.                                                           |
| Documents      | Upload an allowed PDF/DOCX, wait for extraction, review and import selected sections; imported content needs confirmation. |
| Failures       | Invalid/oversized files and failed extraction show errors; manual entry remains available.                                 |
| Service outage | Unavailable backend shows an error/retry, never synthetic success.                                                         |
| Responsive UI  | Fields, navigation and dialogs remain reachable on phone/tablet and with a keyboard.                                       |

Cross-user privacy enforcement, original-file access, matching calculations and
profile-to-recommendation flows require the Python backend and the complete
application. A passing frontend test run does not complete those acceptance criteria.

## Files

- `src/features/auth/`, `profile/`, `privacy/`, `documents/`, `opportunities/`: feature modules and styles.
- `src/layout/`: workspace shell with page configuration supplied by the application.
- `src/app/`: scoped page registration and tag vocabulary composition.
- `src/shared/`, `src/api/`: reusable controls, hooks, styles and HTTP infrastructure.
- `tests/`, `scripts/test.js`: repeatable tests, fixtures and test-only browser service.
- `public/`: application assets; `dist/` is generated build output.

`node_modules/`, `dist/`, `.env` and `.DS_Store` are ignored by Git.

## Maintaining opportunity management

`OpportunitiesPage.jsx` handles lists and detail selection. `OpportunityEditor.jsx`
and `TeamOpportunityEditor.jsx` provide the page and dialog presentations.
Both use `useOpportunityEditor.js` for edits, save/publish actions and explicit
conflict recovery, `OpportunityFields.jsx` for the form and
`OpportunityRecovery.jsx` for comparison and recovery controls.
`RequirementEditor.jsx` handles stable requirement IDs and kind-specific tag
selection. `OpportunityDetails.jsx` renders plain text for both read-only details
and version comparison. `fields.js` holds form labels and limits; change these
with the corresponding OpenAPI schema if the contract evolves. Styles are local
to this feature. Register pages in `src/app/workspace-config.jsx` so the core
workspace and other contributions remain independently testable.

Conflicts keep the local form intact. Reload fetches a separate latest version;
the user compares both and explicitly chooses how to continue. A failed network
response is never automatically replayed. Creation recovery lists saved
opportunities before allowing another attempt, avoiding accidental duplicate
drafts after a lost response. Lists refresh on return/focus; an open editor never
refreshes over unsaved input. See [US-02 details](../docs/us02-implementation.md).

## Maintaining profile forms and pending writes

`ProfileFields.jsx` composes the identity, record, skills and research-interest
editors; `features/profile/fields.js` holds their metadata and record defaults.
Keep API field names, nullable values and stable record IDs aligned with the
contract when editing these modules. Both manual entry and extraction review
reuse the profile field entry point.

`shared/useMutation.js` guards duplicate mutations and suppresses completion
callbacks after a component unmounts. Profile, privacy, opportunity and document
forms disable editable controls while a write is pending. `usePageGuard` and
`layout/useWorkspaceNavigation.js` protect page changes and sign out until the
operation finishes. Errors retain local input for correction or explicit recovery.
Workspace presentation lives in `WorkspaceChrome.jsx`; navigation and small UI
hooks remain separate from the page composition in `Workspace.jsx`.

Formatting accepts each file's existing LF/CRLF endings so Windows Git checkouts
do not require reformatting unrelated files.

## US-01 registration supplement

The login screen accepts an email address or the server-assigned account ID.
Its **Register** button opens `/register`, including support for direct visits,
reloads and browser history. The registration form requests an email code,
offers TALENT and RESEARCH_TEAM account types, and collects a display name,
password and matching confirmation. It shows resend cooldowns and server errors,
and opens the appropriate workspace on success. The shared client retains the
existing session/CSRF handling; see the
[US-01 email-registration contract](../docs/us01-registration.md).
`tests/us01-register-live.mjs` verifies both-role registration through the React
form and real backend, followed by ID login. `tests/task-18-registration.test.js`
covers navigation, validation, sending failures, resends and pending requests.

## Password reset

The login screen offers original-password reset and a staged email-code reset.
New passwords require at least 8 characters, with uppercase, lowercase and
numeric characters, and matching confirmation. The API enforces the same rules
and rejects reuse of the current password. See the [US-01 reset contract](../docs/us01-password-reset.md).
`tests/us01-reset-live.mjs` verifies both paths against the real backend.
