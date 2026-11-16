# BE-3 Profile Save and Confirmation Verification

## 1. Scope and execution environment

| Item | Recorded value |
| --- | --- |
| Task | BE-3: Organise Profile Save and Confirmation Services |
| Branch | H18ABANANA-72-BE-3 |
| Base commit | 8b8a879f997b095b83c97b0f7f946bcf93599194 |
| Tested state | Base commit plus the uncommitted BE-3 implementation and tests |
| Platform | Windows |
| Python / pytest | 3.13.17 / 8.4.2 |
| Database used | Disposable SQLite databases; SQLite 3.50.4 |
| Flask / SQLAlchemy | 3.1.2 / 2.0.44 |
| ONNX Runtime / NumPy / tokenizers | 1.23.2 / 2.3.4 / 0.22.1 |
| Full-run start | 2026-11-16 22:15:55 AEDT (Australia/Sydney) |

The base includes the merged BE-2 and BE-4 work. Preparation checks ran in an
isolated copy outside the repository. Final verification ran against the actual
project with reports and temporary test data directed outside the checkout.
The final implementation commit, MR and owner are recorded during handoff.

## 2. Implementation and state-transition rules

- `profile/service.py` provides `save_profile` and `confirm_profile` with explicit
  arguments and the caller's Session. Both operations retain BE-4's write-lock
  guard and work without a Flask application or HTTP request context.
- `profile/repository.py` owns profile persistence, reference-data queries and
  vocabulary persistence. Profile and tag response assembly remains in the
  serialization module. The existing `seed_tags` CLI/fixture entry point remains
  available through its compatibility wrapper.
- `profile/routes.py` retains authentication, CSRF, request parsing, transaction
  boundaries and HTTP responses. Confirmation retains the existing owner lookup
  before parsing the request body.
- `profile/state.py` supplies `mark_profile_changed`, shared by ordinary saves and
  reviewed imports. Services and repositories do not open nested transactions or
  commit independently; errors propagate through the caller's transaction.
- BE-4 fault injection now targets the profile service's final serialization.
  Only the imported module and injection target changed; its assertions remain
  intact.

| Operation or condition | Preserved behaviour |
| --- | --- |
| Actual ordinary save | Increment revision once; set UNCONFIRMED; clear confirmedRevision/confirmedAt; update the timestamp; mark only changed components as MANUAL. |
| Canonically identical ordinary save | Preserve the complete saved response, revision, confirmation, timestamps and provenance. |
| Successful reviewed import | Increment revision once even for identical imported content; clear confirmation; retain reviewed-document provenance rules. |
| Current-revision confirmation | Require a nonblank name and confirmable content; set confirmedRevision and the first confirmedAt without incrementing revision. |
| Repeated confirmation | Preserve revision and the original confirmation timestamp. |
| Stale save, confirmation or import | Return REVISION_CONFLICT with the stored revision, preserving all database state. |
| Omitted companion fields | Preserve researchInterestText, customInterestTags and resumeDescription. Explicit empty values retain their existing clearing semantics. |
| Personal interests | Preserve normalization, deduplication, shared-label resolution, description compatibility, owner isolation and the combined-count limit. |
| Invalid input or failed writes | Preserve profile state, catalogues, selections and provenance through validation or transaction rollback. |

Inputs are copied before canonicalization so callers' submitted content is not
mutated. No public API schema, dependency or database schema changes are
introduced by BE-3.

## 3. Preparation and final regression

Durations in this table are JUnit suite durations.

| Run | Passed | Failed | Errors | Skipped | Duration |
| --- | ---: | ---: | ---: | ---: | ---: |
| Relevant pre-change baseline, isolated base copy | 276 | 0 | 0 | 0 | 69.959 s |
| New direct service tests, isolated candidate | 23 | 0 | 0 | 0 | 5.596 s |
| Relevant post-change regression, isolated candidate | 299 | 0 | 0 | 0 | 71.000 s |
| Full regression, actual project | 1031 | 0 | 0 | 22 | 413.269 s |

The relevant baseline comprises test_us01.py, test_us03.py, test_us09.py,
test_us11.py, test_personal_interest_descriptions.py, test_sprint3_be1.py,
test_sprint3_be2.py, test_sprint3_be4.py and test_us11_review_regressions.py under
backend/tests/. Candidate regression adds test_sprint3_be3.py.

All 276 baseline identities and passed outcomes are retained in both the
299-case candidate run and the final project run. The 23 additional candidate
cases belong to the new direct service suite and all pass in the final run.

The full run collected 1053 cases and reported 18 warnings. Its terminal summary
was **1031 passed, 22 skipped, 18 warnings in 413.31s (0:06:53)**. There was no
complete pre-change full-suite execution at this base, so the 276-case relevant
baseline is the executed before/after comparison. Earlier BE-2 full-suite totals
also reflect a different upstream base.

## 4. Direct service coverage

The new suite asserts that neither a Flask application context nor an HTTP
request context is active when invoking profile operations. Fresh database
snapshots verify rejected operations and rollback across all mapped tables.

| Scenario | Cases |
| --- | ---: |
| Save, confirm, canonical no-op, repeated confirmation and later edit | 1 |
| Stale save and stale confirmation | 2 |
| Blank name, whitespace-only name and absent confirmable content | 3 |
| Legacy omission and explicit clearing of the three companion fields | 3 |
| Personal-tag normalization, deduplication, shared resolution and canonical no-op | 1 |
| Another owner's personal tag cannot be selected or changed | 1 |
| Invalid shared tag, duplicate record, combined-count limit and invalid label | 4 |
| Save, confirmation and import reject a missing caller write lock | 3 |
| Save rollback after flushed tag resolution, content writes or final serialization | 3 |
| Confirmation rollback after its flushed write and failed serialization | 1 |
| Ordinary no-op versus identical import and stale import replay | 1 |
| Total | 23 |

Save fault-injection cases assert that a real personal-tag write was visible in
the caller's Session before raising the injected exception. Fresh queries after
rollback match the complete pre-operation snapshot. The original input values
and canonical saved output are checked separately.

## 5. BE-4 integration evidence

All 43 BE-4 test cases passed against SQLite. The recorded evidence contains:

- 60 synchronized race rounds: 10 each for save/save, import/manual save,
  confirmation/edit, duplicate import/stale retry, privacy/privacy and
  opportunity writes. Each records the second writer requesting the lock while
  the first still holds it.
- 22 fault-injection cases: 10 save, 10 import and 2 confirmation. All record
  rollback and a successful subsequent retry.
- Six lock-first controls, covering every revision-write route, plus a negative
  control with the writer lock deliberately removed. The negative control's
  observed 200/500 outcome demonstrates the unsafe interleaving expected by that
  test; it is not an unresolved suite failure.

These results establish this execution's SQLite behaviour. The corresponding
actual-MySQL concurrency and recovery acceptance was not run here.

## 6. Frontend and application-model integration

All 18 real HTTP/frontend integration cases passed across
`test_frontend_integration.py`, `test_us09_frontend_integration.py`,
`test_fe3_frontend_integration.py` and `test_fe4_frontend_integration.py`.
They include the existing PDF/DOCX review consumers and profile/editor flows.
All 12 existing BE-2 direct service cases also passed.

The full command enabled `--require-frontend` and `--require-application-model`.
The current real-model checks below passed:

- test_requirement_scoring.py::test_real_chinese_synonyms_and_distinct_meanings_through_http
- test_semantic_matching.py::test_real_minilm_runs_in_owner_and_team_http_matching
- test_sprint3_be7.py::test_real_chinese_negation_and_collection_consistency

The application configuration pins
`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, model version
`multilingual-minilm-requirements-onnx-v1`, revision
`e8f8c211226b894fcb81acc59f3b34ba3efd5f42`.

This run does not establish separate frontend typecheck, build, formatting or
manual-browser acceptance. The optional historical US-13 reproduction uses
separate resources and remains one of the skipped checks below.

## 7. Skips and warnings

| Module | Skipped | Reason |
| --- | ---: | --- |
| test_docker_stack.py | 3 | Docker Compose unavailable for configuration and real-stack checks. |
| test_public_sharing.py | 4 | Docker Compose required for deployment/configuration checks. |
| test_mysql.py | 5 | Requires --run-mysql and a disposable MYSQL_TEST_DATABASE_URL. |
| test_us18.py | 8 | Legacy MySQL upgrade checks require --run-mysql. |
| test_sprint3_be9.py | 1 | Requires --run-docker for the isolated MySQL 8.4 recovery rehearsal. |
| test_us13.py | 1 | Optional historical MiniLM reproduction resources unavailable. |
| Total | 22 | These checks were not verified by this execution. |

The additional skip compared with the earlier BE-2 full report is the upstream
BE-9 recovery rehearsal. The 18 warnings concern record_property compatibility
with JUnit xunit2 in test_sprint2_data_preparation.py and test_us16.py; they did not
cause failures. Existing expectations were not weakened to suppress failures.

## 8. Reproduction

Run from the repository root using a Python 3.13 environment with project test
dependencies, frontend dependencies and the pinned application model prepared.
The virtual environment's local name is arbitrary.

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTEST_ADDOPTS = (($env:PYTEST_ADDOPTS + ' -p no:cacheprovider').Trim())

$be3Evidence = Join-Path ([System.IO.Path]::GetTempPath()) ('be3-full-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $be3Evidence | Out-Null

$env:PYTEST_DEBUG_TEMPROOT = Join-Path $be3Evidence 'pytest-temp'
New-Item -ItemType Directory -Path $env:PYTEST_DEBUG_TEMPROOT | Out-Null

$env:BE4_ROUNDS = '10'
$env:BE4_EVIDENCE = Join-Path $be3Evidence 'be4-evidence.json'

python -B -m pytest backend/tests -q -ra --require-frontend --require-application-model --basetemp="$be3Evidence\tmp-main" --junitxml="$be3Evidence\be3-full.xml" 2>&1 | Tee-Object -FilePath "$be3Evidence\be3-full.log"
```

Reports, logs and temporary test data are directed outside the checkout.

## 9. Evidence and handoff

The original full-run artifacts were created in the system temporary directory
under `be3-full-0abab22ce353451492e8f73b77faa40c`. Unchanged copies are retained in
the external workspace archive, outside the project repository:

- reports/be3-full-0abab22ce353451492e8f73b77faa40c/be3-full.xml
- reports/be3-full-0abab22ce353451492e8f73b77faa40c/be3-full.log
- reports/be3-full-0abab22ce353451492e8f73b77faa40c/be4-evidence.json

Full XML SHA-256:

`35c39dfcbd8c40ca9666a84b51b734516c7b8e2786ab7083cbf084a80739710b`

Preparation artifacts remain in the external workspace under
`output/sprint3-be3-75f7b827/baseline/`, `direct/` and `regression/`. These archive
paths identify local evidence; they are not repository files or requirements
for another developer's environment. A new run creates a new output directory.

Local BE-3 implementation and executed regression acceptance: **PASS**.
Before closing the task, record the final implementation commit, MR and owner,
and satisfy the applicable integration, pipeline and review requirements.
Actual MySQL/Docker acceptance and full Sprint 3 release acceptance are not
established by this local run.

No data migration is required. Revert the BE-3 code changes together when rolling
back so service imports and the shared state transition remain consistent.
