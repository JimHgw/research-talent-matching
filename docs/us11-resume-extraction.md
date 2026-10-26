# US-11: resume tags, free text and a unified description

The user clarified this implementation's scope on 23 October 2026: complete the
backend resume extraction logic, returning tags and description free text, with
an additional unified description of the whole resume. This guide records that
scope and the implemented workflow.

## Returned content

The existing PDF/DOCX upload and background worker produce an owner-only READY
extraction containing these values in `suggestedSections`:

| Field | Meaning |
|---|---|
| `skills` | Free-text `title` and supporting `evidenceText`, with a record `id`; no vocabulary tag or claim selector |
| `researchInterests` | Recognised shared INTEREST IDs, including exact label mentions inside paragraphs |
| `researchInterestText` | Reviewable source description of research interests, up to 5,000 characters, retained even with no matching vocabulary tag |
| `customInterestTags` | Short explicit interest labels outside the shared vocabulary, proposed as `{label}` for acceptance/editing/rejection |
| `resumeDescription` | Unified readable text of the whole resume, including unrecognised sections, up to 20,000 characters; owner-only |
| `education`, `courses`, `researchExperience`, `researchOutputs` | Existing structured suggestions; course/experience/output descriptions retain their source text |

For example, an interest section containing `Machine learning; Climate-resilient
urban systems` produces:

```json
{
  "researchInterests": ["interest_ml"],
  "researchInterestText": "Machine learning; Climate-resilient urban systems",
  "customInterestTags": [{"label": "Climate-resilient urban systems"}]
}
```

`resumeDescription` separately contains the whole document's readable text,
in source order, with blank lines removed and within-line whitespace collapsed.
It is extracted source text, with no invented achievements, inferred credentials
or external-model generation. Headings and content outside recognised sections
remain available. Longer text is shortened with an explicit uncertainty warning;
the owner can consult the private original file.

The parser recognises the documented English headings and common Chinese equivalents
of Education, Research Experience, Skills, Research Interests and Research Outputs,
including full-width colons.
Interest tags use whole-word label mentions. Skill titles now preserve the source
wording without a vocabulary lookup; `Pythonic` and `SQLAlchemy` remain those
titles, and do not establish Python/SQL matches. Explicit negative skill wording
is retained; learning intentions and conflicting statements require review. Skills
are drawn from the skills section, rather than inferred from incidental mentions
elsewhere. Unmatched information remains in free text and uncertainty warnings.
Short list labels can become personal-interest proposals; long sentences remain
descriptive text.

See [free-text skill fields, legacy compatibility and matching](free-text-skills.md)
for the later change replacing the original skill-tag representation.

### Academic Statements and transcripts

Academic records are recognised by their content, even when uploaded with the CV
document type. `Academic Statement`, academic-transcript headings and course-table
headers activate academic parsing; a CV does not need to contain those headings
for the existing section parser to work.

- Repeated university headers, `Academic Career`, `Program`, `Plan` and term lines
  produce deduplicated education suggestions. A career header without an actual
  programme creates no education entry. Student names/IDs and print dates are not
  used as education or course fields.
- A programme title is retained as written when the actual degree title is absent.
  The earliest recorded term supplies a reviewable `startYear`; it may differ from
  enrolment. `endYear` stays null because the last recorded term does not establish
  graduation. The review warning explains these limits.
- Rows such as `COMP 1511 Programming Fundamentals 6.00 6.00 72 CR` become course
  code `COMP1511` and name `Programming Fundamentals`. Decimal credit columns,
  marks and grades stay in the source description alongside the term. Wrapped
  titles/result columns and current subjects with only attempted credit are
  supported. Course names keep digits, commas and other title punctuation.
- Repeated course codes create one suggestion with all recorded attempts in its
  description, including failed attempts and subsequent results. No arbitrary
  attempt is silently selected as the final grade.
- Subjects do not establish programming proficiency, research interests, research
  experience or research outputs. Those sections still require explicit evidence.

Existing READY extractions are stored results. After updating/rebuilding the API
and worker, upload the statement again to create new suggestions. **Reload
suggestions** reloads the stored result; it does not reprocess the original file.
Previously saved profiles are not changed by this parser update.

## Existing API workflow

All paths are under `/api/v1`; this change adds no endpoint.

1. POST `/me/documents`: upload a private PDF/DOCX. The document worker processes
   the actual file and stores suggestions. Upload/extraction creates no personal
   tags and does not modify or confirm the profile.
2. GET `/me/documents/{id}/extraction`: read the owned result, source descriptions,
   tag proposals and uncertainty warnings.
3. The existing review form exposes shared tags, interest text, personal labels
   and the unified resume description. The owner can edit or deselect each
   component. Suggestions are never silently accepted by the worker.
4. POST `/me/documents/{id}/apply`: submit the selected reviewed components and
   `expectedProfileRevision`. The transaction validates ownership, READY state,
   revision, tag kinds, labels and limits before committing all changes together.
5. GET `/me/profile`: reload canonical saved text and tags. Personal labels now
   contain server-generated IDs. Each submitted component records its own
   USER_REVIEWED_DOCUMENT provenance; omitted components retain their values and
   provenance.
6. POST `/me/profile/confirmation`: explicitly confirm the current revision.
   Imports always leave the profile UNCONFIRMED. Manual changes invalidate prior
   confirmation; a true manual no-op preserves the revision and confirmation.

Example selected-component import:

```json
{
  "expectedProfileRevision": 3,
  "sections": {
    "researchInterestText": "I want to investigate ecological forecasting.",
    "customInterestTags": [{"label": "Ecological forecasting"}],
    "resumeDescription": "Reviewed resume description containing the original education, skills and research experience."
  }
}
```

Omitting a component preserves it. `""` clears a text field and `[]` clears a
selected tag collection. The same new fields are optional in the existing full
profile PUT, so older clients saving the original eight fields preserve text and
personal selections. The OpenAPI schemas, examples and existing review/profile
controls have been extended together.

Personal labels use NFKC, collapsed whitespace and case-insensitive exact
deduplication. Labels have 1–100 visible characters; shared and personal interest
selections have a combined maximum of 100. Resolve exact shared INTEREST labels
first, then the current owner's catalogue. A shared match adds its canonical
shared ID and creates no private duplicate. Unselected owner-local records remain
available for reuse. IDs from another owner are rejected. No private label enters
GET `/tags`. Stale/invalid/concurrent writes cannot leave orphan tags or partial
profile updates.

## Privacy and matching boundary

The existing `researchInterests` privacy control covers shared IDs, interest text
and selected personal labels together. Team list/detail queries require a current
confirmed revision and discovery consent, and select only permitted interest
content. Hiding the group removes all three fields and their influence.

The privacy page lists the eight consent groups accepted by `ProfileField` and
`PrivacyWrite`, using its own whitelist rather than all profile display labels.
Interest descriptions and personal labels have no independent checkbox; the
page explains that both follow Research interests. Frontend regression tests
compare all rendered choices and the saved request with the OpenAPI enum. The
real HTTP workflow saves every offered choice against the actual API with the
new profile components populated.

`resumeDescription` is always owner-only because whole-resume text may contain
contact details or information from hidden sections. It has no public visibility
control and is excluded from team schemas, database projections and matching
inputs. Original documents and component provenance remain owner-only.

The structured matcher uses shared interest IDs and exact normalised skill-title
comparisons with existing opportunity criteria. Interest free text and personal
labels do not fabricate a shared-tag match; missing supported evidence
remains UNKNOWN. The separate US-13 semantic matcher is outside this extraction
implementation.

## Upgrade and run

Dependencies are unchanged. Complete the normal [backend setup](../backend/README.md)
if it has not already been run. Fresh databases use the existing `init-db` command.
For an existing installation, stop API/worker writes, retain the same database
configuration, and run from the repository root on Windows:

```powershell
.\.venv\Scripts\python.exe -m flask --app backend.app init-db
.\.venv\Scripts\python.exe -m flask --app backend.app upgrade-resume-text
```

On macOS/Linux, use `.venv/bin/python`. Then restart the API and document worker
using the existing README commands. For Docker, rebuild the application images
and use the existing startup workflow; its entrypoint creates missing tables and
widens the legacy resume-text column before starting the API/worker.

The upgrade is additive: `profile_text_details` stores the text components;
`personal_interest_tags` stores owner-local labels; `profile_personal_interests`
stores ordered selections with a same-owner foreign key;
`profile_component_origins` stores the new components' provenance. Existing tables,
IDs, profile revisions, confirmations, credentials and document results remain
unchanged. The original component-table additions require no ALTER; the later
MySQL capacity fix explicitly widens `resume_description` from TEXT to MEDIUMTEXT
so all 20,000 four-byte Unicode characters fit. No reset is required. Existing profiles default
to empty new fields, and old READY results can still be reviewed/imported.
The later free-text skill update adds `profile_skill_details` as described in
the [skill compatibility guide](free-text-skills.md).

## Verification

Focused functional tests:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_us11.py -q
.\.venv\Scripts\python.exe -m pytest backend/tests/test_us11_academic.py -q
```

The tests cover actual PDF/DOCX upload/worker/import/reload, descriptions without
shared tags, unified unstructured text, truncation warnings, tag boundaries and
negative claims, independent text/tag inputs, partial acceptance/clearing,
provenance preservation, label normalisation/renaming/reuse, ownership, stale and
concurrent writes, combined limits and additive upgrades of an existing SQLite
schema. Existing real HTTP frontend tests also exercise editing/importing the
new fields against the backend and real document worker.

Use the normal full regression command with `--require-frontend`. Real MySQL and
container tests remain available through `--run-mysql` and `--run-docker`; only
report those environments as verified when actually executed.

Initial implementation verification on 23 October 2026 (Windows, Python 3.12.14):

- Full backend regression with `--require-frontend`: **450 passed, 6 skipped**,
  including the real HTTP frontend and actual document-worker workflows.
- US-11 focused functional tests: **24 passed**.
- Frontend tests, including production-build checks: **189 passed**; formatting
  checks passed. All **42** indexed API examples passed schema validation.
- The six skips are five optional real-MySQL cases and the real-container case.
  MySQL table DDL compilation and the actual additive SQLite upgrade were checked;
  a real MySQL/container deployment was not run because Docker was unavailable.

Text-layer PDFs and DOCX paragraphs/tables are supported. Scanned PDFs require
OCR elsewhere or manual entry. Arbitrary layouts and unsupported vocabulary can
still require correction; the unified description preserves readable source text
even when structured recognition fails.

The Academic Statement regression cases use synthetic student data and cover
repeated page headers, programme/career deduplication, decimal result columns,
wrapped rows, repeated attempts, current subjects, limits, and real PDF/DOCX
upload/review/import for both CV and TRANSCRIPT document types. A read-only check
against the user-reported statement's extracted source yielded one education
record and 25 distinct courses, preserving both attempts of a repeated course.

Academic Statement fix verification on 23 October 2026:

- Final full regression with `--require-frontend`: **465 passed, 6 skipped**,
  including all 15 new Academic Statement cases and real HTTP frontend workflows.
- The new Docker image directly read the user-reported original PDF in a read-only
  check: one education entry, 25 distinct courses, both repeated attempts retained,
  and no result columns in course names. Stored suggestions were not overwritten.
- Rebuilt the application image and recreated only `document-worker`. Its startup
  completed successfully; the existing API/frontend remained healthy and the
  running worker contains the new parser. New uploads use the updated rules.
- The six optional isolated Docker/MySQL tests were still skipped. The live
  read-only PDF check and worker update do not replace those isolated tests.

MR !40 review regression verification on 23 October 2026:

- Privacy choices now match the eight `ProfileField` values. Frontend tests save
  every rendered choice, and real HTTP tests do so with all new profile components
  populated. Interest text/personal labels remain one consent group; the resume
  remains owner-only.
- Skill evidence negation is target-specific. English/Chinese cases using both
  legacy and free-text skills keep confirmed Python MATCHED with a score of 100
  when the source denies R instead. Actual Python denials still produce a gap.
- Resume storage uses MySQL MEDIUMTEXT. Real MySQL tests save/reload 17,000 and
  20,000 four-byte characters through manual saves and reviewed imports, reject
  20,001 characters atomically, and upgrade a legacy TEXT column without changing
  its saved profile or interest description.
- Full backend/real-HTTP regression: **501 passed, 6 skipped**. A separate isolated
  MySQL run: **57 passed**. Frontend tests/builds: **192 passed**.
- The existing deployment was updated after backing up its affected text rows in
  the private data volume. Eight profile/document/provenance tables had identical
  row counts and content checksums before and after the capacity upgrade. Public
  page, updated bundle and session API checks returned HTTP 200. The isolated
  test container and its temporary database were removed.
