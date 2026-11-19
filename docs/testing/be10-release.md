# BE-10 integration and release acceptance

## Current scope and provenance

Branch: `be10/integration-diagnostics-release`, based on fetched main
`5c3a96c0ebe90083c94247c503201bc46a6396f2`. Execution date: 2026-11-18.
The implementation commit and machine-readable current results are recorded in
[be10-execution.json](be10-execution.json). These are new local executions, not
the historical results in the linked story reports. Tests ran against the
implementation working tree; a redundant worker logging change was removed and
the affected diagnostics/workflow tests rerun before committing. No frontend,
schema, extraction, matching-score or worker lifecycle logic was replaced.

Dependency review used `git merge-base --is-ancestor <commit> origin/main`;
every entry below succeeded. EN/CN Sprint 3 requirements and the existing BE-9
and frontend review reports were reviewed.

| Dependency | Existing commit on reviewed main |
| --- | --- |
| BE-1 contracts | `77ab806` |
| BE-2 reviewed import | `e1c70f0` |
| BE-3 shared profile services | `2609627` |
| BE-4 transactions/concurrency | `947379c` |
| BE-5 authorization/privacy | `3e590f3` |
| BE-6 worker recovery | `00b67de` |
| BE-7 semantic matching | `2750a2f` |
| BE-8 query performance | `629a037` |
| BE-9 startup/probe readiness | `210833b` |
| FE-1/2/5 integration/review/delivery | `8fb55af` |
| FE-3 polling/query lifecycle | `a515aeb` |
| FE-4 revision/draft recovery | `5386f65` |

## Execution and mandatory gates

Windows, Python 3.12.14, SQLite 3.53.1; three independent disposable MySQL
8.4.13 containers, each with a new `_test` database. Real frontend modules ran
against real HTTP APIs through the existing Node/jsdom harness. Frontend check
also ran typecheck, 348 tests, production build and formatting, all successfully.

| Current run | Passed | Failed/errors | Skipped | Gate |
| --- | ---: | ---: | ---: | --- |
| Complete backend, three SQLite shards | 1092 | 0 | 15 | PASS |
| Complete backend, three real MySQL shards | 1104 | 0 | 3 | PASS |
| Required frontend/API integration | 18 | 0 | 0 | PASS |
| Required current application-model suite | 101 | 0 | 0 | PASS |
| Real Docker restart and BE-9 MySQL backup/restore | 12 | 0 | 0 | PASS |
| Final focused diagnostics/workflow/gate retest | 24 | 0 | 0 | PASS |

The SQLite skips are 13 MySQL-only cases plus two opt-in Docker cases, executed
successfully in the separate runs. MySQL skips are one SQLite-only migration
case and the same two Docker cases, covered separately. There are no skipped
mandatory frontend or actual-model cases. Counts across groups overlap.

Current real model: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`,
version `multilingual-minilm-requirements-onnx-v1`, revision
`e8f8c211226b894fcb81acc59f3b34ba3efd5f42`. Runtime: onnxruntime 1.23.2,
tokenizers 0.22.1; preprocessing `requirement-inputs-v1`, scoring
`requirement-semantic-v1`, thresholds `requirement-thresholds-v1`.
The existing `prepare_semantic` command verified the configured tokenizer/model
checksums. Actual-model tests assert SEMANTIC scoring, current model version,
Chinese/negation behaviour, collection consistency and query equivalence.
Deterministic encoders are not used as actual-model acceptance evidence.

Replay from the repository root with an installed development environment:

```text
python -m backend.src.features.matching.prepare_semantic
python -m pytest backend/tests --require-application-model --shard-total 3 --shard-index N -q --junitxml=reports/backend-tests-N.xml
python -m pytest backend/tests --run-mysql --require-application-model --shard-total 3 --shard-index N -q --junitxml=reports/mysql-tests-N.xml
python -m pytest backend/tests/test_frontend_integration.py backend/tests/test_us09_frontend_integration.py backend/tests/test_fe3_frontend_integration.py backend/tests/test_fe4_frontend_integration.py --require-frontend -q --junitxml=reports/frontend-integration.xml
python -m pytest backend/tests/test_us13.py backend/tests/test_semantic_matching.py backend/tests/test_requirement_scoring.py backend/tests/test_sprint3_be7.py backend/tests/test_sprint3_be8.py backend/tests/test_sprint3_be10.py --require-application-model -q --junitxml=reports/be7-application-model.xml
python -m pytest backend/tests/test_docker_stack.py backend/tests/test_sprint3_be9.py --run-docker -q --junitxml=reports/docker-release.xml
python -m pytest backend/tests/test_sprint3_be10.py backend/tests/test_release_gate.py --require-application-model -q
python scripts/dev.py frontend check
python scripts/verify_release.py --reports reports --output reports/release-acceptance.json
```

Run each shard for N=1,2,3. Set `MYSQL_TEST_DATABASE_URL` to a separate disposable
MySQL 8.4 database per parallel shard; tests clear that database. Never point
these commands at a shared or production database. Local commands used
`.venv/Scripts/python.exe`, `--tb=short -o junit_family=legacy` and the ignored
`.pytest_cache/be10/` report directory. The local MySQL launcher created random
isolated containers/databases and removed only its own resources afterwards.

CI reuses the existing sharded suites and dedicated model/frontend jobs.
`release_acceptance` consumes their same-pipeline JUnit artifacts, rejects
missing/failing/skipped mandatory cases, and verifies actual MySQL 8.4 identity
and current model properties. Sharded MySQL artifacts now have unique names.
The production frontend build follows acceptance. The 19 gate regression tests
exercise missing/skipped/failed/error evidence and wrong DB/model rejection.
CI retains JUnit and `reports/release-acceptance.json` for one week; Docker
recovery is a separately executed local release check, not a Docker-in-Docker CI job.

## Workflow, failures and recovery evidence

- `test_sprint3_be10.py`: DOCX upload, real extraction, selected skills-only
  import, unconfirmed state, explicit confirmation and real semantic matching.
  A second login edits the profile; stale import/write return correlated 409s
  without losing newer data. Explicit reload/review precedes retry. Discovery
  revocation removes team access; encoder failure uses structured fallback while
  health remains 200; deadline editing alone cannot reopen an expired opportunity.
  Recreating the API preserves profile and extraction records.
- Current frontend tests cover PDF/DOCX review, partial selections, account
  boundaries, slow-worker polling and FE-4 conflicting edits/recovery. Drafts
  remain available for explicit resolution, without silently overwriting newer data.
- Existing BE-4 and BE-6 tests execute concurrent writers, independent worker
  processes, process termination, natural lease expiry, reclaim, fencing and
  terminal failure. The additional CLI test correlates CLAIMED/RECLAIMED,
  parse, persistence and READY by document ID, excluding lease secrets.
- Existing BE-9 checks reject incompatible schema before API/worker readiness;
  health connectivity failure is unhealthy, and successful structured semantic
  fallback remains healthy. Actual Docker down/up preserves stored files,
  extraction and profile data across API/worker restart. The real MySQL backup
  and restore rehearsal preserves existing data through repeated upgrades.

Two diagnostic gaps were reproduced against main source loaded only in isolated
test processes, without replacing working files:

| Gap | Baseline reproduction | Final regression |
| --- | --- | --- |
| Request failure lacked stage/category/duration | Controlled 500 test failed against main's `app.py`; request ID alone was present | Correlated response/header/log, safe endpoint, category, exception type and duration pass |
| Semantic fallback lacked request correlation/duration | Release workflow failed its fallback-log assertion with main's `semantic_runtime.py` | Fallback log matches response ID; no model input/path/message exposure |

Baseline reports: `baseline-diagnostics.xml` (one expected failure, existing
worker correlation passed) and `baseline-semantic.xml` (one expected failure).
Final `diagnostics-retest.xml`: 24 passed. Logs are checked against synthetic
password, cookie, CSRF, resume, model-input and private-path markers. Worker
logging was already implemented in BE-6 and is reused unchanged.

## Release and recovery notes

API schemas, status bodies, error envelope, `requestId` and `X-Request-Id` are
unchanged. Only safe error/conflict/fallback diagnostic metadata is added.
No migration is introduced. Follow [BE-9 release/recovery](be9-release.md) for
backups, stopped writers, `prepare-db`, `check-schema`, matching service images,
failed-upgrade recovery and restore. Full schema checking remains at startup;
`/healthz` retains its lightweight readiness-state plus connectivity check.

Prepare the configured local semantic artifacts before acceptance/deployment;
requests never download models. Missing/unusable resources yield structured
fallback, not a false database-readiness failure. Diagnose failures by response
request ID and worker document ID; never add raw request/profile/model text to logs.
After repairing startup schema, restart the API/worker to establish readiness.

Limitations: synthetic isolated data, no shared-server deployment or production
DB changes; jsdom/HTTP integration is not a new human-browser accessibility
audit. Existing [frontend review](sprint3-frontend-review.md) remains supporting
context, not a substitute for these current executions. Runtime DDL and mixed
service versions remain unsupported as documented in BE-9. Test containers were
removed and Docker returned to its initial stopped state. The pre-existing
untracked `test-output/` directory is retained and excluded from commits.
