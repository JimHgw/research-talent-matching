# BE-9 database release and recovery

Base reviewed: `41ae6db8b71b6608b7b8ed459fdf732901d23d3c`.

## One startup sequence

Stop API and document-worker writes, retain configuration and take a verified backup first. With the intended `DATABASE_URL`, run from the repository root:

```powershell
.\.venv\Scripts\python.exe -m flask --app backend.app prepare-db
.\.venv\Scripts\python.exe -m flask --app backend.app check-schema
```

On Unix use `.venv/bin/python`. Only start the API and worker if these commands exit successfully. Docker's shared entrypoint runs `prepare-db` before executing either service. Use matching API/worker images from the same release; mixed-version rolling upgrades are not supported. Do not run individual migration commands concurrently with a release.

The single sequence is `init-db` → `upgrade-opportunity-search` → `upgrade-query-indexes` → `upgrade-academic-requirements --if-mysql` → `upgrade-resume-text` → `seed-tags` → `check-schema`. Existing individual CLI commands remain available for diagnosis. `prepare-db` holds a database-scoped MySQL advisory lock across the entire sequence, including independently committed DDL, so API/worker startup cannot race during table creation or seeding.

- Fresh installation: `init-db` creates the current tables, indexes and constraints. Explicit upgrades are no-ops, vocabulary loads, and compatibility is checked. No accounts are provisioned.
- Existing installation: `init-db` creates **missing tables only**. The subsequent explicit migrations alter legacy structures; `create_all()` is not a migration engine. Known additive columns receive NULL; missing optional detail rows keep existing serializer defaults. Business records and revisions are not backfilled or rewritten.
- Retry: after diagnosing a supported partial failure, rerun the complete command while services remain stopped. Already completed schema changes are preserved. A vocabulary conflict is an error, not permission to replace tags.
- SQLite: current schemas and supported additive upgrades work; the historical MySQL academic upgrade deliberately skips SQLite. Migrating a historical SQLite requirement constraint needs a separately reviewed copy/rebuild procedure; no automatic destructive rebuild is introduced here.

`check-schema` is read-only. It verifies required tables/columns, BE-8 index definitions, MySQL resume capacity/charset/nullability, academic criteria and allowed kinds, and the writer-lock row. Each application process performs full schema validation once during factory/startup and retains a process-local readiness result. `/healthz` reads that result and, when schema-ready, executes only a DB connectivity query (`SELECT 1`); it never performs schema inspection. It preserves the existing status JSON, request-ID headers and session-free behaviour. Failed startup validation or lost DB connectivity returns a generic 503. Connectivity recovery restores health only if schema readiness was already established. `prepare-db` clears readiness before its first step and restores it only after the complete sequence succeeds. After repairing a schema externally, restart the API process to establish fresh readiness; probes do not detect runtime DDL drift or revalidate a failed startup. Native document-worker startup also checks compatibility and exits before claiming jobs. Docker never reaches the server/worker command if preparation fails. The worker has no HTTP health endpoint; its startup exit and the API dependency are the existing deployment gates. Schema inspection is not a general repair tool for arbitrary custom schemas. Stop all writers for upgrades; runtime DDL under active services is unsupported.

Semantic model resources remain governed by the existing matching runtime. Verify the release's local model manifest/checksums and BE-7 acceptance separately; model unavailability can use structured fallback and is not a schema-readiness failure.

## Schema inventory at the reviewed main

| Area | Required action / compatibility evidence |
| --- | --- |
| BE-2 reviewed import / BE-3 save and confirmation | Existing profile JSON, revisions, confirmation, document extraction and provenance tables remain the contract. No additional ALTER attributable to these tasks is present in this main. Verify preserved values rather than inferring that every planned service refactor has merged. |
| BE-4 transactions | Existing `database_write_lock` singleton and revision columns; `init-db` adds missing tables and idempotently ensures the mutex row. No revision resets. |
| BE-5 visibility | Existing privacy revision, discovery flag and visible-field rows; no new columns. Owner document/resume data is not copied into team tables. |
| BE-6 worker recovery | Existing `document_processing_leases` separate table; missing table creation is additive. Existing lease tokens, attempts and expiries are retained. |
| BE-7 scoring | Existing academic requirement `kind VARCHAR(32)`, nullable JSON `criteria`, and five-kind constraint; academic upgrade supports older SKILL/INTEREST schemas. Scoring introduces no persisted score column. |
| BE-8 pagination | `upgrade-query-indexes` adds `ix_opportunities_owner_page` and `ix_opportunities_active_page` after opportunity columns exist. |
| Other current-main compatibility | Opportunity type/deadline/expiry/source nullable additions; resume TEXT → MEDIUMTEXT; missing free-text skill, personal-interest-description, provenance, saved/shortlisted tables created through metadata. Missing personal-interest descriptions remain omitted through the existing outer join. |

Sources: `backend/src/db/{models,collections,database,opportunity_upgrade,query_upgrade,academic_upgrade,schema_upgrades,interests}.py`, current feature routes/repositories and `backend/docker/entrypoint.sh`. The BE-2–BE-8 plan is not itself evidence of deployed schema changes.

## Backup and restore checklist

1. Record application image/commit, DB version/charset, environment configuration and the source database name. Stop both writers and prevent external writes. Snapshot `DOCUMENT_STORAGE_DIR` alongside the database; database rows alone do not contain original files.
2. Use a MySQL 8.4 client with credentials supplied through a protected client option file or secret environment, never command-line password text. For InnoDB, export using `mysqldump --single-transaction --skip-lock-tables --no-tablespaces --set-gtid-purged=OFF --hex-blob DATABASE`. Preserve dump bytes directly (avoid Windows text-pipeline recoding); protect and checksum the backup.
3. Restore into a **different, newly created empty database**, with `utf8mb4` / `utf8mb4_0900_bin`, using `mysql RESTORE_DATABASE` and the dump as binary stdin. Restore original documents to a separate matching directory. Do not drop or overwrite the failed database.
4. Compare row counts and canonical per-table values/checksums, password hashes, role, profile/privacy revisions, confirmation, document references and opportunity requirements/state against the backup manifest. Test both role logins with fictional accounts in a rehearsal; never export real passwords.
5. If recovering the previous release, run its compatible code against the restored pre-upgrade schema and files. If retrying this release, point only the isolated/restored environment at the copy, run `prepare-db` twice, verify health/worker/login and business values, then arrange a controlled configuration switch while writers remain stopped.

MySQL DDL commits independently. Transaction rollback or reverting application code does **not** undo all schema changes. Recovery may lose post-backup writes; a stopped-writer upgrade window is essential. Keep the failed DB and backup until acceptance. Never delete application volumes as a migration step.

## Reproducible verification

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_sprint3_be9.py --run-docker -q
.\.venv\Scripts\python.exe -m pytest backend/tests --require-frontend --run-docker -q
```

The BE-9 Docker test creates a random-name MySQL 8.4 container, tmpfs storage and loopback-only random port; it removes only that container. It never attaches to an existing database. Existing `--run-mysql` tests require a disposable database ending in `_test` and clear it; never point that option at development or shared data.

The fixture covers both real password hashes/roles, confirmed profile and revision 7, privacy revision 4 and visible fields, Unicode JSON and free text, document/extraction/provenance references, controlled/personal tags, saved/shortlisted records, published and expired opportunities and tagged requirements. It snapshots every table, simulates supported old columns/indexes and a missing optional table, upgrades twice, and compares old values exactly plus new NULL defaults. The API contract supplies the 20,000-character resume boundary: Chinese plus four-byte emoji is written, preparation rerun, application connections recreated, and every value compared again before login tests.

Failure coverage includes each ordered step, a missing index, and a real incompatible MySQL criteria column. Health returns 503 and the worker exits. A real `mysqldump`/`mysql` restore into another empty database is compared exactly to the pre-upgrade snapshot, then upgraded and compared to the successful upgraded snapshot. Existing Docker smoke tests additionally exercise actual API/worker containers and restart persistence. The in-process BE-9 restart alone is not claimed as a container restart.

## Execution record — 2026-11-14

Health-probe review, 2026-11-15: the affected startup, release-gate and worker suites (`test_docker_backend.py`, `test_sprint3_be9.py`, `test_us09_worker.py`) report **44 passed, 1 skipped**. The skipped case is the opt-in Docker/MySQL backup/restore rehearsal; it was not rerun for this probe-only change. Regression assertions verify one startup schema check, repeated probes issuing only `SELECT 1` (plus SQLite transaction start), unchanged status/request-ID behaviour, connection failure/recovery, incompatible-startup rejection and readiness invalidation after every failed preparation step. JUnit: `.pytest_cache/be9-health-review.xml`.

| Check | Result |
| --- | --- |
| Final complete backend suite, including required frontend integration and real Docker stack | **811 passed, 18 skipped, 0 failed/errors** across the existing three disjoint shards: 245/7, 264/5, 302/6 passed/skipped. Each command used `--require-frontend --run-docker --shard-total 3 --shard-index N`. No tests were excluded from their union. |
| BE-9 isolated MySQL 8.4 release/recovery | **9 passed**, no skips; fresh API health/worker, legacy data, repeated upgrades and unchanged column/index/constraint inventory, both role logins, valid profile response, Chinese/emoji 20,000-character resume, failure gates and actual dump/restore all passed. |
| Real MySQL migration, academic, query-index, startup and profile regression group | **120 passed, 4 skipped**. |
| Real MySQL resume-boundary, worker and BE-9 gate group after updating the worker startup contract | **42 passed, 1 skipped**. Includes existing API save/import boundary tests. |
| Final SQLite startup and worker group | **35 passed**, no skips. |

The full-suite skips are 13 MySQL-only cases (covered separately using the disposable MySQL runs) and 5 local real-model cases because application model files are absent (`FileNotFoundError`). The MySQL groups skip non-MySQL-only coverage, separately executed Docker-only recovery, and two unavailable-model cases. No real-model acceptance is claimed. The actual isolated Docker stack test passed, including restart, stored file/extraction, login/logout/relogin and profile persistence.

An earlier run exposed the old test expecting the worker to create its lease table automatically. It now asserts refusal before preparation, preservation of the queued document, and successful processing after `prepare-db`; final complete regression and both database-specific reruns pass. Local JUnit records are retained in the ignored `.pytest_cache/be9-final-{1,2,3}.xml`, `be9-release.xml`, `be9-validation-mysql.xml`, `be9-boundary-worker.xml` and `be9-startup-worker.xml`.

Docker was initially stopped. Starting its engine also resumed the existing restart-enabled stack; tests used only newly named disposable resources and never targeted that stack. Test resources were removed and the engine was returned to its stopped state. No shared database recovery, live deployment or production model acceptance was performed.

Changed files: `backend/src/db/release.py`, `backend/src/app.py`, `backend/docker/entrypoint.sh`, `backend/tests/test_sprint3_be9.py`, `backend/tests/test_docker_backend.py`, `backend/tests/test_us09_worker.py`, `backend/README.md`, `docs/mysql-migration.md`, `docs/README_SPRINT_3_DEVELOP_EN.md`, `docs/README_SPRINT_3_DEVELOP_CN.md`, and this report.
