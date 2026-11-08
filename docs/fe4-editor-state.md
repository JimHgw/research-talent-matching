# Sprint 3 FE-4: Editing, confirmation, privacy and account state

Implements FE-4 / H18ABANANA-68 in [the Sprint 3 development guide](README_SPRINT_3_DEVELOP_EN.md#fe-4-align-editing-confirmation-privacy-and-account-state). The branch `jiancheng/fronted-sprint3-fe4-editor-state` starts from main at `bf705618f85f959a92b5fe56074bd443fe5537af`, including FE-3 and BE-7.

## Editor ownership and transitions

`useProfileEditor` and `usePrivacyEditor` own their feature operations and use `useVersionedEditor` for shared read, draft and recovery rules. Their repositories can be replaced by in-memory implementations in tests. Pages render fields, translations and comparison summaries. The existing `useOpportunityEditor` retains its save/publish/reopen and uncertain-creation recovery flow, with added result validation and persistent reconciliation state.

| State | Source and rule |
| --- | --- |
| Saved snapshot | A validated server result; its revision is the next submission baseline. |
| Draft | A separate copy of editable values. Privacy drafts contain no revision. |
| Submission | Capture the saved revision and submitted values at the start of the write. |
| Latest comparison | A separately loaded canonical result; reading it does not change the draft or baseline. |
| Acknowledgement | Applies only to the saved profile actually reviewed; editing, save, reload or reconciliation resets it. |
| Recovery failure | Persists independently of comparison-read errors, preventing blind resubmission. |

Initial load establishes a baseline. Focus can refresh a clean editor, but never a dirty, submitting or unresolved editor. Editing or starting a write invalidates/aborts an older background read, including when the transport ignores abort. Explicit reload keeps the existing discard confirmation and replaces values only after a successful validated read. A failed reload leaves input available.

After a conflict or uncertain write, **Compare before continuing** performs a read without discarding input. Both versions are displayed using user-facing fields. **Use latest version** accepts the canonical values and revision. **Continue editing my version** keeps local values while explicitly adopting the revision shown in the comparison. Neither choice submits a write. Error payload revision hints are never used as a replacement for reading current state.

## Writes and recovery

All writes reuse `useMutation` and navigation/pending guards. Its optional failure callback runs only for a still-mounted caller. Writes are not aborted on unmount, and cancellation is never presented as proof of rollback.

Network errors, HTTP 5xx, unreadable successful responses and invalid successful snapshots are uncertain outcomes. They keep recoverable input, show that the request may have succeeded, disable repeat writes and offer read/compare recovery. A failed comparison does not erase the original recovery requirement. A new opportunity with an unknown creation result still checks recently saved drafts before creating again.

Critical editor responses are checked before resetting dirty state, notifying success or invalidating dependent reads: revisions, expected profile/opportunity identity, profile content/confirmation shape, privacy settings and opportunity lifecycle state. Confirmation must return the reviewed revision with a matching CONFIRMED result. Historical profile reads with an older confirmation are displayed as needing confirmation. A normal save of an expired opportunity must keep EXPIRED; only a successful explicit reopen result establishes ACTIVE.

The list's Publish action uses the same validation and reconciliation rules. An unresolved publication blocks further publication attempts and opens the existing editor for comparison. A second opportunity cannot replace that unresolved outcome. HTTP 401/403/404 remove the relevant private editor; confirmed account changes unmount the entire previous workspace.

`403 CSRF_INVALID` is a known pre-write rejection, not resource access loss. It preserves saved state, local input and the submission revision, and permits a deliberate retry after session/token renewal. A focus-driven session check does not replay the rejected write. Other 403 responses, 401 and 404 continue to clear inaccessible private state. Publication recovery is bound to the blocked opportunity ID: reconciling another opportunity never clears that block or its error, including while the list refresh remains pending.

## Confirmation and consent

Save, reviewed document import and confirmation remain separate operations. A changed/imported profile requires review and explicit confirmation; no save/import automatically calls confirmation. Confirmation is blocked by dirty content, missing acknowledgement, pending operations and unresolved recovery. The server's canonical confirmation revision/status determines the display.

Privacy has its own saved snapshot and revision. The discovery-status notice always describes saved consent, while switches/checkboxes represent the local draft. Only a valid save or an explicit successful reload/reconciliation changes the saved notice. Field ordering is normalised for dirty comparison without changing consent groups.

The existing account-session generation checks, identity-and-role workspace key, anonymous-session bootstrap and elective account-switch guards are preserved. Tests cover switching between two TALENT accounts, old writes succeeding or failing afterwards, session expiry, pending-write guards and suppression of previous-account notifications/invalidation callbacks.

## Dependent read invalidation

`data-invalidation.js` broadcasts domain names only, never profile/document contents. Validated feature writes notify mounted consumers; unmounted pages obtain current data when entered again. Dirty editors do not subscribe to these read-only refresh events.

| Validated operation | Invalidated domains | Affected reads |
| --- | --- | --- |
| Profile save/confirmation | profile, matching, collections | Recommendations, matching details, talent results, saved opportunities and collection state |
| Privacy save | privacy, matching, collections | Consent/eligibility-sensitive lists, evidence and collections |
| Opportunity save/publish/reopen/reconciliation | opportunities, matching, collections | Opportunity lists/details, talent opportunity selection/results, recommendations and collections |

The FE-3 read rules remove inaccessible or ineligible results/dialogs on the next revalidation. Existing cross-tab focus checks continue to enforce server-owned confirmation/consent. No frontend score, rank or matching rule is added.

## Verification and CI

Executed on 8 November 2026, with Node 24.22.1 and Python 3.14.3, against the current backend at the base commit above plus this branch's uncommitted frontend changes:

| Check | Result |
| --- | --- |
| Main baseline frontend suite | 294 passed, 0 failed, 0 skipped |
| Final complete frontend suite | 335 passed, 0 failed, 0 skipped; 41 additional FE-4 tests |
| Existing application/document/FE-3 real HTTP integration | 17 passed, including the slow Worker regression |
| New FE-4 real HTTP integration | 1 passed; server-committed response loss and concurrent/session/lifecycle recovery |
| Vite production build | Passed |
| Frontend Prettier check | Passed |
| CI YAML parsing and required FE-4 integration entry | Passed locally; remote pipeline not run for these uncommitted changes |

Review follow-up against `36a26c30` on the same date: both P2 reports were reproduced with failing regression tests before the production fix. Six new tests cover CSRF rejection/retry for profile, privacy, opportunity save/reopen/list publication, and cross-opportunity reconciliation with a deferred list refresh (including release by the correct ID). The final full suite passes **341 tests**, with **47 FE-4 tests**. The extended FE-4 real HTTP test passes with real shared-cookie re-login and stale CSRF rejection for profile and privacy, followed by session renewal and explicit retry. Production build and the configured formatting check pass. The earlier 17-test HTTP regression result above was not rerun for this targeted follow-up.

From `frontend/`:

```sh
npm run test:68
npm run check
```

From the repository root with backend dependencies and Node available:

```sh
.venv/bin/python -m pytest -q --require-frontend \
  backend/tests/test_fe4_frontend_integration.py \
  backend/tests/test_frontend_integration.py \
  backend/tests/test_us09_frontend_integration.py \
  backend/tests/test_fe3_frontend_integration.py
```

The dedicated CI frontend/backend integration job includes the new FE-4 test with `--require-frontend`. Backend-only jobs keep their normal optional Node gate and deterministic test sharding.

The new integration test starts real Flask/SQLite, uses real cookies and CSRF, and runs React in StrictMode/jsdom. It writes to the server before disturbing delivery of the response. It verifies profile/consent recovery after commit, concurrent profile revisions, independent confirmation, retained expiry after an ordinary save, explicit reopen and publication recovery, withdrawn consent and same-role account isolation with a delayed committed write. All data is synthetic and stored in temporary test databases. The existing application database and Docker volumes are not involved.

Native-browser layout, Docker/MySQL deployment and external model execution are not certified by this frontend run. Re-run shared acceptance when the final BE-3/BE-4/BE-5 service changes are integrated. FE-1's central typed/validated boundaries and FE-2's review UseCases remain separate ownership; their integration must preserve these uncertain-write and revision rules.
