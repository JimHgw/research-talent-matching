# Sprint 3 FE-3: Query refresh, read cancellation and document polling

Implements [FE-3 in the Sprint 3 development guide](README_SPRINT_3_DEVELOP_EN.md#fe-3-improve-query-refresh-read-cancellation-and-document-polling), Jira H18ABANANA-67. This branch starts at `5551888b80b1a0f7c3e9b70e42e06e3735519dab`. FE-4 editor reconciliation is separate work.

## Shared query contract

`useResource(loader, dependencies, focusRefresh, { retainData: true })` enables background retention. The default remains `false` for existing editors. Dependencies identify the authorised context: include every entity, page and filter that changes the result. Account changes continue to reset the workspace through the existing account-session generation boundary.

| Value | Meaning |
| --- | --- |
| `loading` | Any current read is in progress; its existing meaning is preserved. |
| `initialLoading` | A read is in progress without a result for the current context. |
| `refreshing` | A read is in progress while the same context's previous result remains visible. |
| `data` | Last successful current-context result, or `null`. |
| `error` | Initial or non-recoverable read failure; protected data is cleared. |
| `refreshError` | Failed background read with retained data, only for temporary transport/service failures. |
| `refresh()` | Stable callback that invalidates the old read immediately and requests another read. |

Only network failures (`status: 0`), HTTP 429 and HTTP 5xx retain previous data. `INVALID_RESPONSE`, `PROFILE_UNCONFIRMED`, 401, 403, 404 and other non-recoverable failures clear it. Changing context hides the old data during render, before effect cleanup. Both cancellation and an independent request-liveness check protect against late success/failure, including transports that ignore abort.

Read-only document, opportunity, recommendation, talent and collection consumers explicitly use `initialLoading` and `RefreshStatus`. They retain their list during a background read and expose a translated refresh indicator or retryable failure. Removed list entries cannot leave a selected detail open or cause it to reopen after recovery. Team evidence dialogs close on window focus, preserving the existing consent revalidation boundary while the list refreshes. Team opportunity editors close on 401/403/404; temporary list failures leave their draft intact.

Profile/privacy editors and extraction-review loading keep their existing explicit reload semantics. Document-list polling does not reload a review's profile baseline or change its draft, selected sections, acknowledgement or submission revision. FE-2/FE-4 can adopt the new query contract explicitly when their ViewModels land.

## Read cancellation

The loader receives `{ signal }`. Public read methods accept an optional final `{ signal }` argument; existing calls and request URLs remain compatible. Examples:

```js
api.profile({ signal });
api.documents(page, { signal });
api.opportunities('published', page, filters, { signal });
api.talents(opportunityId, page, filters, { signal });
api.talentMatch(opportunityId, talentId, { signal });
```

Extraction and profile reads for a review share the review's signal. Multi-page opportunity loading forwards it to every request. Obsolete/context-switched/unmounted reads are aborted. An expected `AbortError`, including cancellation while reading JSON, is not converted into a user-facing network or invalid-response error.

Shared session bootstrap is still owned by the API client and is not cancelled by one consumer. Cookies, CSRF, upload/download payloads and write methods remain compatible. Cancellation is never treated as evidence that a write was rolled back.

## Document polling lifecycle

`useDocumentsQuery` owns the list and all polling timers/listeners.

- A mount starts a 60-second **wall-clock** budget. Explicit refresh/retry and a successfully completed upload start a fresh budget.
- While the list contains QUEUED/PROCESSING documents, schedule the next read two seconds after the previous read settles. At most one automatic list request is active.
- Background reads retain the current list. A temporary read failure can retry within the same budget; permission loss clears data and stops checks.
- READY/FAILED-only lists stop polling. Expiry only pauses automatic checks; it never changes a server document status to FAILED.
- Hidden pages start no new automatic requests. An already-started read can finish. Time spent hidden still consumes the budget.
- Returning to visibility rechecks pending work once only if the budget is unexpired and no read is active. Window focus alone does not reset the budget.
- Page changes cancel the obsolete read and clear the previous page's list. They do not extend the budget. Unmount removes timers/listeners and aborts the read. Remount establishes a new lifecycle.
- Manual refresh and manual profile entry remain available when checks pause.

## Reproducible verification

From `frontend/`:

```sh
npm run test:67
npm run check
```

From the repository root, with the documented backend dependencies and Node installed:

```sh
.venv/bin/python -m pytest -q --require-frontend \
  backend/tests/test_frontend_integration.py \
  backend/tests/test_us09_frontend_integration.py \
  backend/tests/test_us09_worker.py \
  backend/tests/test_fe3_frontend_integration.py
```

The new slow-Worker test takes about 70 seconds. It starts an isolated HTTP server, SQLite database, private document storage and the actual extraction Worker. A synthetic DOCX is uploaded; only the parser's start is delayed beyond 60 seconds. Real Worker claim/PROCESSING, parser output and READY transitions are used. The React UI runs in StrictMode with jsdom, real HTTP/cookies/CSRF, and a real clock. It verifies retained content, pause without FAILED, focus without restart, manual restart, terminal stop and explicit review acknowledgement. It does not depend on Docker or alter a running application's database.

Focused tests cover deferred success/failure races, immediate refresh invalidation, account/page/filter isolation, public API cancellation, permission/eligibility removal, dirty review preservation, new-upload restart, hidden/visible transitions, timers, StrictMode cleanup and remounts. Existing HTTP regressions cover the surrounding profile/privacy/opportunity/matching/collection/review flows.

## Acceptance boundary

Verification completed on 2026-11-06 with Node 24.22.1, Python 3.14.3 and Vite 7.3.6:

| Check | Result |
| --- | --- |
| Starting frontend baseline at `5551888` | 264 passed, 0 failed, 0 skipped |
| FE-3 focused tests | 29 passed, 0 failed, 0 skipped |
| Full frontend suite | 293 passed, 0 failed, 0 skipped |
| Existing real HTTP/document/Worker regressions | 27 passed, 0 failed, 0 skipped |
| Real slow-Worker integration | 1 passed; 70 seconds with a real clock |
| Vite production build | Passed |
| Frontend Prettier check and `git diff --check` | Passed |

The existing opportunity-source HTTP test now reads the mounted badge's class directly. Diagnostic reproduction showed jsdom returning no result for a cached compound class selector even though the badge's `outerHTML` and `matches()` both reported PUBLISHED. The test still requires publication and an available Edit action; production rendering is not changed for this test-environment issue.

### CI execution budget

Pipeline `3254327` on 2026-11-08 failed only in `backend_test` (job `6290611`). The Runner enforces a 10-minute maximum. Its log collected 764 tests, completed through approximately 95%, then terminated during the remaining US-20 tests. It reported no assertion failure before termination. The new slow-Worker test was skipped in that Python-only job because Node was unavailable; it did not cause the timeout.

The SQLite backend job now uses three parallel instances of the existing deterministic `--shard-index` / `--shard-total` partitioner, also used by the MySQL job. Actual collection yields 243, 246 and 275 tests: their union is all 764 tests with no duplicate assignment. Each instance writes a separate JUnit report and prints its ten slowest test durations. Failures still fail the pipeline; no test selection or timeout bypass is introduced.

The dedicated frontend/backend integration job explicitly includes `test_fe3_frontend_integration.py` with `--require-frontend`, so the slow-Worker acceptance test runs where Node and frontend dependencies are installed. Changing a YAML job timeout alone cannot exceed the Runner maximum.

Execution evidence is recorded against this branch and the current backend. No MySQL deployment, native-browser layout, external scoring model or future BE-6/BE-8 implementation is certified by these tests. Re-run shared acceptance when FE-1/FE-2 and BE-6/BE-8 final implementations are integrated. FE-3 does not change ranking, filtering payloads or backend business logic.
