# BE-1 Regression Baseline and Verification Report

## 1. Execution environment

| Item | Value |
| --- | --- |
| Task | BE-1: API contracts, error semantics and regression baseline |
| Base commit | 3a15eff07d0f23ccbde4b8119049c75ab55b5d11 |
| Branch | H18ABANANA-70-EstablishAPIContracts |
| Operating system | Windows |
| Virtual environment | demo313 |
| Python | 3.13.17 |
| pytest | 8.4.2 |
| Default test database | Temporary SQLite databases |
| SQLite runtime | 3.50.4 |
| Flask / SQLAlchemy | 3.1.2 / 2.0.44 |
| ONNX Runtime / NumPy / tokenizers | 1.23.2 / 2.3.4 / 0.22.1 |

The source tree was clean before the initial baseline run.

The final verification used the same base commit with local BE-1 changes.
Those changes were not yet committed when tested. The final MR/commit and
responsible owner must be recorded during handoff.

## 2. Pre-change baseline

Run started: 2026-11-15 16:27:24 AEDT (Australia/Sydney).

The following command was executed from the repository root:

`python -m pytest backend/tests -q -ra --junitxml=reports/be1-before.xml`

After execution, the XML was moved outside the repository to
COMP3900/reports/be1-before.xml.

Baseline XML SHA-256:

`e04d36749d7ecc8a12c2824582df07dfda15156649a734180e3f2c2f7364b253`

JUnit suite duration: 403.883 seconds.
Terminal duration: 403.92 seconds.

No failing tests or execution errors were observed in this baseline.

## 3. Changes verified

- Added backend/tests/test_sprint3_be1.py.
- Updated docs/api/examples/error-validation.json to match the current
  empty skill-title validation error.
- Corrected profile omission, publication and ranking descriptions in
  docs/api/openapi.json.
- Updated publication and ranking descriptions in
  docs/api/sprint-1-api-contract.md.
- Added the baseline report and contract review matrix.

No production route/service behaviour, database schema or dependency
change was introduced by BE-1.

## 4. Post-change verification

Run started: 2026-11-15 20:11:25 AEDT (Australia/Sydney).

The final run required real frontend integration and the current
application model through --require-frontend and
--require-application-model.

The following setup and command reproduce the verification structure.
Run from the repository root with demo313 activated:

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTEST_ADDOPTS = (($env:PYTEST_ADDOPTS + ' -p no:cacheprovider').Trim())

$be1Evidence = Join-Path (Resolve-Path '..\..').Path ('reports\be1-full-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $be1Evidence | Out-Null

$env:PYTEST_DEBUG_TEMPROOT = Join-Path $be1Evidence 'pytest-temp'
New-Item -ItemType Directory -Path $env:PYTEST_DEBUG_TEMPROOT | Out-Null

python -B -m pytest backend/tests -q -ra --require-frontend --require-application-model --basetemp="$be1Evidence\tmp-main" --junitxml="$be1Evidence\be1-full-after.xml" 2>&1 | Tee-Object -FilePath "$be1Evidence\be1-full-after.log"
```

Reports, logs and temporary databases are directed outside the project
checkout. Child pytest processes inherit the cache and bytecode settings.

## 5. Before/after comparison

| Outcome | Before | After |
| --- | ---: | ---: |
| Collected tests | 908 | 967 |
| Passed | 887 | 946 |
| Failed | 0 | 0 |
| Errors | 0 | 0 |
| Skipped | 21 | 21 |
| Terminal warnings | 18 | 18 |

Post-change JUnit suite duration: 400.590 seconds.
Post-change terminal duration: 400.62 seconds.

Comparison by JUnit class name and test name found all 908 original
cases present with unchanged outcomes and, for skipped cases, unchanged
skip messages.

All 59 additional cases passed. No unresolved regression was observed
in this local run.

## 6. Added regression coverage

| Check | Cases |
| --- | ---: |
| Indexed fixtures validate against their referenced schemas | 49 |
| Current invalid skill-title response matches the validation fixture and preserves the profile | 1 |
| Profile save/confirmation conflicts report the database revision | 2 |
| Privacy conflict reports its independent database revision and preserves profile confirmation | 1 |
| Apply preserves QUEUED, PROCESSING and FAILED error semantics | 3 |
| Stale apply reports the database revision and preserves confirmation | 1 |
| Opportunity save/publication conflicts report the database revision and preserve the draft | 2 |
| Total | 59 |

Existing permission, partial-import, clearing, provenance, expiry,
ranking, visibility and scoring tests were reused in the full regression.

The corresponding business rules, interfaces and tests are mapped in
sprint3-be1-contract-matrix.md.

## 7. Skipped checks

All 21 skips were present in both runs with unchanged reasons.
Individual test identities and messages are preserved in the raw XML.

| Test module | Count | Reason |
| --- | ---: | --- |
| test_docker_stack.py | 3 | Docker Compose was not available to the test process. |
| test_public_sharing.py | 4 | Docker Compose was required for deployment/configuration checks. |
| test_mysql.py | 5 | Requires --run-mysql and a disposable MYSQL_TEST_DATABASE_URL. |
| test_us18.py | 8 | Legacy database upgrade checks require --run-mysql. |
| test_us13.py | 1 | The optional historical MiniLM reproduction check lacked its required model resources. |

Skipped checks are unverified coverage, not successful checks.

This execution does not establish Docker deployment, MySQL or historical
US-13 model reproduction acceptance.

## 8. Warnings

Both runs reported 18 warnings concerning record_property being
incompatible with the default JUnit xunit2 format.

They originated from test_sprint2_data_preparation.py and test_us16.py.
They concern additional report metadata and did not cause test failures.

No existing test expectations were changed to suppress warnings or
conceal failures.

## 9. Integration and current model evidence

The final run executed 18 tests across:

- test_frontend_integration.py
- test_us09_frontend_integration.py
- test_fe3_frontend_integration.py
- test_fe4_frontend_integration.py

All passed with --require-frontend.

These are real HTTP/frontend integration checks. This run does not claim
separate frontend build, formatting, typecheck or manual-browser acceptance.

The following current application model HTTP checks passed with
--require-application-model enabled:

- test_requirement_scoring.py::test_real_chinese_synonyms_and_distinct_meanings_through_http
- test_semantic_matching.py::test_real_minilm_runs_in_owner_and_team_http_matching
- test_sprint3_be7.py::test_real_chinese_negation_and_collection_consistency

Recorded model metadata:

- Model: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
- Model version: multilingual-minilm-requirements-onnx-v1
- Model revision: e8f8c211226b894fcb81acc59f3b34ba3efd5f42
- Scoring version: requirement-semantic-v1

The skipped historical US-13 model check is separate from these executed
application model checks.

## 10. Failure and recovery during development

One intermediate run of the added suite produced 56 passes and one failure.

The FAILED-state apply case set the document status without populating
its error, violating the existing database CHECK constraint during test
setup. The HTTP request had not executed.

The test setup was corrected to supply an EXTRACTION_FAILED error for
FAILED and None for other states. The expected HTTP status and error-code
assertions were preserved.

Subsequent runs passed 57 cases, then 59 cases after the opportunity checks
were added, followed by the passing full regression above.

This was an added test-data preparation defect, not an observed baseline
API regression. The failed-run XML was retained outside the checkout.

## 11. Raw execution evidence

Paths below are relative to the surrounding COMP3900 workspace, outside
the project repository:

- Baseline XML:
  reports/be1-before.xml
- Intermediate failed setup:
  reports/be1-a0f01697bfec4331868283f5c64dbb9c/be1-after.xml
- Final XML:
  reports/be1-full-ada0da5555f242d78fa824ec5a69b48b/be1-full-after.xml
- Final log:
  reports/be1-full-ada0da5555f242d78fa824ec5a69b48b/be1-full-after.log

Final XML SHA-256:

`620789216c01f8b7186a6d50e3458ecb2bb45bbe0e4dc62a58ed46232de39cde`

Raw execution artifacts are not committed.

## 12. Acceptance status and handoff

Local BE-1 implementation and regression checks: PASS.

Contract review and rule-to-test mapping are recorded in
sprint3-be1-contract-matrix.md.

Before marking the work item Done, record:

- Final MR/commit.
- Responsible owner.
- FE-1 agreement on shared fixtures and validation/error expectations.

FE-1 source compatibility was reviewed. Separate owner agreement has not
been recorded in this report.

Docker deployment, MySQL and the skipped historical model reproduction
remain explicitly unverified by this execution.

Reverting the BE-1 documentation, fixture and regression-test changes
requires no data migration.

This report does not establish full Sprint 3 release acceptance.
