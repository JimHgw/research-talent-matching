# Task 53: talent filters and matching evidence

This task reuses `Recommendations`, `TalentPage` and `MatchDetails` from Sprint 1.
The backend still calculates the scores and decides which profiles and fields
the team can see.

## Changes

- Show education, courses, research experience and outputs as separate labelled
  records. Keep the existing short format for skills.
- Show the record that supports each requirement. The frontend uses `field`
  and `recordId` to find it in the shared `talent.fields` response. If it is
  missing, it does not use a different record to fill the gap.
- Only display the supported profile fields. Do not show original document
  links, private document details or the owner's full resume description.
- Keep the backend's scores, reasons and Matched/Partial/Gap/Unknown statuses.
  Add translations for the new academic explanations. Names and profile text
  stay as the user wrote them.
- Hide the evidence dialog while the talent list is reloading or unavailable,
  so the page does not keep showing old evidence during a refresh.

## Filters and backend work

The page uses the existing US-14 filters: search text (`q`), a skill keyword
(`skill`) and one Go8 university (`university`). The backend combines them.
Research interests can be searched with `q` when the talent has shared them.

BE-54 was merged at `b122a71`, then reverted on main at `103de0f`.
This branch includes that revert. Academic evidence therefore needs the backend
work to be restored before it can be used again. The frontend is ready for
`{field, recordId, valueSummary}` and the reason codes
`ACADEMIC_CRITERIA_SUPPORTED` and `ACADEMIC_CRITERIA_PARTIAL`.

The display tests use sample responses. `tests/us53-live.mjs` also checks the
React pages against the real Python API and a temporary SQLite database.
It checks the education, experience and publication records, hidden fields,
withdrawn sharing, unconfirmed edits and an expired opportunity.

The US-13 evaluation chose to keep semantic matching out of the application.
This frontend keeps the current matching method. A high similarity score on
its own is not proof of a qualification, experience or publication.

## Tests

Run these commands in `frontend`:

```text
pnpm test:53
pnpm test
pnpm build
pnpm format:check
```

From the project root, run the real HTTP check with:

```text
.venv\Scripts\python.exe -m pytest backend/tests/test_frontend_integration.py -k 53 --require-frontend -q
```

This check passed on 2026-10-26 before the backend revert. It now reports a skip
when the checked-in API contract lacks the academic requirement types; it is not
a passing academic integration result. Once those types are restored, the test
runs normally and API or UI failures still fail it. It uses jsdom, real HTTP,
cookies and CSRF. A visual browser check and the MySQL upgrade are separate checks.

The new tests check the supporting records, missing references, hidden fields,
filter refresh and translations. Task 20 and US-14 tests already cover matching
statuses, withdrawn sharing consent, filters and pagination. Task 51 can reuse
these cases.
