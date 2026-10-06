# Banana frontend

JavaScript, React and Vite frontend with login/navigation, profile editing,
confirmation, privacy controls, and document upload/review. Talent accounts start
at My profile. Team accounts currently have an account shell only.

All application screens use the Python HTTP API. Synthetic services and data
exist only under `tests/`; normal development and demonstrations use the real
backend. There is no automatic mock fallback in application code.

## Run with the Python backend

Requirements: Node.js 22.12+ and pnpm. Run these commands from `frontend/`:

```sh
./run.sh install --frozen-lockfile
cp .env.example .env
./run.sh dev
```

The optional `run.sh` wrapper uses your installed Node/pnpm, or the local Codex
runtime when available. It does not change shell settings. Normal pnpm commands
also work when Node and pnpm are on PATH.

Open the URL printed by Vite (normally `http://127.0.0.1:5173`). Start the team's
Python service separately; backend code is not included here. Requests use
`/api/v1`, cookies and `X-CSRF-Token` according to the
[API contract](../docs/api/sprint-1-api-contract.md). The development proxy forwards
`/api` to `http://127.0.0.1:8000`; edit `API_PROXY_TARGET` in `.env` and restart Vite
if the backend uses another address. Never put secrets in public `VITE_*` values.
Production must also route `/api` to Python or configure a backend origin with
the appropriate cookie/CORS policy. An unavailable backend shows an error.

## Automated checks

```sh
./run.sh test
./run.sh build
./run.sh format:check
```

For focused checks, use `./run.sh test:18` for login/navigation,
`./run.sh test:21` for profile/privacy, or `./run.sh test:22` for documents.

- `tests/api.test.js`: the shared client/contract, including all 24 operations,
  request payloads, pagination, CSRF, multipart upload, downloads and errors.
- `tests/task-18-shell.test.js`: login/logout, unavailable service and mobile navigation.
- `tests/task-21-profile-privacy.test.js`: edits, confirmation, conflicts and privacy.
- `tests/task-22-documents.test.js`: upload failures, extraction review and import.
- `tests/contribution.test.js`: the application works independently of opportunity
  and matching pages; a tag service outage does not block privacy or sign out.
- `tests/architecture.test.js`: import resolution and module dependency boundaries.
- `tests/build.test.js`: production build and styles, with no test helpers,
  synthetic credentials, fixtures, jsdom, opportunity pages or matching pages.

Tests use isolated synthetic responses, never a live API. Shared contract tests
and their fixtures cover more API operations than the current pages.
jsdom interaction tests do not verify CSS layout or the Python backend.

## Isolated visual checks without Python

```sh
./run.sh test:ui
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
Run the normal frontend with `./run.sh dev`.

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
