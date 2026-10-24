# US-14: search and combined filters

Implemented through existing `/api/v1` operations; no HTTP endpoint was added.
Opportunity browsing, recommendations and team talent discovery have search,
apply and clear controls. Applying/clearing filters resets to page 1. Talent
discovery retains filters on refresh and discards open stale evidence.

## API behaviour

| Existing GET route | Supported search parameters |
| --- | --- |
| `/opportunities` | `q`, `university`, `disciplineGroup`, `discipline`, `researchArea`, `opportunityType`, `deadlineFrom`, `deadlineTo`, existing `scope` and pagination |
| `/me/recommendations` | Same opportunity filters and pagination, without `scope`; requires the owner's current confirmed profile |
| `/opportunities/{id}/talent-matches` | `q`, `skillTagId`, `interestTagId` and pagination; requires an active published opportunity owned by the current team |

Different filters combine with **AND**. Repeated opportunity attribute values and
talent tag IDs combine with **OR** within that parameter. Examples:

```text
/api/v1/opportunities?university=UNSW&university=USYD&disciplineGroup=STEM&opportunityType=PHD
/api/v1/me/recommendations?q=imaging&deadlineFrom=2099-01-01T00%3A00%3A00Z
/api/v1/opportunities/opp_example/talent-matches?skillTagId=skill_python&interestTagId=interest_ml
```

`q` is one literal substring, up to 200 characters. It searches title, university,
discipline, research area and description for opportunities. Text comparisons use
Unicode NFKC, collapsed whitespace and casefold on both MySQL and SQLite;
SQL wildcard characters are literal. University, discipline and research-area
filters use normalised exact values. Enum codes remain exact on input:
`STEM`/`BUSINESS` and `PHD`/`MASTERS`/`RESEARCH_ASSISTANT`/`POSTDOC`/`OTHER`.

Dates require RFC3339 with an explicit offset and at most six fractional digits.
They are stored/returned in UTC. Deadline bounds form `[deadlineFrom, deadlineTo)`;
a bounded query excludes opportunities without deadlines. Equal/reversed ranges,
blank values, duplicate single-valued parameters, invalid enum/tag values and
unknown parameters return `422 VALIDATION_ERROR` with the affected field. Existing
strict pagination remains in effect. No matches return HTTP 200, `items: []` and
the correct filtered `total`. Stable ranking and global ranks are calculated from
the permitted filtered candidate pool before pagination.

## Talent privacy

The server checks current consent, active account and current confirmed revision,
then constructs the permitted projection before text/tag filtering or scoring.
`q` searches only visible structured content, including visible confirmed interest
text and personal labels. It does not search IDs, original documents, extraction
drafts, private provenance or the owner's unified resume description. Shared
interest IDs are searched by their labels. Personal tags are searchable with `q`;
they never become global shared-tag filters.

`skillTagId` requires an exact shared-vocabulary skill supported by a visible
positive claim, using the existing free-text skill adapter. Explicit negatives
override positives; missing/hidden/aspirational evidence cannot pass. Hidden-field
edits cannot change totals, ranks, scores or evidence. Revocation removes the
talent immediately and direct old detail requests return 404. An eligible profile
with no visible fields can appear anonymously in an unfiltered list but cannot
pass a filter using its hidden fields.

## Type and deadline dependencies

Existing opportunity content accepts optional nullable `opportunityType` and
`deadlineAt`. Omission preserves stored values on update; explicit `null` clears
them. Unset values are omitted on reads for legacy content compatibility.
Live responses add `availabilityStatus`: `DRAFT`, `ACTIVE` or `EXPIRED`;
legacy fixtures may omit this additive response property.

Discovery/recommendations exclude drafts and opportunities at/past their deadline;
the exact deadline instant is expired. `scope=mine` retains all owned management
records with availability labels. Published expired details remain readable,
while matching returns `409 OPPORTUNITY_EXPIRED`. Records are retained and no
scheduler is required.

An edit after expiry retains an internal marker, even when the new deadline is in
the future or cleared. Explicit `reopen: true` in the existing opportunity PUT
atomically validates ownership, revision, requirements and a future/null deadline,
applies content, and reopens. Revision increments once; an unchanged active
reopening is a no-op. Draft reopening returns `409 OPPORTUNITY_NOT_PUBLISHED`.
Republishing cannot reopen an expired record. The editor offers a separate
deliberate reopening control. Source URLs (US-19) are outside this delivery.

## Upgrade and rollback

Back up using the existing [MySQL migration procedure](mysql-migration.md).
Stop old API/worker writers, preserve the database configuration, then run:

```text
python -m flask --app backend.app init-db
python -m flask --app backend.app upgrade-opportunity-search
```

Deploy API and frontend together. The Docker entrypoint runs both commands.
The explicit upgrade adds only nullable `opportunity_type`, `deadline_at` and
`expired_at` columns to the existing `opportunities` table. Existing records
receive NULL, so previously published opportunities stay active. It is repeatable,
tolerates partial upgrades, and serializes concurrent API/worker migrations with
a MySQL advisory lock (SQLite uses a write transaction). MySQL retains microseconds
with DATETIME(6). `init-db` alone does not alter existing tables.

When migrating a pre-US-14 SQLite database to MySQL, first run this upgrade
against a backed-up working copy of the SQLite source (select it with
`DATABASE_URL`). Pass that upgraded copy to `migrate-sqlite --source`; the existing
copy tool correctly rejects a source whose column set differs from the current
schema. Retain the original backup unchanged.

For rollback, stop the updated services and restore the verified pre-upgrade
backup with the old application version. Do not drop columns/reset database
volumes as a routine rollback; that would lose newly saved metadata.

## Verification

```text
.venv\Scripts\python.exe -m pytest backend/tests/test_us14.py -q
.venv\Scripts\python.exe -m pytest backend/tests/test_frontend_integration.py -k 14 --require-frontend -q
```

The API suite covers composition, Unicode comparisons, literal input, date
boundaries, validation, pagination, privacy invariance, consent/confirmation,
expiry, reopening and upgrade preservation. The second command runs React
against a real temporary HTTP/SQLite backend with independent account sessions.
Frontend DOM/API checks are in `frontend/tests/us14-search.test.js`; these use
synthetic responses and are separate from the real HTTP workflow. The existing
frontend runner also checks the production build.

Text filtering currently normalises authorised candidates in application memory
for identical Unicode behaviour across engines. This suits the current project
dataset; it is not a large-corpus search index. Local MySQL/Docker runtime
validation requires a running Docker engine; SQLite results do not certify a
live MySQL deployment.

Verified on 2026-10-24: all 19 US-14 API cases, the US-14 real HTTP workflow,
229 frontend checks (including production builds), formatting and related
opportunity/matching/privacy regression checks passed. Docker was unavailable,
so the live MySQL upgrade/deployment remains unverified locally.
