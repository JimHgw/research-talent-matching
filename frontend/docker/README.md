# Frontend-only Docker

This configuration builds the JavaScript frontend using Node 24 and pnpm 11.25.0,
then serves the production bundle with Nginx. The Python backend, virtual
environment and SQLite database stay on the host. No backend source, credentials,
test fixtures or local dependencies are copied into the image.

Install and start Docker Desktop on macOS/Windows, or Docker Engine with Compose
v2 on Linux. Verify availability with `docker version` and `docker compose version`.
The initial build downloads images and JavaScript dependencies.

## Start the existing backend

In a separate terminal, use the repository checkout where your backend environment
and database are already configured. From that checkout's root:

```sh
COOKIE_SECURE=false .venv/bin/python -m flask --app backend.app run --host 0.0.0.0 --port 8000
```

On Windows, from the equivalent checkout:

```powershell
$env:COOKIE_SECURE = 'false'
.\.venv\Scripts\python.exe -m flask --app backend.app run --host 0.0.0.0 --port 8000
```

Binding to `0.0.0.0` allows the container to reach the host service. This also
exposes the development backend on the host's network interfaces; use this
binding only for local testing on a trusted network. Keep `COOKIE_SECURE=false`
for this local HTTP session. Do not use Flask's development server as a public
deployment. Use [backend setup](../../backend/README.md) if accounts or the
database have not yet been provisioned. Existing account passwords are unchanged.

## Start the frontend

From the root of the checkout containing this Docker configuration:

```sh
docker compose -f frontend/compose.yaml config
docker compose -f frontend/compose.yaml up --build -d
docker compose -f frontend/compose.yaml ps
```

Open `http://127.0.0.1:5173`. Stop any local Vite process using port 5173 first.
Only the frontend service runs in Compose. Its port is published on loopback.

The browser sends requests to `/api/v1` on the page's origin. Nginx forwards them
to `http://host.docker.internal:8000` and preserves paths, cookies, the browser
Origin header and the CSRF header. The existing backend's default allowed origins
already include `http://127.0.0.1:5173` and `http://localhost:5173`.

Docker Desktop provides the host name; Compose also supplies a host-gateway
mapping for Linux. `127.0.0.1` inside a container refers to the container itself,
so do not use it as the backend target. To change the backend port on macOS/Linux:

```sh
API_PROXY_TARGET=http://host.docker.internal:9000 docker compose -f frontend/compose.yaml up -d
```

On PowerShell, set `$env:API_PROXY_TARGET = 'http://host.docker.internal:9000'`
before the same Compose command. The target must be an HTTP(S) origin without
an `/api/v1` suffix. This is a runtime setting, so changing it recreates the
container without requiring a frontend rebuild. Compose does not read
`frontend/.env` used by Vite; it reads the shell environment and its own .env rules.

## Verify and stop

```sh
curl -f http://127.0.0.1:5173/healthz
curl -i http://127.0.0.1:5173/api/v1/auth/session
docker compose -f frontend/compose.yaml logs --tail=100 frontend
```

The first command should return `ok`. It only checks the frontend server. The
second must reach the Python API and return its session response, including
session cookies. A `502` response usually means the backend is stopped, bound
only to loopback, or the target port is incorrect. Then verify valid/invalid
login, reload, logout and the backend-supported profile and opportunity flows in
the browser. An unimplemented API still returns an error; Docker adds no mock
fallback. The frontend's normal automated tests remain local (`npm test` after
setup); they are not included in the runtime image.

Changes to JavaScript, CSS or build configuration require running `up --build`
again. This container serves a production bundle without Vite hot reload.

```sh
docker compose -f frontend/compose.yaml down
```

This stops/removes the frontend container and its Compose network. It does not
delete the host backend environment or database. Build images/cache remain in
Docker and are not Git files. This configuration creates no database volume.

## References

- [Docker multistage builds](https://docs.docker.com/build/building/multi-stage/)
- [Docker Desktop host networking](https://docs.docker.com/desktop/features/networking/)
- [Official Nginx image template configuration](https://hub.docker.com/_/nginx)
