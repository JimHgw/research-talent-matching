# Docker run guide for macOS and Linux

For Windows PowerShell startup and the project's ngrok and Cloudflare sharing
scripts, see the [Windows Docker run guide](../README_BEFORE_START.md).

The root `compose.yaml` runs four containers in the existing
`banana-backend` project: Nginx serves the frontend, Gunicorn serves the Python
API, a document worker processes uploads, and MySQL stores database records. They join `banana-backend_default`; Docker resolves the backend service name
without a host gateway or fixed container IP.

The browser sends relative `/api/v1` requests from the published frontend address.
Nginx forwards the complete path to `http://backend:8000`, preserving cookies,
Origin and the CSRF header. The backend's host port can change without changing
this internal address. The frontend builds from `./frontend`; the backend builds
from the repository root with its own Dockerfile and build-context exclusions.

## Install Docker

- On **macOS**, install Docker Desktop for your Mac's chip and open it. It includes
  Compose. [Docker Desktop for Mac](https://docs.docker.com/desktop/setup/install/mac-install/)
- On **Linux**, follow your distribution's instructions to install and start Docker
  Engine with the Compose plugin. [Docker Engine](https://docs.docker.com/engine/install/) ·
  [Compose plugin](https://docs.docker.com/compose/install/linux/)

Run these checks in a terminal. `docker version` should show server details.
Use a Compose version that supports `up --wait`. Python and Node run inside the
application images. [Compose startup options](https://docs.docker.com/reference/cli/docker/compose/up/)

```sh
docker version
docker compose version
```

## Configure the project

The stack uses MySQL 8.4. If you need to keep data from an existing SQLite
installation, complete the migration before starting the updated stack.
[SQLite to MySQL migration guide](mysql-migration.md)

Open a terminal in the repository root, where `compose.yaml` lives. Compose
reads the root `.env` automatically. Use the existing file for overrides, or
create it from the template if it is missing.

```sh
if [ ! -e .env ]; then
    cp .env.example .env
fi
```

For custom ports or MySQL settings, see [ports, cookies and storage](#ports-cookies-and-storage).

For email registration or email-based password reset, configure SMTP in that
`.env` before startup. Set `SMTP_HOST` and `SMTP_FROM`, and add `SMTP_USERNAME`
and `SMTP_PASSWORD` if your mail provider requires authentication. Match
`SMTP_PORT` and `SMTP_SECURITY` to your provider. Compose defaults to port
`587`, `starttls` and an `SMTP_TIMEOUT` of `10` seconds when those three settings
are blank. Keep real SMTP credentials out of Git commits.
[SMTP setup and registration](us01-registration.md)

## Start the stack

Stop any processes using the frontend and backend host ports before starting.
The first build downloads the base images and dependencies. Run from the
repository root.

```sh
docker compose config --quiet
docker compose up --build --detach --wait --wait-timeout 180 --force-recreate
docker compose ps
```

MySQL, the backend and the frontend should report healthy. The document worker
should report running. The 180-second wait covers startup after the build.
If startup times out, inspect `docker compose logs --tail=100` before retrying.

Open `http://127.0.0.1:5173` with the default frontend port. If you changed
`FRONTEND_PORT`, use the address from `docker compose port frontend 80`.
Startup prepares the database and seeds tags. Sign in with an existing account
or use **Register** after configuring SMTP. To create development accounts,
run these commands.

```sh
docker compose exec backend python -m flask --app backend.app provision-user --email talent@example.test --display-name "Demo Talent" --role TALENT
docker compose exec backend python -m flask --app backend.app provision-user --email team@example.test --display-name "Demo Team" --role RESEARCH_TEAM
```

Each command prompts for a hidden password twice. Keep using one browser hostname
throughout a session. Docker volumes do not automatically import the host's
`data/h18abanana.db` file or host accounts.

## Verify the complete path

Read the published addresses before checking health and the API proxy. These
commands work with the port overrides in your root `.env`.

```sh
frontend_address=$(docker compose port frontend 80)
backend_address=$(docker compose port backend 8000)
curl -fsS "http://${frontend_address}/healthz"
curl -fsS "http://${backend_address}/healthz"
curl -fsi "http://${frontend_address}/api/v1/auth/session"
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

Use the root `.env` for Docker overrides. `frontend/.env` configures Vite when
running the frontend on the host.

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

## Stop the stack

Use `docker compose stop` to stop services and keep their containers. Use
`docker compose down` to stop services and remove their containers and network.
Both commands preserve the named volumes for the database and uploads. Adding
`--volumes` to `docker compose down` deletes those volumes.

## Separate workflows and updates

For native development on macOS or Linux, install the host runtimes and run
`sh setup.sh` from the repository root. Then follow the service startup steps
for MySQL, the API, the document worker and Vite.
[Native setup](../backend/README.md#first-step-after-cloning-install-the-development-environment) ·
[Native startup](../backend/README.md#start-the-services)

`sh docker-backend.sh` or `docker-backend.ps1` still builds/starts only the backend,
for use with native Vite. Use [the frontend-only configuration](../frontend/docker/README.md)
only with a backend running on the host. The integrated route avoids the Linux
host-loopback/host-gateway mismatch. Do not merge the root and frontend-only
Compose files: their relative build contexts refer to different directories.

After changing application code or `.env`, repeat the startup command to apply
the changes and refresh Nginx's connection to the backend. [Start the stack](#start-the-stack)

Nginx and the upload endpoint allow 11 MiB request bodies for 10 MiB files plus
multipart overhead. The backend also validates the actual file size and format.
Other endpoints retain their 4 MiB request limit. Private originals and the
worker's persistent claims share the backend data volume.
