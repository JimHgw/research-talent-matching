# Before Starting: Windows Docker Run Guide

This guide covers starting, checking and shutting down the complete application
from Windows PowerShell. The root Compose configuration runs MySQL, the
frontend, the backend and the document worker. Public sharing is optional.

For macOS and Linux, use the [Docker run guide](docs/docker-integration.md).

## 1. Prepare before starting

1. Start Docker Desktop and wait until its engine is ready. Use Linux containers.
2. Open PowerShell in your repository root, the directory containing
   `compose.yaml`.
3. Stop any native Vite/Flask processes or other applications using the configured
   frontend and backend host ports. The defaults are 5173 and 8000; an existing
   root `.env` or shell environment may override them through `FRONTEND_PORT`
   and `BACKEND_PORT`. Keep valid existing settings. Use the published addresses
   reported by Compose for health checks.
4. Keep using the existing Compose project name. The default is
   `banana-backend`; if you previously set `COMPOSE_PROJECT_NAME`, keep the same
   value so the application uses the same database volume.

The Docker workflow does not require activating `.venv`, installing host Python
or Node dependencies, or running `setup.ps1`. An already active `.venv` is fine.

If you need to keep data from an existing SQLite installation, follow the
[SQLite to MySQL migration guide](docs/mysql-migration.md) before starting the
updated application.

The root `.env` is optional for default local startup. If you need SMTP or port
settings, use the existing file or create it from `.env.example` using this command.

```powershell
if (-not (Test-Path -LiteralPath .\.env)) {
    Copy-Item -LiteralPath .\.env.example -Destination .\.env
}
```

If you need email registration or email-based password reset, configure SMTP in
the root `.env` before starting the application. Set `SMTP_HOST` and `SMTP_FROM`,
and provide `SMTP_USERNAME` and `SMTP_PASSWORD` if your mail provider requires
authentication. Match `SMTP_PORT` and `SMTP_SECURITY` to your provider. Compose
defaults to port `587`, `starttls` and an `SMTP_TIMEOUT` of `10` seconds when
those values are blank. Both sharing scripts use the same settings. Keep real
SMTP credentials out of Git commits.
See [registration and SMTP setup](docs/us01-registration.md).

## 2. Start the application: choose one mode

### A. Local use

Run from the repository root:

```powershell
docker compose up --build --detach --wait --wait-timeout 180 --force-recreate
```

This builds the application and starts MySQL, the frontend, the backend and
the document worker in the background.
Recreating the frontend together with the backend refreshes its connection to
the backend. Database and uploaded files are retained.

After the command succeeds, open <http://127.0.0.1:5173> when using the default
frontend port. With a custom `FRONTEND_PORT`, use that port instead. The backend
host port serves the API; the website is served through the frontend port.
`localhost` on another computer refers to that computer; use a public sharing
mode for people on other networks.

### B. Public access through your assigned ngrok URL

Use this mode when your ngrok account has an assigned development URL.

Before starting, turn off the same URL's endpoint in the Docker Desktop ngrok
extension to avoid a duplicate endpoint. Leave its account configuration intact.
The script can reuse the extension's existing token. Without a configured
extension, supply `NGROK_AUTHTOKEN` through your local environment before running
the script.

For the first run, replace the example URL with your assigned ngrok URL and run
the startup script.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\share-ngrok.ps1 -Url https://your-name.ngrok-free.dev
```

The script builds the application images, starts the services, configures public
login and connects ngrok directly to the frontend container. Wait until it prints
`Share this URL: ...`, then open and share that HTTPS URL.
If the browser shows ngrok's warning page, click **Visit Site**.

After a successful first run, the URL is saved locally. On later runs:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\share-ngrok.ps1
```

Pass `-Url` again if the saved URL is missing or your assigned URL changes.
The script accepts assigned HTTPS domains ending in `ngrok-free.dev` or `ngrok-free.app`.
An optional trailing `/` is accepted and removed automatically. Use the root
URL without a page path or query string.

### C. Public access through a temporary Cloudflare URL

For a temporary sharing URL, run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\share.ps1
```

The script builds and starts the application, configures public login and checks
the public frontend and session API. Wait for:

```text
Share this URL: https://<random-name>.trycloudflare.com
```

Share the actual displayed URL. A new tunnel can receive a different URL, so use
the script again when restarting sharing and distribute the latest URL.
If application code has not changed and images are already built, you may use:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\share.ps1 -NoBuild
```

For either public mode, keep this computer awake, online and running Docker
Desktop. Closing the PowerShell window does not stop the containers. A phone
using mobile data is a useful check that access works from another network.

When switching between local, ngrok and Cloudflare modes, first use the complete
shutdown command in section 5, then run the chosen startup command. This avoids
leaving an old sharing container running with outdated application settings.

## 3. Check the application after startup

Check all four services:

```powershell
docker compose ps
```

`mysql`, `frontend` and `backend` should be running and healthy.
`document-worker` should be running; it has no health probe or browser port.
A failed startup wait needs investigation before using or sharing the
application. The first build can take longer than 180 seconds; the wait timeout
applies to service startup after build.

Read the current published addresses and check the frontend, backend and API
proxy. These commands use the existing port mappings, including custom ports:

```powershell
$frontendAddress = docker compose port frontend 80
if ($LASTEXITCODE -ne 0 -or -not $frontendAddress) {
    throw 'Cannot resolve the frontend host port. Check docker compose ps.'
}
$backendAddress = docker compose port backend 8000
if ($LASTEXITCODE -ne 0 -or -not $backendAddress) {
    throw 'Cannot resolve the backend host port. Check docker compose ps.'
}

curl.exe -fsS "http://$frontendAddress/healthz"
curl.exe -fsS "http://$backendAddress/healthz"
curl.exe -i "http://$frontendAddress/api/v1/auth/session"
```

Expected results: frontend text `ok`; backend JSON with `"status":"ok"`; and
an HTTP 200 session response with `csrfToken` and a `Set-Cookie` header. A new
anonymous session has no signed-in user. The frontend health endpoint alone
does not prove that the API works.

For public access, also open the actual public URL and test login there. Use the
same browser hostname throughout a session. Local and public URLs have separate
browser sessions, so sign in separately when changing URLs.

## 4. Prepare accounts and verify the user workflows

Startup automatically creates missing database tables and seeds the shared
tags. It does not create default accounts or passwords. Existing Docker accounts
remain available after normal shutdown and container recreation.

Choose an account setup method:

- **Existing account:** sign in with its email or account ID and password.
- **Email registration:** with SMTP configured, click **Register**, request an
  email code and create a TALENT or RESEARCH_TEAM account.
- **Development/demo accounts without SMTP:** while the backend is running,
  provision accounts from PowerShell:

  ```powershell
  docker compose exec backend python -m flask --app backend.app provision-user --email talent@example.test --display-name "Demo Talent" --role TALENT
  docker compose exec backend python -m flask --app backend.app provision-user --email team@example.test --display-name "Demo Team" --role RESEARCH_TEAM
  ```

Each provisioning command prompts twice for a hidden password. Use 8-200
characters including an uppercase letter, a lowercase letter and a digit.
Provision each email only once; an existing email is rejected. These example
addresses are for demo login, not email delivery. Email registration and email
password resets still require SMTP.

After signing in:

1. **TALENT:** fill in **My profile**, save, review the saved information and
   select **Confirm profile**. Current confirmed information is used for matching.
2. **Optional document import:** in **My documents**, upload a PDF or DOCX up to
   10 MiB, wait for the worker, review and select the extracted sections, then
   apply them. Uploading alone does not update the profile. Confirm the profile
   again after importing or changing its content. Scanned PDFs or unsupported
   layouts may require manual entry.
3. **Team discovery consent:** in **Privacy & visibility**, allow discovery,
   select the fields to share and save. New talent profiles are private by
   default. Team discovery requires both a currently confirmed profile and consent.
4. **RESEARCH_TEAM:** in **My opportunities**, create an opportunity, enter its
   requirements, save and publish it. Drafts are not available for matching.
   Use **Discover talent** for one of your published opportunities.
5. **Recommendations:** return to the talent account and inspect recommended
   opportunities and their explanations. A fresh database has no opportunities
   until a team publishes one; an empty result can also reflect no eligible match.
6. Reload the page and verify that saved data remains. For a two-role demo, use
   separate browser profiles or a private window to keep the sessions independent.

The document worker already runs in Docker; there is no extra worker command to
run on the host. Docker storage does not automatically import accounts from a
native `data/h18abanana.db` file.

## 5. Finish: stop sharing or shut down everything

### Completely shut down the project

Use this command for local mode or either public sharing mode:

```powershell
docker compose down --remove-orphans
```

It stops and removes the project's frontend, backend, document worker, remaining
`tunnel`/`ngrok` containers and project network. `--remove-orphans` handles
sharing services defined in additional Compose files, preventing the network
from remaining in use after an ordinary `docker compose down`.

The database and uploaded files in the named volume are preserved. Do not add
`-v` or `--volumes` to a normal shutdown: those options delete the data volume.
Use the same startup mode again next time; account provisioning is not repeated.

### Stop ngrok sharing while keeping the application running

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\share-ngrok.ps1 -Action stop
```

This stops only ngrok. It does not stop a separate Cloudflare tunnel or restore
the base local settings. To return fully to local mode, use complete shutdown,
then the local startup command.

### Stop Cloudflare sharing and restore local application settings

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\share.ps1 -Action stop
```

This stops the Cloudflare tunnel and recreates the local application services.
The local website remains available. It does not stop a separate ngrok container;
if both were running, use complete shutdown to finish everything.

## 6. Status, logs and common problems

Application logs:

```powershell
docker compose ps
docker compose logs --tail=100 frontend backend document-worker
docker compose logs --follow --tail=100 frontend backend document-worker
```

Press **Ctrl+C** to leave the live log view. This does not stop the containers.

Sharing status and logs (use the commands for your chosen mode):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\share-ngrok.ps1 -Action status
powershell -NoProfile -ExecutionPolicy Bypass -File .\share-ngrok.ps1 -Action logs
powershell -NoProfile -ExecutionPolicy Bypass -File .\share.ps1 -Action status
powershell -NoProfile -ExecutionPolicy Bypass -File .\share.ps1 -Action logs
```

| Problem | Action |
| --- | --- |
| Cannot connect to Docker | Start Docker Desktop and confirm Linux containers are selected. |
| A configured host port is already in use | Stop the process using that port. For custom ports, update the root `.env`; changing `FRONTEND_PORT` also requires matching `ALLOWED_ORIGINS`. |
| Windows reports a socket access-permission error with no process listening | Check `netsh interface ipv4 show excludedportrange protocol=tcp`. Choose an available host port outside the excluded ranges and set `BACKEND_PORT` in the root `.env`. Keep an existing valid port. The backend's internal container port remains 8000. |
| Startup times out or the page returns 502 | Inspect application logs and container status. For local mode, rerun the full local startup command to recreate frontend and backend together; for public mode, rerun its sharing script. |
| The page opens but login/save fails | Keep one URL per session; for public access, rerun the sharing script to refresh the allowed origin and session settings. |
| Registration/reset email does not arrive | Check the root `.env` SMTP settings, provider credentials and spam folder. Reapply settings using your chosen startup mode. Demo provisioning is available for login without SMTP. |
| No matching results | Confirm the talent's latest saved profile, publish an opportunity and, for team discovery, save consent and field visibility. |
| A document stays queued | Check `document-worker` status and logs. |
| Network reports `Resource is still in use` on shutdown | Run `docker compose down --remove-orphans` to remove remaining project sharing containers. |

After code or `.env` changes, rerun the startup process for the mode you are
using. Running only the base local startup command while sharing can replace
public login settings.

Further detail: [Docker integration](docs/docker-integration.md),
[ngrok sharing](docs/ngrok-sharing.md),
[Cloudflare sharing](docs/public-sharing.md), and
[document processing](docs/us09-documents.md).
