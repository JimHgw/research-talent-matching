# Frontend and backend in Docker

To let people on other networks access this computer through a temporary HTTPS
URL, use `share.ps1` and [the public sharing guide](public-sharing.md).

The root `compose.yaml` runs four containers in the existing
`banana-backend` project: Nginx serves the frontend, Gunicorn serves the Python
API, a document worker processes uploads, and MySQL stores database records. They join `banana-backend_default`; Docker resolves the backend service name
without a host gateway or fixed container IP.

The browser opens `http://127.0.0.1:5173` and sends relative `/api/v1` requests.
Nginx forwards the complete path to `http://backend:8000`, preserving cookies,
Origin and the CSRF header. The backend's host port can change without changing
this internal address. The frontend builds from `./frontend`; the backend builds
from the repository root with its own Dockerfile and build-context exclusions.

## Start the stack

The database is MySQL 8.4 in its own service. **Existing SQLite installations must
follow the [migration guide](mysql-migration.md) before starting the new stack.**
MySQL uses `mysql_data`; `backend_data` retains uploaded files and the original SQLite database.

Install and start Docker Desktop with Linux containers on macOS/Windows, or Docker
Engine with Compose on Linux. Use Compose with `up --wait` support. Host Python,
Node and the native virtual environment are not required for this workflow.
The first build downloads the base images and dependencies.

From the repository root, on macOS, Linux or PowerShell:

```sh
docker compose config --quiet
docker compose up --build --detach --wait --wait-timeout 180
docker compose ps
```

Stop existing Vite/Flask processes or other containers using ports 5173/8000
before startup. The frontend starts after the backend reports healthy; the wait
also checks the frontend health endpoint. Build time is separate from the
180-second startup wait. A failed wait is not a successful deployment; inspect
`docker compose logs --tail=100` before retrying.

Open `http://127.0.0.1:5173`. These containers serve the real API without demo
fixtures or a mock fallback. The backend initializes missing tables and seeds
tags, but does not create accounts automatically. Configure SMTP in the root
`.env`, then use **Register** on the login screen or visit `/register` to create
a TALENT or RESEARCH_TEAM account with an emailed verification code. See the
[registration guide](us01-registration.md) for SMTP setup and password rules.
For development accounts, provisioning is also available:

```sh
docker compose exec backend python -m flask --app backend.app provision-user --email talent@example.test --display-name "Demo Talent" --role TALENT
docker compose exec backend python -m flask --app backend.app provision-user --email team@example.test --display-name "Demo Team" --role RESEARCH_TEAM
```

Each command prompts for a hidden password twice. Keep using one browser hostname
throughout a session. Docker volumes do not automatically import the host's
`data/h18abanana.db` file or host accounts.

## Verify the complete path

```sh
curl -f http://127.0.0.1:5173/healthz
curl -f http://127.0.0.1:8000/healthz
curl -i http://127.0.0.1:5173/api/v1/auth/session
```

The first endpoint checks Nginx; the second checks the backend/database. The third
must return the API session JSON and cookie through Nginx. Then verify sign-in,
profile saving, page reload, privacy and opportunity flows using provisioned
accounts. Upload a PDF/DOCX and wait for review suggestions without invoking a
worker manually. See [US-09 extraction rules and recovery](us09-documents.md).

For native regression tests, run the existing frontend and Python checks after
host setup. The Docker configuration tests also run without a Docker daemon when
the Docker Compose CLI is installed:

```sh
.venv/bin/python -m pytest backend/tests/test_docker_stack.py -q -rs
```

On Windows use `.\.venv\Scripts\python.exe` instead. The actual isolated-container
smoke test is opt-in and requires a working Linux Docker engine:

```sh
.venv/bin/python -m pytest backend/tests/test_docker_stack.py -q -rs --run-docker
```

It creates a unique Compose project and test data volumes, checks all four containers,
API proxying, login, profile writes, automatic document processing and restart persistence, then removes only
that temporary project's containers, network and volume. It does not use the
default project's accounts or database. Configuration tests alone do not prove
that images build or containers communicate.

## Ports, cookies and storage

Copy the root `.env.example` to `.env` for overrides. Compose reads the root
`.env` automatically; the existing backend-only launchers explicitly select it.
`frontend/.env` remains a Vite configuration file and does not configure the
integrated Nginx proxy.

| Variable          | Default                            | Meaning                                                   |
| ----------------- | ---------------------------------- | --------------------------------------------------------- |
| `FRONTEND_PORT`   | `5173`                             | Browser port; frontend container still listens on 80      |
| `BACKEND_PORT`    | `8000`                             | Optional direct host API port; internal API stays on 8000 |
| `COOKIE_SECURE`   | `false`                            | Local HTTP only; use true behind HTTPS                    |
| `ALLOWED_ORIGINS` | Local browser origins on port 5173 | Exact browser origins for CSRF validation                 |

When changing `FRONTEND_PORT`, update `ALLOWED_ORIGINS` to match, for example
`http://127.0.0.1:5174,http://localhost:5174`. The browser still uses `/api/v1`.
Do not set its API URL to `http://backend:8000`: that name is internal to Docker.
Production also requires HTTPS and deliberate trusted-proxy configuration.

The existing project name `banana-backend`, volume key `backend_data`, and mount
`/app/data` are unchanged. With the default project name, the existing volume is
`banana-backend_backend_data`; uploaded files survive container
replacement. Continue using the same `COMPOSE_PROJECT_NAME` if you previously
overrode it. Different checkouts on one engine can address the same project.

MySQL records persist in `banana-backend_mysql_data`. Both API and document worker
use the same MySQL settings. Configure `MYSQL_DATABASE`, `MYSQL_USER`, `MYSQL_PASSWORD`
and `MYSQL_ROOT_PASSWORD` in the root `.env`; defaults are for local development.
MySQL has no host port unless you add `compose.mysql-local.yaml` for native development.

```sh
docker compose stop
docker compose down
```

Both preserve the database volume. Do not add `--volumes` / `-v` unless you intend
to erase that project's data. Images and build cache are Docker resources, not
repository files.

## Separate workflows and updates

`sh docker-backend.sh` or `docker-backend.ps1` still builds/starts only the backend,
for use with native Vite. Use [the frontend-only configuration](../frontend/docker/README.md)
only with a backend running on the host. The integrated route avoids the Linux
host-loopback/host-gateway mismatch. Do not merge the root and frontend-only
Compose files: their relative build contexts refer to different directories.

After changing frontend/backend code, rebuild the affected images. If replacing
the backend container, also recreate the frontend so Nginx resolves the backend's
new container address:

```sh
docker compose up --build --detach --wait --wait-timeout 180 --force-recreate
```

Nginx and the upload endpoint allow 11 MiB request bodies for 10 MiB files plus
multipart overhead. The backend also validates the actual file size and format.
Other endpoints retain their 4 MiB request limit. Private originals and the
worker's persistent claims share the backend data volume.
