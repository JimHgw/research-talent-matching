# Migrating from SQLite to MySQL

The project uses **MySQL 8.4 + PyMySQL + SQLAlchemy** by default. No changes to the frontend or HTTP API are required.
SQLite connections can still be configured explicitly for legacy data migration, rollback and quick regression tests.

## Starting MySQL without migrating old data

Use this section for a new environment or when you do not need the old SQLite accounts, profiles or other records.
**Skip the migration commands below; there is no need to delete old SQLite files or data volumes.**
Check that neither the process environment nor the root `.env` contains a `DATABASE_URL` that still points to SQLite.
If one exists, remove that override and use the `MYSQL_*` settings described below. This creates an application database
with no business records when `mysql_data` is first created. If a MySQL data volume already exists, normal startup
continues to use its data and does not clear it automatically.

Review `.env.example` in the project root. If you already have a `.env`, merge in the new `MYSQL_*` settings
while keeping your existing SMTP, port and other settings. The example passwords are for local development only;
set your own passwords for deployment. The MySQL image creates the database and accounts only when the data volume
is first initialized. With an existing MySQL volume, editing `.env` does not automatically change database passwords.
Update the accounts in MySQL first, then update the API/worker configuration to match.

```sh
docker compose up --build --detach --wait --wait-timeout 180
```

Compose waits until MySQL accepts connections, initializes the backend and vocabulary, then starts the frontend and document worker.
MySQL does not expose a host port by default; the backend connects through the internal address `mysql:3306`.
`mysql_data` stores the database, while the existing `backend_data` retains uploaded files and old SQLite files.
A new MySQL database does not automatically import old accounts or create default accounts.
Startup automatically creates tables and initializes the tag vocabulary; accounts must be registered again or created with `provision-user`.
Old uploaded files do not automatically appear in the new database or user interface, even if they remain in `backend_data`.

## Migrating an existing Docker environment

**To preserve old SQLite data, complete this section before starting the updated API.** Normal startup initializes
the vocabulary, and the migration command refuses to import into any MySQL database that already contains business data.
Keep the original Compose project name so that the original `backend_data` is mounted. Do not change the project name
or delete the data volumes.

**US-14 compatibility step:** If the source SQLite file predates US-14, keep an original backup first.
On a working copy, use that copy's `DATABASE_URL` to run `init-db` and
`upgrade-opportunity-search`, then pass the upgraded copy to `migrate-sqlite --source`.
The migration tool validates the source column set and does not skip missing columns. See the [US-14 upgrade notes](us14-search.md#upgrade-and-rollback).

1. Stop the API and document worker to pause application writes, and save the current version and database configuration.

   ```sh
   docker compose stop backend document-worker
   docker compose build backend
   ```

2. Create a consistent SQLite backup in a temporary container that still mounts the old data volume.
   The backup is saved in the original volume with a timestamped filename. Uploaded files remain in
   `/app/data/documents`; back up the entire documents directory separately.

   ```sh
   docker compose run --rm --no-deps --entrypoint python backend -c "import sqlite3; from datetime import datetime, timezone; source = sqlite3.connect('file:/app/data/h18abanana.db?mode=ro', uri=True); name = '/app/data/h18abanana-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.backup.db'; target = sqlite3.connect(name); source.backup(target); target.close(); source.close(); print(name)"
   ```

3. Start MySQL, then run the migration command directly. Override the container entrypoint here to avoid running `seed-tags` beforehand.

   ```sh
   docker compose up --detach --wait --wait-timeout 180 mysql
   docker compose run --rm --no-deps --entrypoint python backend -m flask --app backend.app migrate-sqlite --source sqlite:////app/data/h18abanana.db
   ```

   The migration copies all known application tables in foreign-key order, including accounts and password hashes,
   sessions, profiles, privacy settings, opportunities, saved items, shortlists, document metadata, extraction results
   and worker leases. IDs, JSON, null values and UTC timestamps with microsecond precision are preserved.
   Row counts and content checksums are calculated in primary-key order for each table; the migration commits only
   after all values match. Any failure rolls back the copied data, although MySQL table creation may leave empty tables.
   The original SQLite file is not modified.

   Migration stops if the target database is not empty, source columns do not match or unknown tables are present.
   Do not clear an existing target database to retry. Check the configuration first, or have a database administrator
   prepare a separate empty database. If an older version lacks an entire table added by a later version, the migration
   treats it as empty. Confirm that these tables have not yet been used.

4. Start all services only after seeing `Migration committed`.

   ```sh
   docker compose up --build --detach --wait --wait-timeout 180
   docker compose ps
   ```

   Sign in with an existing account and check profiles, privacy settings, opportunities, saved items and shortlists.
   Upload a document and wait for extraction, and confirm that old files can still be downloaded.
   Restart the services and check again that the data persists.

Rollback: stop the API/worker, explicitly set `DATABASE_URL` in the root `.env` to
`sqlite:////app/data/h18abanana.db`, then start the services. The old SQLite database contains only data from before
the switch. Additions and changes made after switching to MySQL are not automatically synchronized back to SQLite;
if new writes have occurred, plan a reverse migration first.
Do not delete either data volume. `docker compose down` preserves data; `down -v` deletes it.

## Local Flask development or local SQLite migration

Reinstall the backend dependencies, then expose the MySQL port only on the local loopback address:

```sh
docker compose -f compose.yaml -f compose.mysql-local.yaml up --detach --wait --wait-timeout 180 mysql
```

Local Flask connects to `127.0.0.1:3306` by default. The default username, password and database name match `.env.example`.
For custom settings, export the variables from `backend/.env.example` to the API and worker processes; Flask does not load that file automatically.
You can also use `DATABASE_URL=mysql+pymysql://user:url-encoded-password@host:3306/database?charset=utf8mb4`.
Separate `MYSQL_*` settings construct the URL through SQLAlchemy, so special characters in passwords do not need manual encoding.

On Windows, stop the local Flask/worker processes and back up `data/` before migrating:

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt
.\.venv\Scripts\python.exe -m flask --app backend.app migrate-sqlite --source sqlite:///data/h18abanana.db
```

On macOS/Linux, replace the Python path with `.venv/bin/python`. Do not run `seed-tags` before migrating.
After a successful migration, start the API/worker using the existing backend startup instructions.
Local and Docker migrations use different source databases; choose the data source actually used by your application.
The migration command transfers database records only and does not copy uploaded files. If the storage directory changes,
copy all files and preserve their storage-key mappings.

## Database behavior and verification

- Strings have explicit lengths, evidence and descriptions use long text, and JSON retains its structure.
- Tables use InnoDB, `utf8mb4` and the case-sensitive `utf8mb4_0900_bin` collation to preserve ID comparison behavior.
- Timestamps use UTC `DATETIME(6)`; foreign keys, unique constraints and CHECK constraints remain enforced.
- MySQL write transactions first lock the single row in `database_write_lock`, preserving SQLite's existing serialized
  write behavior to protect revision checks, rate limits and document leases. The lock is released on commit or rollback.
  Read-only transactions use a consistent snapshot. The current implementation prioritizes consistent behavior;
  write concurrency remains limited by this global lock, which could later be replaced with locks for individual resources.
- `init-db` creates missing tables only and does not alter existing table structures. Future schema upgrades still require separate migrations.

Tests use temporary SQLite databases by default. Regression tests against a real MySQL instance require a dedicated
test database whose name ends with `_test`. This mode clears the project's tables in the test database; do not use an application database.

```powershell
$env:MYSQL_TEST_DATABASE_URL='mysql+pymysql://banana:test-password@127.0.0.1:3306/banana_test'
.\.venv\Scripts\python.exe -m pytest backend/tests --run-mysql -q
```

The CI `backend_mysql_test` runs as three independent jobs, each with its own MySQL 8.4 service.
Tests are assigned deterministically by test ID. Together, the jobs still run the complete suite without missing or
duplicating cases, while avoiding the Runner's 10-minute limit for an individual job.
Local runs without sharding arguments still execute all tests; use `--shard-index 1 --shard-total 3` to reproduce the first job separately.
Each test process recreates tables only at the beginning and end. Between cases, records are deleted in foreign-key
order while retaining the transaction-lock row, balancing data isolation and test speed. CI saves JUnit reports and
the ten slowest test durations to help investigate future performance issues.
Sharding uses [GitLab parallel jobs](https://docs.gitlab.com/ci/yaml/#parallel).
Tests cover successful migration, value-by-value verification, rollback on failure, refusal to overwrite existing data,
login with original passwords, and existing application concurrency and permission regressions.
`--run-docker` separately verifies the complete container stack, automatic document processing and persistence after container recreation.

To run the 14 environment checks that the default suite skips (five MySQL migration/storage checks,
eight academic upgrade variants, and one complete Docker stack check), start Docker Desktop's Linux engine
and run this command from the repository root after setup:

```powershell
.\.venv\Scripts\python.exe scripts/test-environment.py
```

On macOS/Linux, use `.venv/bin/python scripts/test-environment.py`.
The runner creates a separate MySQL 8.4 container with a new test database, random credentials and
a dynamically allocated loopback port. It enables both test flags, requires all 14 checks to execute
and pass with zero skips, and saves a JUnit report under `.pytest_cache/environment-tests/`.
The stack check creates its own unique Compose project. Both environments clean up their temporary
containers and data; existing application containers, databases and volumes are not used.
The first run may download images, build application images and download the pinned semantic model.
Windows also requires Git Bash for the automatic startup upgrade checks.

For Sprint 3 BE-8, add `--include-be8` to also verify query/filter/page equivalence,
batch-query bounds and the required real application model on the disposable MySQL server.
Use `--report docs/testing/be8/mysql-docker.xml` to retain the combined acceptance report.
See [BE-8 query measurements and index upgrades](testing/be8/README.md).

For connection and transaction configuration, see the [SQLAlchemy MySQL documentation](https://docs.sqlalchemy.org/en/20/dialects/mysql.html).
For timestamp precision, see the [MySQL fractional seconds documentation](https://dev.mysql.com/doc/refman/8.4/en/fractional-seconds.html).

## Resume description capacity upgrade

The API limit for `resumeDescription` is 20,000 characters. Four-byte Unicode characters can require up to
80,000 bytes within this limit, exceeding MySQL TEXT capacity, so new tables use MEDIUMTEXT.
For existing databases, rebuilding the application image or running `init-db` does not automatically change existing column types.

For local deployments, stop API/worker writes, keep a database backup and the existing configuration, then run:

```powershell
.\.venv\Scripts\python.exe -m flask --app backend.app init-db
.\.venv\Scripts\python.exe -m flask --app backend.app upgrade-resume-text
```

On macOS/Linux, use `.venv/bin/python`. The upgrade only widens the existing
`profile_text_details.resume_description` column from TEXT to MEDIUMTEXT, preserving its utf8mb4 character set,
collation, NOT NULL constraint and data. It does not change profile revisions, confirmation status or provenance.
Existing MEDIUMTEXT/LONGTEXT columns and SQLite require no changes, and the command is safe to repeat.
An unrecognized existing column definition stops the upgrade for maintainer review, avoiding implicit changes to other constraints.

The Docker entrypoint explicitly runs this upgrade after `init-db` and before starting the API/worker;
rebuild and update the application using the existing workflow. MySQL DDL commits separately, so this step is not
a data migration within a transaction. Do not rely on an ordinary application transaction rollback to undo the column-type
upgrade. There is no need to delete data volumes.

`backend/tests/test_us11_review_regressions.py` covers manual saves, reviewed imports, complete round trips of
17,000/20,000 four-byte characters, atomic rejection when the limit is exceeded, and data preservation and repeated
execution after upgrading an old TEXT column, using a real MySQL test database.
