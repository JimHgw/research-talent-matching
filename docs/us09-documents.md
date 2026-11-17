# US-09 document upload, extraction and reviewed import

PDF and DOCX files up to 10 MiB are optional. Originals are stored privately;
only their authenticated talent owner can list, download, inspect or import
them. Upload/extraction never changes the current profile or its confirmation.
The review screen lets the owner edit and select sections. Applying them replaces
only those sections, checks the profile revision, records the document origin
and requires a separate profile confirmation before matching uses the new data.

## Running the worker

The root Compose stack and both `docker-backend` launchers start
`document-worker` automatically alongside the API. They use the same application
image, MySQL database and private `/app/data/documents` directory. The worker has
no published port; Compose restarts it if its process exits.

For native development, after the usual setup, `prepare-db` and `seed-tags`,
keep a third terminal open at the repository root:

```powershell
.\.venv\Scripts\python.exe -m flask --app backend.app process-documents
```

On macOS/Linux:

```sh
.venv/bin/python -m flask --app backend.app process-documents
```

The API and worker must use identical `DATABASE_URL` and
`DOCUMENT_STORAGE_DIR` settings. Run `prepare-db` before starting either
service. The worker checks schema compatibility and refuses incompatible or
unavailable storage; it does not create or upgrade tables while processing.
`--once` attempts one available document and exits.

Worker diagnostics record the document ID, processing stage, outcome,
exception class, duration and attempt count where available. Resume text,
private storage paths and lease tokens are excluded. The worker command
prints INFO diagnostics to its terminal; it does not automatically create
log files.

The BE-6 process-restart test generates `process-restart.json` inside its
pytest temporary directory. Normal API or Worker startup does not generate
this file. Use `--basetemp` to keep test artifacts outside the repository.

## Supported extraction rules

Extraction reads PDF text layers and Word paragraphs/tables. It attempts all six
sections under English headings (case insensitive) and common Chinese headings, accepting headings on their
own line, `Heading: value`, and headings in a Word table's first cell.
Bullets, comma/semicolon lists and tab/pipe separated rows are supported.

| Section | Recognised source structure |
| --- | --- |
| Education / Academic qualifications / Qualifications | Institution and degree on separate lines or `Institution | Qualification | Discipline | 2022-2025`; labelled Institution/University, Qualification/Degree, Discipline/Major, Start year and End year |
| Courses / Coursework / Relevant coursework / Academic transcript / Transcript | Course code and name, e.g. `COMP1511 - Programming Fundamentals`; transcript rows with code, name and optional further columns; labelled Name/Course name, Code/Course code, Description |
| Research experience | `Title | Organisation | Description`, or labelled Title, Organisation/Organization, Description |
| Skills / Technical skills / Programming skills | Free-text titles/evidence from lists, descriptions or labelled blocks; no skill vocabulary lookup; explicit negative wording and source text are preserved |
| Research interests / Interests | Controlled INTEREST label mentions, source-grounded free text and short personal-label proposals |
| Research outputs / Publications / Projects / Research projects | `PUBLICATION | Title | https://...`, `PROJECT | Title`, or labelled Title, Type, URL, Description |

Academic Statements also support programme/plan/term metadata, repeated page
headers and course-result tables without `Education` or `Courses` section titles.
Course codes are normalised, result columns stay in descriptions, and repeated
attempts are retained together. Degree/completion details are not invented and
subjects do not imply skill or research claims. See the
[Academic Statement rules and existing-result recovery](us11-resume-extraction.md#academic-statements-and-transcripts).

Separate labelled records with a blank line or repeat their first key.
Delimited rows and course-code lines are separate records. Explicit year ranges
are parsed; unsupported dates, reversed ranges, invalid URLs and records that do
not fit the API schema are left for manual entry. Missing optional details stay
empty/null and are marked uncertain. An unspecified output type is suggested as
OTHER with an explicit warning. No institution, degree, skill or research fact
is inferred from incidental mentions.

Suggestions use the existing Extraction schema: `documentId`,
`suggestedSections`, `uncertainFields`, `warnings`, `reviewRequired: true`.
Skills retain their source line in `evidenceText`; courses and research records
retain source text in `description` when there is no explicit description.
The owner can consult the original file. Reviewed section provenance stores
`USER_REVIEWED_DOCUMENT` and that document's ID.

US-11 extends this result with `researchInterestText`, `customInterestTags` and
the unified owner-only `resumeDescription`. Text remains available without a
vocabulary match. Proposed personal labels create no rows until accepted in a
reviewed save. See [fields, partial imports, privacy and upgrades](us11-resume-extraction.md).

Unknown items remain visible in uncertainty reasons, even when other items in
the same section were recognised (e.g. Python alongside unsupported COBOL).
Each section is limited to 100 suggestions; omitted items and shortened skill
evidence are flagged. Unrecognised sections receive NOT_RECOGNISED; partially
recognised sections receive UNKNOWN. This is conservative rule-based extraction,
not OCR or a general resume parser. Scanned PDFs, arbitrary layouts, unsupported
headings and vocabulary may need manual entry.

## Recovery and failure

QUEUED becomes PROCESSING under a persistent lease with a unique attempt token.
The default `DOCUMENT_PROCESSING_TIMEOUT=300` is measured in seconds.
After expiry, another worker (including a restarted worker) can claim the job.
An expired or superseded worker cannot save a success or failure.
Legacy PROCESSING rows without leases are recovered after the same timeout.
`DOCUMENT_PROCESSING_MAX_ATTEMPTS=3` limits attempts across worker restarts.
Both settings must be positive integers.

After repeated timeouts, or an unreadable/corrupt file, the document becomes
FAILED with advice to upload another file or fill in the profile manually.
Manual editing remains available. A live parser that exceeds the deadline loses
its claim; recovery happens when a worker next polls. The lease does not forcibly
terminate a hung parser; restart its worker or run another worker to recover it.

## Verification

```sh
.venv/bin/python -m pytest backend/tests --require-frontend
.venv/bin/python -m pytest backend/tests/test_docker_stack.py --run-docker
```

Use `.\.venv\Scripts\python.exe` on Windows. The first command includes real
PDF/DOCX extraction and import, Word tables, partial/unknown results, bounded
recovery, simultaneous claims, stale-result fencing, privacy/validation and a
React workflow with a separate worker CLI process. CI has a dedicated integration
job with Node, frontend dependencies and Python; missing dependencies fail that
job instead of silently skipping it.

The optional Docker test uses a unique project/volume and verifies automatic
worker processing through Nginx, original-file download and persistence across
container recreation. It removes only its own test resources.

## Sprint 3 BE-6 verification

Verification date: 2026-11-17 (Australia/Sydney).

The BE-6 working-tree changes were tested against baseline commit
`81616dd0220ea4ac26b08b862a865614986ef3c0`, before committing.

### Environment and results

| Item | Recorded result |
| --- | --- |
| Python | 3.13.17 |
| Database | File-backed SQLite 3.50.4 |
| Flask / SQLAlchemy / pytest | 3.1.2 / 2.0.44 / 8.4.2 |
| Node.js | 24.20.0 |
| Existing and new Worker tests | 32 passed in 42.91 seconds |
| Full backend regression | 1061 passed, 22 skipped, 0 failed in 653.03 seconds |
| Required frontend integration | Enabled with `--require-frontend`; passed |
| Required application-model checks | Enabled with `--require-application-model`; passed |

The 22 skipped cases comprise 8 Docker/deployment checks, 13 MySQL and
legacy-upgrade checks, and 1 optional historical US-13 model experiment.
The current application-model checks were required and passed.
MySQL and Docker behaviour was not verified by this local run.

### Coverage

The 21 new BE-6 cases complement the 11 existing Worker tests.

| Scenario | New cases |
| --- | ---: |
| Independent processes competing for queued or expired work | 2 |
| Actual process termination, natural lease expiry and recovery | 1 |
| Late success/failure against a newer lease or READY result | 4 |
| Maximum attempts across independent process exits | 1 |
| Invalid schema or mismatched document identity and recovery | 2 |
| Processing failures, safe diagnostics and manual editing | 6 |
| Claim/result/failure commit rollback | 3 |
| Upload registration failure and saved-file cleanup | 2 |

The tests invoke the real Worker command callback in independent Python
processes. Parser-start gates control timing; successful recovery uses the
real parser, extraction builder, schema validation and persistence code.

The HTTP integration tests also track the actual Worker interpreter PID,
including Windows environments where the launcher has a different PID.

### Actual process-restart record

The following values were read from the restart record generated during
the full regression run.

| Observation | Recorded value |
| --- | --- |
| Document ID | `doc_ccf26b03f24b4e2b9e3a7424dca5fd7b` |
| Started at UTC | `2026-11-17T04:52:38.280187+00:00` |
| Finished at UTC | `2026-11-17T04:52:43.494239+00:00` |
| Interrupted Worker PID / exit code | `13776` / `15` |
| Recovery Worker PID / exit code | `15752` / `0` |
| Test lease duration | 3 seconds; natural expiry without timestamp injection |
| Attempt count | 1 -> 2 |
| Lease token rotated | Yes |
| Final document state | READY |
| Valid extraction rows | Exactly 1 |
| Manual profile save while parsing was blocked | Passed |
| Manually saved profile preserved after recovery | Passed |

The three-second lease is confined to the test. Production defaults remain
300 seconds and three maximum attempts. Raw lease tokens, credentials,
private file paths and resume contents are excluded from this record.

### Reproduction

Run from the repository root in the configured Python environment.
Future runs can keep all BE-6 artifacts under one project-external directory:

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTEST_ADDOPTS = (($env:PYTEST_ADDOPTS + ' -p no:cacheprovider').Trim())

$be6Evidence = Join-Path (Resolve-Path '..\..').Path 'reports\be6'
New-Item -ItemType Directory -Path $be6Evidence -Force | Out-Null

$env:PYTEST_DEBUG_TEMPROOT = Join-Path $be6Evidence 'pytest-temp'
New-Item -ItemType Directory -Path $env:PYTEST_DEBUG_TEMPROOT -Force | Out-Null

$env:BE4_ROUNDS = '10'
$env:BE4_EVIDENCE = Join-Path $be6Evidence 'be4.json'

python -B -m pytest backend/tests/test_us09_worker.py backend/tests/test_sprint3_be6.py -q -ra --basetemp="$be6Evidence\tmp-worker"

python -B -m pytest backend/tests -q -ra --require-frontend --require-application-model --basetemp="$be6Evidence\tmp-full"
```

The temporary directories contain reproducible test data and are not
submission files. Normal API/Worker startup does not generate restart records.
The fixed temporary directories should be used for sequential runs.

### Acceptance scope

Local SQLite, Worker recovery, frontend integration and current
application-model regression checks passed. Public API schemas, database
tables and lease rules remain unchanged. MySQL CI results must be checked
before final acceptance.
