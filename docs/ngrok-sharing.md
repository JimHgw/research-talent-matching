# Using a fixed free ngrok URL

The frontend is available at `http://127.0.0.1:5173` on Windows and
`http://frontend:80` within the Docker network. Version 1.0.0 of the ngrok Docker Desktop extension
uses the fixed upstream address `172.17.0.1:<mapped-port>`. With this project's configuration,
which binds only to the loopback address, that address may refuse connections. The page can return
`ERR_NGROK_3004` even when the dashboard shows the endpoint as online.

This workflow uses the official ngrok agent container on the same Docker network as the frontend,
explicitly connecting to `http://frontend:80`. No router changes or exposure of local ports on other network interfaces are required.

First, switch off the endpoint for the same URL in the ngrok extension in Docker Desktop.
Keep the extension's existing account configuration. On its first run, the script reads the existing token
from the local extension and saves it to the Git-ignored `data/public-sharing/ngrok-agent.env`.
The token is not passed as a command-line argument or printed in the output.
If the extension is not configured, set `NGROK_AUTHTOKEN` locally before starting.

Run the following from the project root, replacing the example with the actual URL assigned to your account:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\share-ngrok.ps1 -Url https://your-name.ngrok-free.dev
```

A trailing `/` is accepted and removed automatically. Use the site's root URL without page paths or query parameters.

Startup builds the latest application images, automatically starts MySQL 8.4, waits for the database to be ready,
initializes tables and tags, starts the API, document worker and frontend, and updates allowed origins and HTTPS cookies.
There is no need to run a separate Compose startup command first.
If you do not need old data, run this script directly. A newly created MySQL database has no business records,
so accounts must be registered again. Old SQLite data is not automatically imported or deleted;
to preserve it, import it first using the [migration guide](mysql-migration.md).
Existing MySQL data and uploaded files are preserved, and later startups do not clear them.
The script keeps any recorded temporary Cloudflare URL as another allowed origin, and also preserves access
and login configuration for the local addresses `http://127.0.0.1:5173` and
`http://localhost:5173`; the port follows `FRONTEND_PORT`.
Different URLs use separate browser sessions, so you must sign in separately at each one.

The script displays `Share this URL` after successfully checking the public frontend and session endpoint.
On the ngrok free plan's interstitial page, visitors must click **Visit Site** to enter the website.
Registration and password reset continue to use the existing SMTP configuration in the root `.env`.

For subsequent starts, status checks, logs and stops:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\share-ngrok.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\share-ngrok.ps1 -Action status
powershell -NoProfile -ExecutionPolicy Bypass -File .\share-ngrok.ps1 -Action logs
powershell -NoProfile -ExecutionPolicy Bypass -File .\share-ngrok.ps1 -Action stop
```

Keep the computer connected to the network, awake and running Docker Desktop. The ngrok container is configured
to restart automatically, so the connection is restored after Docker restarts. After an explicit stop,
run the startup command again.
Stopping ngrok does not stop an existing Cloudflare tunnel. To stop that tunnel, use `share.ps1 -Action stop`.
That operation also restores the normal local login configuration; the next ngrok startup configures public login again.

References: [ngrok Docker image](https://github.com/ngrok/docker-ngrok),
[ERR_NGROK_3004](https://ngrok.com/docs/errors/err_ngrok_3004).
