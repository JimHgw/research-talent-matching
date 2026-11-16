# BE-2 Reviewed Document Import Verification

## 1. Scope and environment

| Item | Value |
| --- | --- |
| Task | BE-2: Extract the Reviewed Document Import Application Service |
| Branch | H18ABANANA-71-BE-2 |
| Base commit | 77ab806131b6ae2a666f890ca1a17ab7abfffa1e |
| Operating system | Windows |
| Python | 3.13.17 |
| pytest | 8.4.2 |
| Default test database | Temporary SQLite databases |
| SQLite runtime | 3.50.4 |
| Flask / SQLAlchemy | 3.1.2 / 2.0.44 |
| ONNX Runtime / NumPy / tokenizers | 1.23.2 / 2.3.4 / 0.22.1 |

The verification exercised local BE-2 changes on the base commit above.
The BE-2 changes were uncommitted when these tests ran. The final
implementation commit, MR and responsible owner must be recorded at handoff.

## 2. Implementation

The reviewed import operation is implemented by
apply_reviewed_extraction in
backend/src/features/documents/service.py.

Responsibilities are separated as follows:

| Module | Responsibility |
| --- | --- |
| documents/routes.py | Authentication, CSRF, request parsing, transaction boundary and HTTP response |
| documents/service.py | Ownership, extraction state, revision checks, tag-resolution orchestration, import and confirmation invalidation |
| documents/repository.py | Document/reference-data reads and reviewed content/provenance writes |
| documents/review.py | Validation of resolved sections against supplied reference data |
| profile/repository.py | Owner-profile queries and related-data loading |
| profile/serialization.py | Response assembly from loaded data |

Module paths above are relative to backend/src/features/.

Document routes no longer import profile/routes.py.

The HTTP route retains the original ownership-before-body error order.
The service independently checks ownership for direct callers.

The caller authenticates/authorizes the actor and establishes the protected
write transaction before invoking the service. The service and repositories
use the supplied Session and do not commit or open nested transactions.

Existing SQLite write protection and MySQL write locking remain unchanged.
File parsing and model inference are not performed by the import service.

## 3. Preserved behaviour

- An owned READY document and valid current revision can be imported.
- Only supplied sections are replaced, subject to existing shared-label
  normalisation rules.
- Omitted content and provenance are preserved.
- Explicit empty lists and allowed empty strings clear selected components.
- Every successful import increments the profile revision once, including
  an identical-content import using the current revision.
- Successful imports set UNCONFIRMED and clear confirmedRevision/confirmedAt.
- Profile confirmation remains a separate operation.
- QUEUED/PROCESSING returns 409 / EXTRACTION_NOT_READY.
- FAILED returns 422 / EXTRACTION_FAILED.
- Inaccessible documents return 404 / NOT_FOUND.
- Stale imports return 409 / REVISION_CONFLICT with the current revision.
- Rejected imports and failed transactions preserve existing stored state.
- Reviewed values retain existing schema limits and supported fields.
- Request sections are copied before normalisation.

No public API schema, database schema or dependency changes were introduced.

## 4. Execution history

Durations below are JUnit suite durations.

| Run | Passed | Failed | Errors | Skipped | Duration |
| --- | ---: | ---: | ---: | ---: | ---: |
| Shared query/serialization extraction | 187 | 0 | 0 | 0 | 65.300 s |
| Initial application-service extraction | 149 | 33 | 5 | 0 | 40.213 s |
| Corrected route wiring | 187 | 0 | 0 | 0 | 38.336 s |
| Direct service acceptance | 12 | 0 | 0 | 0 | 3.003 s |
| Final full regression | 958 | 0 | 0 | 21 | 398.279 s |

The 187-case targeted group comprised test_us01.py, test_us03.py,
test_us09.py, test_us11.py and test_sprint3_be1.py under backend/tests/.

### Intermediate failure and correction

The initial extraction left the old route-level own_document function in
documents/routes.py. That definition shadowed the Repository import and
referenced validator/invalid imports that had been removed.

The resulting NameError was converted into INTERNAL_ERROR responses.
Document reads/downloads and extraction checks failed, and dependent READY
document fixtures produced setup errors.

The obsolete route-level function was removed so callers use the Repository
implementation. The targeted group then passed all 187 cases.

No test expectations were weakened to conceal the failure. The failed-run
XML was retained outside the project.

## 5. Direct service coverage

backend/tests/test_sprint3_be2.py prepares isolated database data and invokes
the service without making HTTP requests. Its invocation helper asserts
that no HTTP request context is active.

| Scenario | Cases |
| --- | ---: |
| Skills-only import, preserved omitted data/origins, stale replay and identical-content import at the current revision | 1 |
| Explicit clearing of skills, researchInterestText and resumeDescription | 3 |
| QUEUED, PROCESSING and FAILED errors | 3 |
| Other-owner document hidden before payload validation | 1 |
| Stale import preserves confirmed profile and catalogue | 1 |
| Canonical personal tags without mutating caller input | 1 |
| Failure after tag resolution or reviewed writes have been flushed | 2 |
| Total | 12 |

Fault-injection cases confirm that a real personal-tag write occurred before
raising the injected exception. The exception propagates through the caller's
transaction.

After rollback, fresh queries verify the original profile content, revision,
confirmation, provenance and personal-tag catalogue/detail/selection counts.

## 6. Final regression comparison

The reference is the final BE-1 regression run recorded in
docs/api/sprint3-be1-baseline.md.

| Outcome | BE-1 reference | BE-2 final |
| --- | ---: | ---: |
| Collected tests | 967 | 979 |
| Passed | 946 | 958 |
| Failed | 0 | 0 |
| Errors | 0 | 0 |
| Skipped | 21 | 21 |
| Terminal warnings | 18 | 18 |

Comparison by JUnit class name and test name found all 967 reference cases
present with unchanged outcomes and unchanged skip messages.

All 12 added cases passed. No unresolved local regression was observed.

The final run started at 2026-11-15 22:32:00 AEDT (Australia/Sydney).
Terminal duration was 398.30 seconds.

## 7. Frontend and model integration

The final run enabled --require-frontend and --require-application-model.

All 18 cases across the following real HTTP/frontend integration modules
passed:

- test_frontend_integration.py
- test_us09_frontend_integration.py
- test_fe3_frontend_integration.py
- test_fe4_frontend_integration.py

These include PDF/DOCX document workflows and the existing review consumers.

Representative current application model checks also passed:

- test_requirement_scoring.py::test_real_chinese_synonyms_and_distinct_meanings_through_http
- test_semantic_matching.py::test_real_minilm_runs_in_owner_and_team_http_matching
- test_sprint3_be7.py::test_real_chinese_negation_and_collection_consistency

Recorded model metadata:

- Model: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
- Model version: multilingual-minilm-requirements-onnx-v1
- Model revision: e8f8c211226b894fcb81acc59f3b34ba3efd5f42
- Scoring version: requirement-semantic-v1

This execution does not claim separate frontend build, typecheck,
formatting or manual-browser release acceptance.

## 8. Skips and warnings

All 21 skips match the BE-1 reference:

| Module | Count | Reason |
| --- | ---: | --- |
| test_docker_stack.py | 3 | Docker Compose unavailable to the test process |
| test_public_sharing.py | 4 | Docker Compose required for deployment/configuration checks |
| test_mysql.py | 5 | Requires --run-mysql and a disposable MYSQL_TEST_DATABASE_URL |
| test_us18.py | 8 | Legacy upgrade checks require --run-mysql |
| test_us13.py | 1 | Historical model reproduction resources unavailable |

Skipped checks are unverified coverage, not passes. The historical US-13
skip does not replace or invalidate the executed current application model
checks.

The 18 warnings concern record_property compatibility with JUnit xunit2
in test_sprint2_data_preparation.py and test_us16.py. They match the reference
run and did not cause test failures.

## 9. Reproduction

Run from the repository root with a Python 3.13 virtual environment activated
and the project test dependencies installed:

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTEST_ADDOPTS = (($env:PYTEST_ADDOPTS + ' -p no:cacheprovider').Trim())

$be2Evidence = Join-Path ([System.IO.Path]::GetTempPath()) ('be2-full-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $be2Evidence | Out-Null

$env:PYTEST_DEBUG_TEMPROOT = Join-Path $be2Evidence 'pytest-temp'
New-Item -ItemType Directory -Path $env:PYTEST_DEBUG_TEMPROOT | Out-Null

python -B -m pytest backend/tests -q -ra --require-frontend --require-application-model --basetemp="$be2Evidence\tmp-main" --junitxml="$be2Evidence\be2-full.xml" 2>&1 | Tee-Object -FilePath "$be2Evidence\be2-full.log"
```

Reports, logs and temporary databases are stored outside the project.
Raw execution artifacts are not committed.

## 10. Evidence locations

Paths below are relative to the original surrounding COMP3900 workspace.
They identify the local evidence archive, not repository files or
prerequisites for reproduction. A new run creates its own external output
directory:

- Shared extraction:
  reports/be2-step1-0b19526f954e4d0b9045f8aa547aeb1e/be2-step1.xml
- Failed route wiring:
  reports/be2-step2-c852f09f6f634365b760361e7f3eef88/be2-step2.xml
- Corrected route wiring:
  reports/be2-step2-fix-0f3a2403dbce4fb79a0be59680f84dbd/be2-step2.xml
- Direct service suite:
  reports/be2-direct-6d6b6f7b913e47d0a2c68b84f297c973/be2-direct.xml
- Final regression:
  reports/be2-full-200acc1d46cc46aabda37489bacd63bc/be2-full.xml
- Final log:
  reports/be2-full-200acc1d46cc46aabda37489bacd63bc/be2-full.log

Final XML SHA-256:

`737dfe75862ceb30aef8dd59a982460d0ad67af73fc6956f293a0e353482a85c`

## 11. Acceptance and handoff

Local BE-2 implementation, direct service tests and full regression: PASS.

Remaining delivery records/actions:

- Record the implementation commit, MR and responsible owner.
- Synchronise with the relevant merged upstream changes and verify the
  integrated result against the resulting base.
- Confirm the BE-3 shared-module interface and BE-4 transaction/concurrency
  integration as those dependent changes become available.
- Verify the latest MR pipeline and project review requirements.

The shared profile query/serialization foundation is provided here.
Full SaveProfile/ConfirmProfile extraction remains BE-3 scope.
MySQL and multi-connection concurrency acceptance are not established by
this SQLite run and remain part of the relevant BE-4 verification.

No data migration is required. A rollback must revert the BE-2 change set
together so route imports and shared modules remain consistent.

This report does not establish full Sprint 3 release acceptance.
