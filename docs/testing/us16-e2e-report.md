# US-16 end-to-end validation

## Decision

**Ready for demonstration with known limitations.** This means a controlled local demonstration using the synthetic dataset, not deployment or real-input acceptance. **US-16 is not fully complete:** four acceptance cases remain BLOCKED. No product defect was confirmed by this run. Do not treat unavailable checks as passes.

## Environment and scope

- Run date: 2026-10-31, Australia/Sydney; Windows, Python 3.12; exact platform/runtime recorded in [results](us16/results.json).
- Branch: `test/us16-e2e-validation`.
- Base main: `999291aa5d8da20861e62f6d5376487ceb4a21ec`.
- Tested code commit: 368849bb062519e73f9a265b625cb8cc9d1ea9f8.
- Non-Docker isolated SQLite, Flask clients and real loopback HTTP, actual React workflows in Node/jsdom. These are not full browser visual acceptance tests.
- Supplemental native browser: frontend `http://127.0.0.1:5176`, backend `http://127.0.0.1:18716`; source URL enabled. Both temporary servers stopped after observation. No shared deployment was accessed.
- No product logic or CI configuration changed. Existing documents, shared databases and pre-existing `test-output/` were preserved.

Investigated `.gitlab-ci.yml`, `compose.yaml`, the three root README files, existing backend/frontend tests and source, scripts and testing documentation. Existing registration, profile, document, privacy, opportunity, matching, search, source URL, deadline and locale tests were reused. Source URL display is feature-gated; Docker defaults do not enable it. Role switching means changing authenticated accounts while retaining server-authoritative roles. SMTP verification is tested with the existing isolated outbox, not external delivery.

## Dataset

H18ABANANA-40 dataset **sprint2-synthetic-v2**: 10 talent profiles, 7 opportunities (6 published, 1 draft), 2 team accounts, 12 total accounts and 12 independent matching/access labels. See `backend/tests/data/sprint2/manifest.json`, `talents.json`, `opportunities.json` and `expected-results.json`.

`backend/tests/data_preparation.py::prepare_run` provisions a fresh database and private upload directory per run, refuses an existing destination and overrides ambient database configuration. Scenario edits use normal endpoints inside fresh test databases; original labels and dataset files were not changed. Reset means prepare another new directory, not delete or overwrite a database:

```powershell
.venv\Scripts\python.exe scripts/prepare-test-data.py --run-dir data/sprint2-runs/us16-next-run
```

The name above must be unused. No credentials belong in reports. The new six executions reuse this prepared dataset, including the unconfirmed document account. Existing tests retain their established isolated fixtures; they are not misrepresented as all using prepared records. Per-case `datasetUsage` distinguishes them.

**Authorised real examples: zero.** `sourceStatus=AUTHORISED_REAL_INPUT_REQUIRED` remains a dependency blocker. No general matching accuracy or client real-data acceptance is inferred.

## Results

24 acceptance cases: **20 PASS, 0 FAIL, 4 BLOCKED, 0 NOT READY, 0 NOT APPLICABLE**. Case totals are not individual pytest totals. [Plan](us16/plan.json) contains fixed expectations; [results](us16/results.json) records environment, steps, actual assertion outcomes, evidence references, defects and retests for every case.

| Case | Story | Result | Individual checks |
|---|---|---|---:|
| E2E-AUTH-01 | US-15 / US-01 | PASS | 12 |
| E2E-AUTH-02 | US-15 | PASS | 5 |
| E2E-AUTH-03 | US-15 / US-01 | PASS | 2 |
| E2E-PROFILE-01 | US-03 / US-10 | PASS | 13 |
| E2E-DOC-01 | US-09 / US-11 | PASS | 2 |
| E2E-DOC-02 | US-09 / US-10 | PASS | 17 |
| E2E-REGRESSION-35 | H18ABANANA-35 | PASS | 2 |
| E2E-PRIVACY-01 | US-05 / US-10 | PASS | 2 |
| E2E-OPP-01 | US-02 | PASS | 51 |
| E2E-MATCH-01 | US-04 / US-05 / H18ABANANA-40 | PASS | 13 |
| E2E-MATCH-02 | US-18 | BLOCKED | 14 |
| E2E-SEARCH-01 | US-14 | PASS | 17 |
| E2E-SOURCE-01 | US-19 | PASS | 30 |
| E2E-EXPIRY-01 | US-20 | PASS | 36 |
| E2E-LANG-01 | US-21 | PASS | 2 |
| E2E-SESSION-01 | US-15 / US-10 | PASS | 1 |
| E2E-PROFILE-02 | US-10 | PASS | 1 |
| E2E-SEARCH-02 | US-14 | PASS | 1 |
| E2E-EXPIRY-02 | US-19 / US-20 | PASS | 1 |
| E2E-SEMANTIC-01 | US-13 | PASS | 9 |
| E2E-SEMANTIC-02 | US-13 | PASS | 1 |
| E2E-DATA-01 | H18ABANANA-40 | BLOCKED | 0 |
| E2E-ENV-01 | US-16 | BLOCKED | 0 |
| E2E-SOURCE-02 | US-19 | BLOCKED | 0 |

Representative observed outcomes:

- Independent talent/team sessions: unauthorized team profile write returned 403 without changing content; hidden evidence became UNKNOWN with no evidence; revoked discovery returned 404 and disappeared from results; talent logout left the team signed in.
- Profile edit incremented revision, removed confirmation and returned 409 for owner matching until reconfirmation; a second owner session read the saved content; reconfirmation restored six recommendations.
- Prepared opportunity query totals were 6/1/6/1/0; team query totals 4/0/4; explicit empty API query returned 422. UI empty input/reset behaviour is covered separately by the existing live test.
- Deadline at one microsecond before/exactly at/after the boundary produced 1/0/0 matching list results; expired discovery returned 409 while published detail remained readable.
- Source persistence, validation and rendered attributes passed. Actual browser activation created a tab targeting `https://example.org/`, but destination loading failed with `ERR_NAME_NOT_RESOLVED`; the original application remained usable with six opportunities.
- Academic explanations passed on SQLite and the live interface; eight MySQL upgrade variants remain skipped. E2E-MATCH-02 therefore remains BLOCKED, not PASS.
- Real pinned model inference passed in both owner and team HTTP matching. This checks workflow behaviour, not a new quantitative quality study.

## H18ABANANA-35

The base already contains fix `07f3ffc` (integrated by `56cfeb5`). This is repository evidence, not an assertion about Jira status. Dedicated **E2E-REGRESSION-35 PASS** was established by executing both PDF and DOCX with the existing real upload/worker/React workflow. Assertions cover suggestions, absence of `not-recording`, correction, section selection, apply, changed profile revision and reconfirmation. The only existing test helper change permits the prepared account identifier and retains its original default. No teammate product implementation was changed.

## Executed checks and commands

All commands ran from the repository root with its existing virtual environment, except one initial runtime command launched from the parent directory and failed before pytest started; it was immediately rerun from the root. Logs are private ignored `.pytest_cache/us16-*.txt`; durable JUnit summaries omit captured output, hostnames and local paths. The initial failure remains in [cases-initial.xml](us16/evidence/cases-initial.xml).

```powershell
.venv\Scripts\python.exe -m pytest backend/tests --require-frontend -q --tb=short --junitxml=.pytest_cache/us16-baseline.xml
# 728 passed, 16 skipped, 12 warnings, 304.71s
.venv\Scripts\python.exe -m pytest backend/tests/test_us16.py --require-frontend -q --tb=short --junitxml=.pytest_cache/us16-cases-initial.xml
# 5 passed, 1 failed: test request used unsupported skills parameter
.venv\Scripts\python.exe -m pytest backend/tests/test_us16.py --require-frontend -q --tb=short -o junit_family=legacy --junitxml=.pytest_cache/us16-cases.xml
# 6 passed, 23.50s; unchanged expected outcomes
.venv\Scripts\python.exe -m pytest backend/tests/test_semantic_matching.py backend/tests/test_us16.py --require-frontend -q --tb=short -o junit_family=legacy --junitxml=.pytest_cache/us16-runtime.xml
# 33 passed, 34.87s
.venv\Scripts\python.exe -m pytest backend/tests/test_us13.py -q --tb=short -o junit_family=legacy --junitxml=.pytest_cache/us16-semantic-evaluation.xml
# 12 passed, 1.22s
.venv\Scripts\python.exe scripts/dev.py frontend test
# 260 passed, 0 skipped
.venv\Scripts\python.exe scripts/dev.py frontend format:check
# PASS
.venv\Scripts\python.exe scripts/dev.py frontend build
# PASS; 109 modules transformed
```

API validation executed Python `json.load` across `docs/api/**/*.json`: **51 valid files**, including OpenAPI, indexes and examples. `git diff --check` passed. No skipped tests were introduced, assertions removed or CI jobs weakened.

The initial backend run skipped one Docker test, five MySQL tests, eight MySQL academic upgrade variants and two real-model tests. The latter two passed after installing `backend/requirements-semantic.txt` and downloading the pinned model through the existing checksum-verifying downloader. Latest-result aggregation is **736 passed, 14 environment-skipped** across 750 unique backend test IDs; do not add repeated runs together. Frontend totals are separate. Docker server probe `docker version --format '{{.Server.Version}}'` failed because its Linux engine pipe was absent. No migration or stack command was run against an existing database.

The baseline's JUnit warnings concern property compatibility; the dedicated retest uses legacy JUnit for dataset metadata. No warning was treated as a pass/failure override.

Rebuild the acceptance report from the committed evidence, ordered so a later exact test replaces its earlier result:

```powershell
.venv\Scripts\python.exe scripts/us16-report.py --base 999291aa5d8da20861e62f6d5376487ceb4a21ec --junit docs/testing/us16/evidence/baseline.xml --junit docs/testing/us16/evidence/cases.xml --junit docs/testing/us16/evidence/runtime.xml --junit docs/testing/us16/evidence/semantic-evaluation.xml
```

This command only maps evidence; it does not rerun tests. It fails for failed/missing selected checks; blocked cases are explicitly retained. The recorded `codeCommit` is the tested code commit; the documentation commit is later. The captured working-tree state precedes the documentation commit and is not a claim of final dirtiness.

## Defects, limitations and follow-up

[Structured records](us16/defects.json) include reproduction, environment, expected/observed outcomes, severity, evidence, investigation and retest status.

| ID | Classification | Outcome |
|---|---|---|
| US16-TEST-01 | Low, new test request defect | RESOLVED: `skills` corrected to documented `skill`; zero-result expectation unchanged; exact retest passed twice |
| US16-ENV-01 | Medium, environment | BLOCKED: Docker/MySQL deployment and upgrade acceptance unavailable |
| US16-DEP-01 | Medium, dependency | BLOCKED: authorised real source examples absent |
| US16-ENV-02 | Low, environment | BLOCKED: external destination DNS failure; tab activation verified |

No product root cause is invented. To close acceptance, provide a disposable Docker/MySQL environment, approved talent/opportunity examples with independent labels, and working DNS for the safe source-link retest. Run existing opt-in MySQL/Docker checks only against disposable targets. External SMTP delivery and broad graphical/cross-browser acceptance are not established here.

Documentation improvement: `docs/testing/sprint2-data-preparation.md` still says deadlines are absent, while the current opportunity implementation and US-20 tests support them. Update that guidance in its owning documentation work; the dataset was not silently changed.

## Change and Git record

- `backend/tests/test_us16.py`: six prepared-data executions for session/privacy, revision/reconfirmation, search, source/deadline and both document formats.
- `frontend/tests/us09-live.mjs`: optional prepared login identifier; original default preserved.
- `scripts/us16-report.py`: deterministic evidence-to-case mapping with fail/missing-check detection.
- `docs/testing/us16/plan.json`: 24 structured cases and independent expectations.
- `docs/testing/us16/results.json`: executed case/environment/evidence results.
- `docs/testing/us16/defects.json`: one resolved test defect and three limitations.
- `docs/testing/us16/evidence/*.xml`: baseline, preserved failure, retest and runtime evidence without captured logs.
- This report: readiness and reproducibility record.

Local code commit: `368849bb062519e73f9a265b625cb8cc9d1ea9f8`. The final documentation commit can be identified with `git log -2` on this branch. Main was only fast-forward synchronized with origin/main as requested before branch creation; its content was not edited and no new commit was made on main. Nothing was pushed, no branch was merged and no Merge Request was created. Pre-existing untracked `test-output/` is excluded from both commits. No remote Pipeline is claimed for these local-only commits.
