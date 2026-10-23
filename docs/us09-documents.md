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

For native development, after the usual setup, `init-db` and `seed-tags`,
keep a third terminal open at the repository root:

```powershell
.\.venv\Scripts\python.exe -m flask --app backend.app process-documents
```

On macOS/Linux:

```sh
.venv/bin/python -m flask --app backend.app process-documents
```

The API and worker must use identical `DATABASE_URL` and
`DOCUMENT_STORAGE_DIR` settings. The worker command also creates any missing
tables, including the new lease table, without replacing existing document or
profile data. `--once` attempts one available document and exits.

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
| Skills / Technical skills / Programming skills | Controlled SKILL label mentions in lists or descriptive paragraphs; explicit negative claims and original supporting text are preserved |
| Research interests / Interests | Controlled INTEREST label mentions, source-grounded free text and short personal-label proposals |
| Research outputs / Publications / Projects / Research projects | `PUBLICATION | Title | https://...`, `PROJECT | Title`, or labelled Title, Type, URL, Description |

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
