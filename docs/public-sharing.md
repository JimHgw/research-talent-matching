# Sharing a temporary URL from your Windows computer

If you already have a fixed free ngrok URL, see the [ngrok guide](ngrok-sharing.md).

Visitors on other Wi-Fi networks, university networks or mobile data need a public URL.
`localhost` and `192.168.x.x` addresses cannot be accessed directly across these networks.
This project uses Cloudflare Quick Tunnel to connect a temporary HTTPS URL to the Docker frontend
on your computer. The frontend then forwards `/api/v1` to the backend on the same computer.
The database and uploaded files remain in the existing Docker data volumes.

## Starting the services and getting the URL

Start Docker Desktop using Linux containers, then run the following from the project root:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\share.ps1
```

The first run downloads Cloudflare's official image and builds the application. On success, it displays:

```text
Share this URL: https://<random-name>.trycloudflare.com
```

Share the actual URL displayed with other people. They can open it directly in a browser without installing
software or connecting to the same Wi-Fi network. To verify access, turn off Wi-Fi on your phone and use mobile data.
The local addresses `http://127.0.0.1:5173` and `http://localhost:5173` remain available.
The sharing configuration also keeps both addresses as allowed login origins; the port follows `FRONTEND_PORT`.

The script adds this exact URL to the backend's allowed origins and enables HTTPS session cookies
so that login and saving work as well as page access. It checks the public health endpoint and API session
before reporting success. The current URL is saved in the Git-ignored `data/public-sharing/public-url.txt`.
Existing accounts continue to work. New user registration still requires an SMTP email service configured
in the root `.env`. The tunnel does not replace email delivery. Without SMTP, you can create accounts
interactively on the local computer by following the [Docker deployment guide](docker-integration.md).

If the application code has not changed, you can skip rebuilding:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\share.ps1 -NoBuild
```

## Checking status and stopping

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\share.ps1 -Action status
powershell -NoProfile -ExecutionPolicy Bypass -File .\share.ps1 -Action logs
powershell -NoProfile -ExecutionPolicy Bypass -File .\share.ps1 -Action stop
```

Stopping closes the public tunnel and restores the normal local Docker configuration without deleting the database.
External access also stops if the computer shuts down, sleeps, loses its network connection or stops Docker.
The URL changes when the tunnel is recreated, so run the startup script again to update the backend configuration.
The container does not automatically restart the tunnel, preventing allowed origins from still pointing to an old
URL after it changes. Closing the PowerShell window does not stop the tunnel running in Docker.
The existing Compose project name is kept by default. If you previously set `COMPOSE_PROJECT_NAME`, continue using the same value.

Quick Tunnel is suitable for temporary demonstrations and testing. It has no availability guarantee,
supports up to 200 concurrent in-flight requests and does not support SSE. Anyone with the URL can reach
the site's login and registration pages; the application's existing account permissions still apply.
For long-term use with a fixed URL, you can switch to a Cloudflare Tunnel connected to your own domain.
See the [official Cloudflare Quick Tunnel documentation](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/).
