# Sprint 2 test data preparation

## Scope and source status

Dataset **`sprint2-synthetic-v2`** packages existing US-06 synthetic matching
cases and US-05 privacy scenarios into repeatable application state. It contains
10 talent profiles, 7 opportunities (6 published, 1 draft), 2 team accounts and
12 independently labelled matching/access cases. It does not replace US-06.

**Authorised real examples: 0. AC1's real-input requirement remains blocked.**
The checked-in sources do not establish permission to use any real applicant's
CV or any real research opportunity. These synthetic regression cases must not
be described as real examples, client acceptance evidence or measured real-world
matching quality. Obtain authorised talent **and** opportunity source material
through the team's shared QA dataset review before claiming that criterion.

## Layout and provenance

| File | Purpose |
|---|---|
| `backend/tests/data/sprint2/manifest.json` | Version, source status, account roles/purposes, vocabulary and per-example provenance |
| `backend/tests/data/sprint2/talents.json` | Current ProfileContent plus explicit confirmation, revision, consent and visible fields |
| `backend/tests/data/sprint2/opportunities.json` | Current OpportunityContent, stable owner reference, revision and publication state |
| `backend/tests/data/sprint2/expected-results.json` | Independent, static labels and their manual sources |
| `backend/tests/data_preparation.py` | Validates the dataset and builds an isolated application through existing provisioning, tag and HTTP helpers |
| `scripts/prepare-test-data.py` | Command-line entry point, with no shared-database target option |
| `backend/tests/test_sprint2_data_preparation.py` | Preparation, restoration, schema, matching and privacy regression checks |

Each talent/opportunity has a stable `s2_` identifier. Every example's source
record includes type, category, reference, preparation date and steps,
de-identification steps, intended use, original privacy/retention flags and
dataset version. Account identifiers are independent of generated database IDs.
Only structured application content is passed to profile/opportunity endpoints;
provenance is kept outside application payloads and team-facing results.

The vocabulary reuses `docs/api/examples/tags.json`, adding only the synthetic
Java, Computer vision and Natural language processing IDs already used by US-06.
It is seeded exclusively into the new test database. No deployment vocabulary is
changed. The current opportunity contract has **no deadline field**; proposed
Sprint 2 specifications do not make deadlines available in the current API.

## Source admission and de-identification

Admit only public, owner-provided, explicitly authorised or approved de-identified
examples. Record permission and intended use in a non-sensitive source reference;
de-identification alone does not confer permission. A human reviewer must check
rights, indirect identifiers and necessity before including a new example.
Automated schema checks cannot prove consent or detect all personal information.

Remove real names, contact details, addresses, identifiers, unnecessary precise
dates and identifiable organisations from private examples. Use stable pseudonyms
and only supported structured fields. Review free-text evidence as well as names.
Never include confidential CVs/transcripts, source emails, credentials or private
original-file locations in fixtures or shared reports. If a permitted original
must be retained, keep it outside this repository with restricted access and
record only `originalFileRetained: true` and a safe source description.

For approved additions, update talent/opportunity records and the matching source
records together, explicitly set private defaults (`discoverable: false`,
`visibleFields: []`) unless a test requires disclosure, write labels independently,
and increment `datasetVersion` in manifest, source records and expected results.
Update source status/counts honestly and obtain QA review. Shared artifacts must
use synthetic or approved de-identified variants; do not put private originals
through this workflow. Keep later source packages versioned alongside the tests.

## Prepare a controlled run

Use the existing development dependencies (`backend/requirements-dev.txt`) and
run from the repository root. Windows:

```powershell
.\.venv\Scripts\python.exe scripts/prepare-test-data.py --run-dir data/sprint2-runs/run-001
```

macOS/Linux: use `.venv/bin/python` with the same arguments. `data/` is already
Git-ignored. The destination must **not exist**, even if empty. Preparation does
not load `.env`, uses an explicit new SQLite file and private upload directory,
does not accept a database URL, and overrides ambient `DATABASE_URL` and SMTP.
It never connects to the normal MySQL service or any existing SQLite database.
The live application uses MySQL; this workflow deliberately follows the existing
isolated SQLite pytest convention. It is not a MySQL deployment acceptance test.

For interactive tests, optionally supply a strong password through
`SPRINT2_TEST_PASSWORD` in your local environment before preparation. Do not put
it in a fixture, shell transcript or shared report. Accounts use the stable
account identifier followed by `@example.test`. Without this environment value,
a random password is generated in memory and is neither printed nor saved; the
Python helper returns authenticated test clients for automated use. Credentials
are stored only as normal application password hashes in the private test DB.

Preparation writes `test.sqlite3` and `starting-state.json`. The latter records
dataset version and SHA-256 identity, algorithm version, stable-to-runtime ID
mapping, roles/purposes, verified confirmation/discovery/publication revisions,
visible fields and content hashes. The versioned fixture contains the content
and requirements corresponding to each hash. No credentials, originals or private
source references are included in that report. Keep the database local; do not
commit it or include it in shared test evidence.

Preparation reuses account provisioning, controlled tag seeding, profile save and
confirmation, privacy writes and opportunity create/publish. It does not edit
application tables directly to bypass these rules. All profiles start private;
only the explicitly specified scenarios subsequently enable discovery.

## Restore/reset safely

Stop using the previous run and execute the **same command with a new directory**:

```powershell
.\.venv\Scripts\python.exe scripts/prepare-test-data.py --run-dir data/sprint2-runs/run-002
```

Use the new run's database/clients for the next test. This is restoration through
isolation, not an in-place reset: the old database, unrelated accounts, edited
profiles and uploaded files remain untouched. Reusing `run-001` fails before
opening its database. There is no DROP, broad delete, `/clear`, shared seed or
in-place overwrite path. A failed preparation is retained for diagnosis; retry
with a fresh directory. No cleanup is performed automatically.

The same version yields identical semantic starting content, state, revisions,
counts and expected outcomes. Each database uses the application's random IDs,
timestamps, password hashes and sessions; byte-identical databases and tie-order
rankings are not promised. Compare stable identifiers/content hashes rather than
runtime IDs. Each successful run has exactly 12 accounts, 10 profiles and 7
opportunities; repeated preparation never appends duplicates into an old run.

## Independent labels and current matching semantics

The first seven label sets preserve the manually authored US-06 expectations.
Additional labels encode existing US-05 privacy rules before execution. Expected
results are never obtained by executing matching and saving its output.

`tag-coverage-v1` uses REQUIRED=2 and PREFERRED=1. MATCHED contributes 1, PARTIAL
0.5, GAP/UNKNOWN 0. Explicit negative skill claims yield GAP; absent evidence
yields UNKNOWN. The fixtures preserve these rules, including required gap count,
unknown weight percentage and the current two-decimal rounding.

The empty-criteria case is a draft and is checked directly against the existing
engine: it returns INSUFFICIENT_CRITERIA with null score/unknown percentage. The
public API correctly cannot publish it. An incomplete but confirmed profile is
distinct from an unconfirmed profile: the latter returns PROFILE_UNCONFIRMED for
owner matching and is excluded from discovery. The name-only visible profile
has full private skills but receives only UNKNOWN results in team matching.

## Run linkage and verification

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_sprint2_data_preparation.py -q -o junit_family=legacy --junitxml=data/sprint2-runs/results.xml
.\.venv\Scripts\python.exe -m pytest backend/tests --require-frontend -q
.\.venv\Scripts\python.exe scripts/dev.py frontend test
.\.venv\Scripts\python.exe scripts/dev.py frontend format:check
.\.venv\Scripts\python.exe scripts/dev.py frontend build
```

Matching test cases attach `datasetVersion` and `datasetSha256` to their JUnit
properties; `starting-state.json` links a prepared run to the same fixture content.
US-11 should reference those values when defining quantitative measures, not
reinterpret synthetic accuracy as real-world relevance. US-16 should include
version/hash, application commit, environment, case ID, steps, actual outcome,
pass/fail and defects alongside its existing shared workflow report. Preparation
success is not proof of a successful browser workflow. Reuse the existing task
41/49/61 integration tests instead of duplicating them here.

Automated preparation tests check source completeness, schema/tag validity,
starting states, independent labels, all four statuses, visibility/exclusions,
metadata isolation, deterministic restoration, refusal of existing destinations,
duplicate counts and preservation of unrelated data/documents. They always use
their own SQLite databases, including when collected by the MySQL CI job. The
existing MySQL fixtures and CI configuration are unchanged.

See [the local verification record](sprint2-data-preparation-verification.md)
for actual commands, results and environment limitations for this change.

## Main synchronization compatibility (2026-10-23)

Version v2 uses the current ProfileContent skill records (`id`, `title`, `evidenceText`) and explicit empty defaults for the three new profile components. Negative claims retain their meaning as `No <skill>` titles. Existing tag-backed opportunity criteria and independently authored matching labels are unchanged. Duplicate skill record IDs and unknown interest tags are rejected before creating an isolated run. No existing database is migrated or overwritten by this dataset update.
