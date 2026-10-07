# Banana frontend

JavaScript, React and Vite frontend with login/navigation, profile editing,
confirmation, privacy controls, and document upload/review. Talent accounts start
at My profile. Team accounts currently have an account shell only.

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
Python service separately using the [US-01 backend setup](../backend/README.md). Requests use
`/api/v1`, cookies and `X-CSRF-Token` according to the
[API contract](../docs/api/sprint-1-api-contract.md). The development proxy forwards
`/api` to `http://127.0.0.1:8000`; edit `API_PROXY_TARGET` in `.env` and restart Vite
if the backend uses another address. Never put secrets in public `VITE_*` values.
Production must also route `/api` to Python or configure a backend origin with
the appropriate cookie/CORS policy. An unavailable backend shows an error.

The current backend implements sessions, login/logout, tags and manual profile
reads/saves. Confirmation, privacy and document endpoints belong to other user
stories and are not yet supplied by that backend. Their existing UI remains for
those contributions. The US-01 development flow ends after saving the draft.

## Automated checks

From `frontend/`, use these commands on macOS, Linux or Windows:

```sh
npm run check
```

To run just one stage, use `npm test`, `npm run build`, or `npm run format:check`.
For focused checks, use `npm run test:18` for login/navigation,
`npm run test:21` for profile/privacy, or `npm run test:22` for documents. Focused
checks do not replace the full suite, which also covers shared code and contracts.
After full-stack setup, `sh run.sh check` or `./run.ps1 check` are alternatives
that use the saved toolchain.

- `tests/api.test.js`: the shared client/contract, including all 24 operations,
  request payloads, pagination, CSRF, multipart upload, downloads and errors.
- `tests/task-18-shell.test.js`: login/logout, unavailable service and mobile navigation.
- `tests/task-21-profile-privacy.test.js`: edits, confirmation, conflicts and privacy.
- `tests/task-22-documents.test.js`: upload failures, extraction review and import.
- `tests/contribution.test.js`: the application works independently of opportunity
  and matching pages; a tag service outage does not block privacy or sign out.
- `tests/architecture.test.js`: import resolution and module dependency boundaries.
- `tests/runner.test.js`: the command works from another directory (including paths
  with spaces), reports failing tests, and rejects an empty task selection.
- `tests/build.test.js`: production build and styles, with no test helpers,
  synthetic credentials, fixtures, jsdom, opportunity pages or matching pages.

The standard frontend tests use isolated synthetic responses. Shared contract tests
and their fixtures cover more API operations than the current pages.
jsdom interaction tests do not verify CSS layout or the Python backend.

For real HTTP integration, run the repository-root Python test suite after installing
frontend dependencies. `backend/tests/test_frontend_integration.py` runs frontend's `tests/us01-live.mjs`
against a temporary Python service and SQLite database. The actual React pages
exercise login, editing, saving, reload, conflicts, logout and account isolation.
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
only the account shell. These accounts are synthetic test fixtures.

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
| Privacy        | Discovery and field visibility settings save and survive reload.                                                           |
| Documents      | Upload an allowed PDF/DOCX, wait for extraction, review and import selected sections; imported content needs confirmation. |
| Failures       | Invalid/oversized files and failed extraction show errors; manual entry remains available.                                 |
| Service outage | Unavailable backend shows an error/retry, never synthetic success.                                                         |
| Responsive UI  | Fields, navigation and dialogs remain reachable on phone/tablet and with a keyboard.                                       |

Cross-user privacy enforcement, original-file access, matching calculations and
profile-to-recommendation flows require the Python backend and the complete
application. A passing frontend test run does not complete those acceptance criteria.

## Files

- `src/features/auth/`, `profile/`, `privacy/`, `documents/`: feature modules and styles.
- `src/layout/`: workspace shell with page configuration supplied by the application.
- `src/app/`: scoped page registration and tag vocabulary composition.
- `src/shared/`, `src/api/`: reusable controls, hooks, styles and HTTP infrastructure.
- `tests/`, `scripts/test.js`: repeatable tests, fixtures and test-only browser service.
- `public/`: application assets; `dist/` is generated build output.

`node_modules/`, `dist/`, `.env` and `.DS_Store` are ignored by Git.
