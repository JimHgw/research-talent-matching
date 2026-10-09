# Research matching backend

Flask + SQLite + SQLAlchemy ORM implementation for provisioned-account login and
manual talent profiles, confirmation, privacy, research opportunities and two-sided matching. Requests and responses follow the checked-in
[Sprint 1 contract](../docs/api/sprint-1-api-contract.md) and its OpenAPI models.

## First step after cloning: install the development environment

**After pulling the repository, run the setup program before writing code,
starting either service or running tests.** Run it again after dependency files
change. Choose the entry point for your operating system.

### macOS / Linux

Install Python 3.12+ and Node.js 22.13+ **with npm**, and make `python3`, `node`
and `npm` available on PATH. On Linux, the Python installation also needs its
`venv`/`ensurepip` support (some distributions package it separately).
From the repository root:

```sh
sh setup.sh
```

From `backend/`, use `sh ../setup.sh`. To choose a particular Python, use
`PYTHON=python3.12 sh setup.sh`. The script creates/reuses `.venv/bin/python`,
installs backend dependencies and the pinned project-local pnpm, installs frontend
dependencies from the lockfile, then runs both test suites and required real HTTP
integration. It needs internet access for downloads; no global pnpm or Codex
installation is required. Missing/old runtimes produce an error; the script does
not run Homebrew, apt, sudo or change your shell configuration.

### Windows

From the repository root:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\setup.ps1
```

If your terminal is already inside `backend/`, use:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File ..\setup.ps1
```

The program uses its own location, so it also works when invoked with an absolute
path from another directory. Wait for **Setup complete** before continuing.
It performs these steps automatically:

1. Reuse Python 3.12+ or install Python 3.13 with WinGet, then create/reuse `.venv/`.
2. Reuse Node.js 22.13+ with npm, or install Node.js LTS with WinGet.
3. Install all backend runtime and test dependencies from `requirements-dev.txt`.
4. Install the pnpm version pinned in `frontend/package.json` inside `.venv/node-tools/`.
5. Install frontend runtime and development dependencies using `pnpm-lock.yaml`
   with `--frozen-lockfile`.
6. Run the backend suite, real frontend HTTP integration, and frontend suite
   (including its production-build check). Any failure stops setup with an error.

Requirements: Windows 10/11, PowerShell 5.1+, and internet access to download
dependencies. Missing runtimes are installed using [WinGet](https://learn.microsoft.com/en-us/windows/package-manager/winget/install).
If WinGet is missing, install Microsoft's [App Installer](https://aka.ms/getwinget)
and rerun setup. Windows may request permission when installing Node.js.
`ExecutionPolicy Bypass` applies only to this process; no permanent policy change
is made. Existing compatible runtimes and the virtual environment are reused.
A broken or outdated `.venv` is reported rather than overwritten; rename it and
rerun setup to create a new one. Database contents, accounts and `.env` files are
not changed by setup; tests use separate temporary databases.

The installer records local Node/pnpm paths in the ignored `.venv/toolchain.json`.
Pytest and the frontend launchers (`run.ps1` / `run.sh`) read it automatically, so new terminals can find Node
without setting `NODE_BINARY` or relying on a Codex installation. Do not commit
`.venv/` or `node_modules/`; commit the setup scripts, manifests and lockfile.
If you move the checkout or remove a runtime, rerun setup to refresh these paths.

Both installers leave accounts, database contents and `.env` files unchanged.
Do not copy `.venv/` or `node_modules/` between operating systems: recreate them
on the destination machine. Shell scripts use LF endings via `.gitattributes`.

## Implemented scope

| Method | Path (under `/api/v1`) | Access |
| --- | --- | --- |
| GET | `/auth/session` | Anonymous or signed in; supplies CSRF token |
| POST | `/auth/login` | Provisioned credentials + anonymous session/CSRF |
| POST | `/auth/logout` | Signed in + CSRF |
| GET | `/tags` | Either signed-in role; optional `kind=SKILL` or `INTEREST` |
| GET | `/me/profile` | Talent owner |
| PUT | `/me/profile` | Talent owner + CSRF + expected revision |
| POST | `/me/profile/confirmation` | Talent owner + CSRF + current revision |
| GET | `/me/privacy` | Talent owner |
| PUT | `/me/privacy` | Talent owner + CSRF + independent privacy revision |
| GET | `/opportunities` | Signed in; published by default, `scope=mine` for teams |
| POST | `/opportunities` | Team + CSRF; creates an owned draft |
| GET | `/opportunities/{id}` | Signed in; drafts restricted to their owner |
| PUT | `/opportunities/{id}` | Team owner + CSRF + expected revision |
| POST | `/opportunities/{id}/publish` | Team owner + CSRF + expected revision |
| GET | `/me/recommendations` | Talent owner with a currently confirmed profile |
| GET | `/me/opportunity-matches/{id}` | Talent owner; published opportunity and current confirmation |
| GET | `/opportunities/{id}/talent-matches` | Owner team of a published opportunity |
| GET | `/opportunities/{id}/talent-matches/{talentId}` | Owner team; currently confirmed, opted-in talent |

The React pages use these routes without a mock service. US-05 includes the
owner privacy endpoints needed to enable discovery through the existing privacy
page. Team matching filters consent, confirmation and field visibility before
scoring, ranking and pagination; every request evaluates current data.
See [US-05 implementation and acceptance](../docs/us05-implementation.md).
Document upload/extraction endpoints (US-09) remain unimplemented.
There is no public registration or default password.

## Files

The backend follows the frontend's `src/`, feature and test organization:

```text
backend/
  app.py                  # Stable entry point: flask --app backend.app
  src/
    app.py                # Application factory, configuration and CLI commands
    features/
      auth/routes.py      # Login, logout, sessions and account provisioning
      profile/routes.py   # Owner profile editing and controlled vocabulary
      opportunities/      # HTTP routes, lifecycle service and ordered persistence
    db/
      database.py         # Database access and transactions
      models.py           # Shared SQLAlchemy schema
    shared/
      paths.py            # Repository-relative resource paths
      security.py         # Session lookup, role and CSRF checks
      validation.py       # OpenAPI validation and API errors
      pagination.py       # Strict pagination using OpenAPI defaults and limits
  tests/                  # Backend checks and real frontend integration
  requirements.txt        # Runtime dependencies
  requirements-dev.txt    # Runtime and test dependencies
  pytest.ini              # Test discovery when working inside backend/
  .env.example            # Backend environment-variable reference
```

Features use `db/` and `shared/` without importing another feature. Register new
feature blueprints in `src/app.py`. The repository's `docs/api/` remains the shared
contract and fixture source; existing SQLite files remain in the root `data/`.

## Start the services

### macOS / Linux

After setup completes, run from the repository root:

```sh
.venv/bin/python -m flask --app backend.app init-db
.venv/bin/python -m flask --app backend.app seed-tags
.venv/bin/python -m flask --app backend.app provision-user --email talent@example.test --display-name "Demo Talent" --role TALENT
.venv/bin/python -m flask --app backend.app provision-user --email team@example.test --display-name "Demo Team" --role RESEARCH_TEAM
export COOKIE_SECURE=false
.venv/bin/python -m flask --app backend.app run --host 127.0.0.1 --port 8000
```

In another terminal, from the repository root:

```sh
sh frontend/run.sh dev
```

From inside `backend/`, the equivalent server command is
`../.venv/bin/python -m flask --app src.app run --host 127.0.0.1 --port 8000`.
Set `COOKIE_SECURE=false` in that terminal as well.

### Windows

After **First step after cloning** completes, run from the repository root:

```powershell
.\.venv\Scripts\python.exe -m flask --app backend.app init-db
.\.venv\Scripts\python.exe -m flask --app backend.app seed-tags
.\.venv\Scripts\python.exe -m flask --app backend.app provision-user --email talent@example.test --display-name "Demo Talent" --role TALENT
.\.venv\Scripts\python.exe -m flask --app backend.app provision-user --email team@example.test --display-name "Demo Team" --role RESEARCH_TEAM
$env:COOKIE_SECURE = 'false'
.\.venv\Scripts\python.exe -m flask --app backend.app run --host 127.0.0.1 --port 8000
```

Each provision command prompts twice for a hidden password. Use those passwords
in the login page. A talent account, empty revision-0 profile and default privacy
settings are created in one transaction. Reusing an email is rejected. The seed
command explicitly loads the shared tags from `docs/api/examples/tags.json`;
repeating an identical seed is safe. Application startup does not create accounts
or silently insert demo data.

In another PowerShell terminal, from `frontend/`:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\run.ps1 dev
```

Open `http://127.0.0.1:5173`. The existing Vite configuration forwards `/api` to
port 8000. Use the same browser hostname throughout. No `.env` copy is required
for these defaults.

To work from `backend/`, reuse the same virtual environment and run:

```powershell
..\.venv\Scripts\python.exe -m flask --app src.app run --host 127.0.0.1 --port 8000
```

Set `COOKIE_SECURE=false` in that terminal for local HTTP as above. The same
`--app src.app` entry supports `init-db`, `seed-tags`, `provision-user` and
`prune-sessions`. Both entry points resolve relative database and contract paths
from the repository root, regardless of the terminal's working directory.

## Configuration and storage

These are process environment variables; the backend does not automatically load
`.env`. `backend/.env.example` lists them for reference.

| Variable | Default | Meaning |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite:///data/h18abanana.db` | File-backed SQLite; relative paths resolve from the repository root |
| `COOKIE_SECURE` | `true` | Set exactly `false` only for local HTTP development; keep `true` for HTTPS |
| `ALLOWED_ORIGINS` | `http://127.0.0.1:5173,http://localhost:5173` | Comma-separated exact frontend origins, with no trailing slash |

Keep production frontend/API on the same origin behind HTTPS. Cross-origin CORS
is not enabled. Configure the real HTTPS frontend origin before deployment; the
Flask development server is for local use. No session token is returned in JSON:
`h18_session` is an HttpOnly, SameSite=Lax, host-only cookie with path `/`.

Implementation defaults are 24-hour signed-in sessions, 1-hour anonymous
sessions, and a 15-minute login-attempt window with limits of 10 per normalized
email and 30 per connecting IP. These are implementation choices, not new API
requirements. The factory configuration can override these limits for tests.
Counters survive restarts and include successful attempts. Forwarded IP headers
are not trusted; a deployment using a reverse proxy must deliberately configure
trusted proxy handling before relying on per-client limits.

Passwords use Argon2id; session bearer tokens are stored only as SHA-256 digests.
Login rotates session and CSRF tokens; logout revokes the current session.
Every mutation requires its session's CSRF token and an allowed Origin. All API
responses have `Cache-Control: no-store`.

`src/db/models.py` defines the US-01 account, session, vocabulary, profile and privacy
tables using `Mapped`, `mapped_column` and child-to-parent `relationship` mappings.
These mappings retain the existing tables, columns, indexes and constraints;
no schema migration is needed for this mapping update. Relationships do not
enable cascading deletion of accounts or other independent resources.
Four academic arrays use JSON; skills/interests use ordered FK rows.
Document metadata is included only as the FK target for profile provenance.
Each connection enables SQLite foreign keys. Short write transactions acquire
`BEGIN IMMEDIATE` before reading revisions; expensive password hashing and
verification happen outside those locks. Session cookies are emitted only after
successful commit. Profile writes replace all eight content fields, reject stale
revisions with 409 and preserve the full response on a no-op. Actual changes
increment the revision, reset confirmation and mark only changed academic sections
as manual. Unchanged section provenance is preserved.

`init-db` creates missing tables; it does **not** migrate existing table shapes.
Coordinate a migration before later modules change this schema. The `data/`
directory, local environments and credentials are ignored by Git.

### Adding US-02 to an existing US-01 installation

Run `init-db` again using the same database configuration before restarting the
backend. US-02 only adds `opportunities`, `opportunity_requirements` and
`requirement_tags`; existing accounts, profiles and tags keep their current schema
and data. Run `seed-tags` if this installation has not loaded the vocabulary.

Opportunity routes handle session/role/CSRF checks and transaction boundaries.
`features/opportunities/service.py` owns visibility, tag validation, revision
checks and draft/publication transitions; `repository.py` owns ordered writes and
public serialization. Lists batch-load children, filter before counting, then
sort by update time descending and ID ascending. Owner information stays internal.
Requirements use stable IDs scoped to an opportunity, with foreign keys to shared
tags. Drafts may have zero requirements; published opportunities may not.

Writes acquire the existing SQLite writer lock before checking revisions. No-op
updates and repeated publication at the current revision preserve timestamps and
revisions. Stale updates/publication return 409 without changing any rows. Changes
to an already published opportunity remain published. Future matching can use
`published_opportunities()` and current ordered requirement/tag rows; US-02 does
not add recommendation endpoints or cached scores.

See [US-02 implementation and acceptance](../docs/us02-implementation.md) for module
extension points, the UI workflow and test coverage.

Maintenance command:

```sh
.venv/bin/python -m flask --app backend.app prune-sessions
```

On Windows:

```powershell
.\.venv\Scripts\python.exe -m flask --app backend.app prune-sessions
```

## Verification

For full US-01 / US-02 acceptance, from the repository root on macOS/Linux:

```sh
.venv/bin/python -m pytest -q -rs --require-frontend
sh frontend/run.sh test
```

On Windows:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -rs --require-frontend
powershell -NoProfile -ExecutionPolicy Bypass -File .\frontend\run.ps1 test
```

From `backend/`, use `../.venv/bin/python` (macOS/Linux) or
`..\.venv\Scripts\python.exe` (Windows) with the same pytest arguments.
The root `pytest.ini` forwards discovery to `backend/tests/`; backend-local
configuration supports running the same suite from inside `backend/`.

Test databases and other pytest temporary files default to the repository's
`.pytest_cache/tmp/`, avoiding Windows system-temp permission errors. Pytest
manages separate numbered directories for each run. Explicit `--basetemp` or
`PYTEST_DEBUG_TEMPROOT` settings take precedence. These files are ignored by Git.

To run just the real frontend integration test from the repository root:

```sh
.venv/bin/python -m pytest backend/tests/test_frontend_integration.py -q --require-frontend
```

On Windows:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_frontend_integration.py -q --require-frontend
```

Run test files through `python -m pytest`, rather than directly with `python`;
pytest loads the project import paths and the app/database fixtures.

Backend checks cover contract responses, cookie rotation/revocation, expiry,
CSRF/Origin, roles, default privacy, persistence across app restarts, complete
replacement and clearing, no-op behavior, invalid inputs, rollback, provenance,
foreign keys, login throttling and concurrent writes from independent connections.
Regression checks also cover bracketed array indices in validation error paths,
contract-valid HTTP 405 errors with the `Allow` header, and ORM relationship
loading without weakening foreign-key deletion restrictions.
`tests/test_layout.py` also checks database path stability and executes database
initialization, default tag seeding and route discovery from both working directories.

With frontend dependencies installed and Node located through setup's toolchain,
`NODE_BINARY` or PATH, pytest also runs
`tests/test_frontend_integration.py`: it starts a temporary Python HTTP server and uses
the actual React app in jsdom against an isolated SQLite file. It verifies login,
all eight profile fields, reload, conflicting saves, logout, account isolation and
the team shell. It also runs the US-02 React flow through draft creation, ordered
requirements, reload, publication, editing, conflict comparison, talent discovery
and cross-team access. Shared browser setup lives in `frontend/tests/support/live-app.js`.
The US-05 flow exercises privacy opt-in, published-opportunity selection, all four
statuses, hidden fields, anonymous talent, revocation and profile edit invalidation.
`tests/test_us05.py` separately checks ownership, pagination, deterministic ranking,
the team evidence shape and privacy revision/CSRF rules against real SQLite.
It simulates browser Cookie/Origin transport; it does not test
browser layout, Vite proxying or HTTPS cookie enforcement. Set `NODE_BINARY` to
an absolute Node executable to override automatic selection. On a manually
configured environment, this integration test is explicitly skipped when Node or
frontend dependencies are unavailable; use `pytest -rs` to display the reason.
With `--require-frontend`, missing Node/jsdom is a failure, not a skip. Both setup
scripts use this flag. Omit it only for backend-only development; a skipped HTTP
test is not evidence that integration passed. The two WinGet installer tests
remain intentionally skipped on macOS/Linux. Portable setup tests run on all
platforms and cover platform-specific paths, directories with spaces, failure
propagation and the strict integration requirement. Those simulated setup tests
do not replace running the full suite on each native OS.

The existing frontend suite remains separate:

```sh
sh frontend/run.sh test
sh frontend/run.sh build
sh frontend/run.sh format:check
```

On Windows:

```powershell
cd frontend
powershell -NoProfile -ExecutionPolicy Bypass -File .\run.ps1 test
powershell -NoProfile -ExecutionPolicy Bypass -File .\run.ps1 build
powershell -NoProfile -ExecutionPolicy Bypass -File .\run.ps1 format:check
```

For manual acceptance, provision an account, open the Vite page, sign in, edit
the profile, save, refresh and check the saved values. Two tabs editing the same
revision must show a conflict on the second save. Sign out and sign in as another
account to verify the previous owner's content is no longer shown.

For US-02, sign in as a team, choose **Opportunities**, create a draft, add skill
or interest requirements, save and publish. Sign in as talent to browse its
published details. Another team can read the published content but cannot edit
it. `tests/test_us02.py` covers the lifecycle, permissions, validation, pagination,
restarts, foreign keys, rollback and simultaneous writers against real SQLite.
