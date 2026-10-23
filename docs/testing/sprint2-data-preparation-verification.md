# Sprint 2 preparation: local verification

Date: 2026-10-23 (Australia/Sydney).
Base: `origin/main` at `0d65d89ee0c4ed62b0ae77b3d2e4595aef58d4a2`.
Branch: `test/sprint2-data-preparation`.
Dataset: `sprint2-synthetic-v1`.
Dataset SHA-256: `fe1d7dd0a3a83c26bc02a91ec367b7b6590a2227ee0dc5ac7bafef57d015a701`.

## Checks executed

Commands below were run from the repository root with the existing project-local
development toolchain. No application database or shared service was used.

| Command/check | Observed result |
|---|---|
| `python scripts/dev.py setup` | Dependencies installed from existing manifests; baseline suite: 425 passed, 1 failed, 6 skipped. See failure record below. |
| `python -m pytest backend/tests/test_sprint2_data_preparation.py -q -o junit_family=legacy --junitxml=data/sprint2-runs/preparation-tests.xml` | 23 passed, including the final unrelated-opportunity preservation assertion |
| `python -m pytest backend/tests -q --require-frontend -o junit_family=legacy --junitxml=data/sprint2-runs/final-tests.xml --tb=short` | 449 passed, 6 skipped; existing real HTTP/frontend integrations included |
| `python scripts/dev.py frontend test` | 189 passed, 0 failed, 0 skipped |
| `python scripts/dev.py frontend format:check` | Passed |
| `python scripts/dev.py frontend build` | Passed |
| CI API JSON parsing equivalent | openapi.json, endpoint-index.json and all 41 example/index JSON files parsed successfully |
| Current OpenAPI schema validation of example index | All 40 indexed API examples passed |
| `python scripts/prepare-test-data.py --run-dir data/sprint2-runs/verification-20261023` | Successfully prepared 12 accounts, 10 profiles, 7 opportunities and starting-state.json |
| Repeat the same preparation command | Refused with FileExistsError/nonzero exit; no existing database was opened |
| `git diff --cached --check` | Passed |

The complete suite collected before the extra unrelated-opportunity assertion
was added to the restoration test; the final focused run above includes that
assertion. No application code changed between these checks.

The six optional skips are the existing real Docker stack case and five opt-in
MySQL cases. Docker CLI is installed, but the Docker Desktop Linux engine pipe
was unavailable; no MySQL/container acceptance claim is made. No tests were
disabled or changed to obtain a pass. Existing CI and Docker configuration were
not changed. GitLab CI was not triggered because this branch was not pushed.

JUnit matching case properties contain datasetVersion and datasetSha256.
Runtime XML, logs and SQLite files remain local in ignored `data/` or
`.pytest_cache/`; they are not part of the commit.

## Existing intermittent failure

Before adding the preparation tests, the baseline run failed in
`backend/tests/test_frontend_integration.py::test_real_frontend_workflow[05]`.
An isolated rerun reproduced it. The log showed logout followed by a login
returning HTTP 403 and a timeout at `frontend/tests/us05-live.mjs:165`, while the
page requested a refresh. React act() warnings were also logged.

The final complete run passed this test without changing its source or related
application code. This is an observed intermittent failure, not a fixed defect;
the exact cause is unconfirmed. Preserve it for follow-up if it recurs rather
than inferring a data-preparation regression or suppressing the test.

## Requirement assessment

| Requirement | Status/evidence |
|---|---|
| AC1: authorised real talent and opportunity examples | **Pending external inputs.** Zero authorised real examples. The fallback preparation infrastructure is implemented; every included record is explicitly synthetic. |
| AC2: source and preparation records | Satisfied for all 17 included examples: stable ID/type/category/reference/date/steps/de-identification/intended use/privacy/retention/version. Future real inputs need their own reviewed records. |
| Versioned dataset and representative coverage | Implemented: 10 talents, 7 opportunities, 12 labels, current schemas and tag-coverage-v1; four statuses, incomplete/unconfirmed, unrelated, negative, hidden and private cases. |
| Starting state and independent outcomes | Implemented: explicit state definitions, verified runtime report and static manually sourced labels; current contract has no deadline. |
| Deterministic preparation and safe restore | Verified through new isolated databases. Existing destinations are refused; unrelated users/opportunities/files and old test edits survive. No in-place shared reset is provided. |
| Privacy and document handling | Verified: explicit visibility, private defaults, hidden evidence excluded, source metadata absent from team responses/reports; no original documents included. |
| US-06 / US-11 / US-16 linkage | US-06 unchanged; version/hash available in starting-state report and JUnit. This is not a real-source quality or browser acceptance report. |
| Local verification / CI preservation | Focused, complete backend/integration, frontend, format, build and API checks passed as above; optional MySQL/Docker checks not executed. Intermittent baseline issue disclosed. |

All changes are new test-data, helper, test, script or documentation files. No
application logic, API schema, matching weights, authentication, extraction,
frontend layout, database migration, CI or Docker configuration was edited.
Local main was fast-forwarded to the fetched remote tip as requested; no task
changes or commits were made on main. Existing untracked test-output files were
preserved and excluded from staging. No remote push, merge, history rewrite or
merge request was performed.

## Follow-up: logout/session race

The subsequently pushed commit `7dafd97` triggered pipeline 3214237. Its only
failed job, frontend_backend_integration (6181551), reproduced US-05's logout,
login HTTP 403 and page timeout. Backend, MySQL shards, frontend tests, formatting
and API validation passed; the dependent build was skipped.

A controlled pending-session regression failed against the original frontend:
logout cleared the API client's CSRF token, but App immediately displayed Login
while the asynchronous anonymous-session refresh was still pending. Login could
submit before the replacement token was available. This confirms a missing
readiness barrier, rather than a need to relax server CSRF checks.

The fix keeps the account state loading, with no previous user, until the fresh
session resolves. Both workspace and unsupported-role logout use this path;
ordinary background focus refreshes retain their existing behaviour. Session
failure retains the existing error/retry UI. No API, backend security, CI rules
or test skip conditions were changed.

Regression coverage holds the session response without fixed sleeps, checks
that no login form is available early, verifies the next login sends the new
token, and exercises refresh failure/recovery. The existing US-05 real HTTP
workflow also holds the actual anonymous response before switching accounts.
The focused real HTTP case passed; all 191 frontend tests, formatting and build
passed locally. Full `pytest backend/tests --require-frontend -q --tb=short`
returned 449 passed and the same 6 existing optional MySQL/Docker skips; no skip
was added. The earlier baseline failure record above remains historical.
