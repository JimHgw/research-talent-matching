# Free-text skills

Skills in the talent profile and extraction-review form now have exactly two
editable values: **Skill title** and **Supporting evidence**. Both STEM and
Business use the same form. Titles need not exist in the shared vocabulary;
examples include `CRISPR experimental design` and `Financial modelling`.

## API and extraction

Each entry in `content.skills`, reviewed `sections.skills`, extraction suggestions
and permitted team-facing skills uses:

```json
{
  "id": "record_financial_modelling",
  "title": "Financial modelling",
  "evidenceText": "Built a cash-flow forecast and documented the assumptions."
}
```

`id` identifies the profile record, not a vocabulary tag. IDs must be unique within
the section. There are at most 100 entries; titles require 1–350 characters with
visible text; evidence permits 0–2,000 characters. The title is a text input and
evidence is a multiline input. The form has no skill-tag or claim dropdown.

Extraction reads explicit skill-section entries without consulting SKILL tags.
Short lists produce separate entries. `Title: ...` / `Supporting evidence: ...`
blocks and `Skill name: source description` entries preserve their two values.
Descriptive sentences remain free-text titles with source evidence; the parser
does not invent a taxonomy from them. Repeated titles retain combined source
evidence. Limits, conflicting statements and learning intentions require review.
Course records alone still do not imply proficiency.

The existing upload, review, partial import, profile confirmation and privacy
flows remain in place. Saving or importing changed skills requires confirmation
again. An omitted import section preserves skills; `skills: []` clears them.

## Existing data and deployment

Run the normal `init-db` step before starting the updated API/worker, or use the
existing Docker startup workflow. It adds only `profile_skill_details`; no existing
table or profile record is deleted or altered. The new table stores each owner's
ordered skill records, including an explicit empty list after clearing.

Profiles without a new row read their old `profile_skills` entries as skill
titles resolved from the original tag labels, preserving evidence and order.
Explicit negative claims become titles such as `No SQL`, so they cannot silently
become positive claims. This read adapter preserves profile revisions,
confirmation and provenance. A later save stores the new representation; clearing
it never causes the preserved legacy records to reappear.

Old READY extraction results are converted to the new shape when their owner
reads them. Stored extraction JSON and original uploads are preserved. Those
results can be edited and imported without re-uploading. New requests must use
the new skill shape; deploy the API and frontend together.

## Matching and visibility

The existing opportunity requirements continue to use their shared criteria.
Skill records themselves carry no tag reference. Matching resolves a skill title
against a criterion's name using Unicode, whitespace and case normalisation with
exact comparison. `Python` can support the Python criterion; `Pythonic` and
`SQLAlchemy` do not establish Python or SQL proficiency. Unknown free-text titles
remain valid profile entries even when no existing criterion has that name.
This change adds no semantic similarity or new inferred abilities.

Explanations cite the actual skill record ID and supporting text. Explicit
negative statements remain gaps; omitted/unmatched skills remain UNKNOWN. The
skills privacy field governs both title and evidence. Hidden skills are excluded
before reading matching inputs or producing team scores/explanations.

Negation in evidence must govern the particular skill. For example, `No R
experience, but used Python` denies R and does not deny Python. Punctuation and
contrast clauses separate statements; target-specific negative phrases are
supported in English and Chinese. The MR !40 regression cases exercise both
legacy and free-text records through owner/team matching HTTP endpoints.

## Verification

`backend/tests/test_free_text_skills.py` covers both disciplines, arbitrary titles,
actual PDF/DOCX review/import, persistence, legacy-table upgrades and old READY
results, clearing, validation, confirmation, record-ID evidence and privacy.
Real HTTP frontend tests exercise free-text manual entry and document review.
The frontend form test also removes every SKILL vocabulary tag and verifies that
adding, editing, saving, refreshing and clearing a skill still work.

Recorded verification on 23 October 2026:

- Full backend regression, including real HTTP frontend integration: **478 passed,
  6 skipped**. The skips are the optional isolated Docker/MySQL cases.
- New free-text skill tests: **13 passed**.
- Frontend tests, including production builds: **190 passed**; formatting passed.
- All **42** indexed API examples validated against the updated schema.
- Both Docker application images built successfully. An existing deployment must
  update the API, frontend and worker together through its configured startup mode.
