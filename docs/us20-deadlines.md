# US-20: deadlines and automatic expiry

## API and time rule

Use the existing opportunity POST/PUT routes with optional `content.deadlineAt`.
Supply RFC3339 with an explicit offset and at most six fractional digits, for
example `2027-01-01T17:00:00+11:00`. The application converts the instant to UTC,
stores MySQL `DATETIME(6)`, and returns a UTC string ending in `Z`. The converted
UTC year must be within MySQL's supported range of 1000-9999. Invalid dates,
times, types, missing offsets, excessive precision and conversion overflow return
422 `VALIDATION_ERROR` with an actionable `content.deadlineAt` field message.
Omission preserves the saved deadline on update; explicit null clears it. No
deadline is required, and unset deadlines are omitted from read responses.

A published opportunity is active strictly before its deadline and expired at or
after it. Without a deadline it stays active unless previously expired and not
explicitly reopened. Availability and active queries use the same UTC rule.
Each request applies that rule; no scheduled database mutation or deletion is
needed. Existing pages obtain the current state when refreshed or reopened.

Active browsing, search and talent recommendations exclude expired records.
Talent match details and both team talent match routes return
409 `OPPORTUNITY_EXPIRED`. Direct published opportunity details remain readable
with `availabilityStatus: EXPIRED`; owners retain the record in `scope=mine`.
`status` remains `PUBLISHED`, distinguishing publication from current availability.
The existing UI displays the deadline with the viewer's time-zone label and uses
the availability state for expired badges and matching controls.

## Owner edits and reopening

The existing role, ownership, CSRF and expected-revision checks protect edits.
Changing or removing an expired deadline retains expiry. Explicit reopening uses
the existing PUT with the whole content and `reopen: true`:

```json
{
  "expectedRevision": 4,
  "content": {
    "title": "Research assistant",
    "university": "UNSW",
    "disciplineGroup": "STEM",
    "discipline": "Computer Science",
    "researchArea": "Data analysis",
    "description": "Research assistant opportunity.",
    "requirements": [
      {"id": "req_python", "label": "Python", "kind": "SKILL",
       "importance": "REQUIRED", "tagIds": ["skill_python"]}
    ],
    "deadlineAt": "2027-01-01T17:00:00+11:00"
  },
  "reopen": true
}
```

Use the opportunity's current revision and complete content when editing.
Reopening requires a published opportunity, valid content and a
future deadline or no deadline. Expired or exactly-current deadlines are rejected
atomically. A draft cannot be reopened. Republishing alone does not reopen an
expired record. Successful reopening increments the revision once; an unchanged
active reopening is a no-op. Stale revisions fail with 409 without overwriting data.

## Existing databases

Deadline storage and its idempotent upgrade already exist from US-14. Deploy with
the existing `upgrade-opportunity-search` command, which adds nullable
`deadline_at` and `expired_at` to legacy tables while preserving all records.
The Docker entrypoint runs it automatically. An already upgraded installation
needs no additional columns for US-20.

For the running Docker backend, from the repository root:

```sh
docker compose exec -T backend python -m flask --app backend.app upgrade-opportunity-search
```

Native Python commands require the database to be reachable from the host;
Docker-internal MySQL is reached from the backend container. Keep the existing
business database and volumes. US-20 retains expired records permanently until a
separate deletion rule is confirmed.

## Regression checks

```sh
.venv/bin/python -m pytest backend/tests/test_us20.py backend/tests/test_us14.py backend/tests/test_us19.py backend/tests/test_us02.py backend/tests/test_us04.py backend/tests/test_us05.py backend/tests/test_us08.py backend/tests/test_us18.py backend/tests/test_mysql.py -q
```

For MySQL, configure `MYSQL_TEST_DATABASE_URL` to an isolated disposable database
whose name ends in `_test`, then add `--run-mysql`. Test fixtures clear that
database; never configure a business database for tests.

US-20 API tests cover the microsecond before, exactly at and after the deadline;
equivalent UTC/offset instants; no deadline; exact persisted values and application
restart; saved deadline changes; active browsing/search and both matching
directions; retained direct and owner views; invalid input atomicity; future/null
reopening; invalid reopening; ownership, role, CSRF and stale revision protection;
and expiry after upgrading an old database. The upgrade test runs against SQLite
or MySQL according to `--run-mysql` and checks MySQL microsecond precision.

Verified on 2026-10-27: all 36 US-20 cases passed on SQLite. The regression command
above with `--run-mysql` passed 235 tests on isolated MySQL 8.4.13; one US-18
non-MySQL startup test was intentionally skipped. The disposable container and
its anonymous volumes were removed after the run.
