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
| `skills` | Recognised shared SKILL IDs, HAS/DOES_NOT_HAVE claims and the original supporting line in `evidenceText` |
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

The parser recognises the documented English headings and common Chinese headings
such as 教育背景, 科研经历, 技能, 研究兴趣 and 研究成果, including full-width colons.
Known tags use whole-word label mentions, so `Pythonic` and `SQLAlchemy` do not
become Python/SQL claims. Explicit negative skill statements are preserved as
DOES_NOT_HAVE; learning intentions and conflicting claims require review. Skills
are drawn from the skills section, rather than inferred from incidental mentions
elsewhere. Unmatched information remains in free text and uncertainty warnings.
Short list labels can become personal-interest proposals; long sentences remain
descriptive text.

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

`resumeDescription` is always owner-only because whole-resume text may contain
contact details or information from hidden sections. It has no public visibility
control and is excluded from team schemas, database projections and matching
inputs. Original documents and component provenance remain owner-only.

The structured matcher continues to use confirmed shared IDs. Free text and
personal labels do not fabricate a shared-tag match; missing supported evidence
remains UNKNOWN. The separate US-13 semantic matcher is outside this extraction
implementation.

## Upgrade and run

Dependencies are unchanged. Complete the normal [backend setup](../backend/README.md)
if it has not already been run. Fresh databases use the existing `init-db` command.
For an existing installation, stop API/worker writes, retain the same database
configuration, and run from the repository root on Windows:

```powershell
.\.venv\Scripts\python.exe -m flask --app backend.app init-db
```

On macOS/Linux, use `.venv/bin/python`. Then restart the API and document worker
using the existing README commands. For Docker, rebuild the application images
and use the existing startup workflow; its entrypoint creates missing tables.

The upgrade is additive: `profile_text_details` stores the text components;
`personal_interest_tags` stores owner-local labels; `profile_personal_interests`
stores ordered selections with a same-owner foreign key;
`profile_component_origins` stores the new components' provenance. Existing tables,
IDs, profile revisions, confirmations, credentials and document results remain
unchanged. No ALTER or destructive reset is required. Existing profiles default
to empty new fields, and old READY results can still be reviewed/imported.

## Verification

Focused functional tests:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_us11.py -q
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

Recorded verification on 23 October 2026 (Windows, Python 3.12.14):

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
