# US-01 supplement: verified-email registration and email/ID login

This supplement adds two endpoints under `/api/v1/auth`, within US-01
(H18ABANANA-9). Both `TALENT` and `RESEARCH_TEAM` may self-register. Existing
provisioned accounts and legacy `{email, password}` login requests remain supported.
The OpenAPI version is `0.1.2-draft`, with 29 operations in the overall contract.

## Request flow

1. Call `GET /api/v1/auth/session`; retain its cookie and `csrfToken`.
2. Call `POST /api/v1/auth/register/code` with the email address. A successful
   SMTP submission returns 202; the six-digit code is sent only by email.
3. Call `POST /api/v1/auth/register` from the same browser session with the email,
   emailed code, chosen password, display name and role. Success returns 201 with
   a `Session`, including the unique server-assigned `user.id`, and a new cookie.
4. For subsequent login, submit `{identifier, password}` to
   `POST /api/v1/auth/login`. `identifier` may be the email or the returned account
   ID. IDs are case-sensitive; emails are normalized to lowercase.

Every POST requires an allowed `Origin` and `X-CSRF-Token`. Replace the CSRF token
after registration or login. A signed-in user must sign out before registration.

## Send a verification code

`POST /api/v1/auth/register/code`

```json
{"email": "new-user@example.test"}
```

202 response:

```json
{"expiresAt": "2026-10-10T00:10:00Z", "resendAfterSeconds": 60}
```

The code is generated using `secrets.randbelow(1_000_000)` and formatted as exactly
six ASCII digits. Leading zeros are significant: `"012345"` is a valid code.
Only an Argon2id hash is stored. Codes and SMTP credentials are never returned or
logged. SMTP work runs outside the SQLite writer transaction; a pending or failed
delivery cannot authorize registration. SMTP acceptance does not guarantee that
the receiving provider places the message in the inbox.

## Complete registration

`POST /api/v1/auth/register`

```json
{
  "email": "new-user@example.test",
  "code": "012345",
  "password": "Example-only-password-123!",
  "displayName": "New User",
  "role": "TALENT"
}
```

All fields are required. Passwords contain 8–200 characters with at least one uppercase letter, lowercase letter and digit; `displayName` contains
1–100 characters and must not be blank. `role` is `TALENT` or `RESEARCH_TEAM`.
The caller cannot choose an account ID. The server generates `user_` plus 32
random hexadecimal characters, with database primary-key uniqueness. This ID
is an account identifier; password authentication is still required.

201 response:

```json
{
  "user": {
    "id": "user_0123456789abcdef0123456789abcdef",
    "displayName": "New User",
    "email": "new-user@example.test",
    "role": "TALENT"
  },
  "csrfToken": "example-only-new-csrf-token"
}
```

Account creation, verification-code consumption, anonymous-session revocation and
new-session creation commit atomically. Talent accounts also receive an empty
revision-0, unconfirmed profile and privacy settings with discovery disabled and
no visible fields. Team accounts represent one research team and do not receive
a talent profile. Existing email addresses cannot be registered twice.

## Subsequent login

`POST /api/v1/auth/login`

```json
{"identifier": "user_0123456789abcdef0123456789abcdef", "password": "Example-only-password-123!"}
```

The same request accepts an email in `identifier`. Existing callers may continue
to use the `email` field. Supply exactly one of `identifier` and `email`, with a
password. Both login aliases share the existing per-account login-attempt limit;
alternating email and ID cannot bypass it. The login screen accepts either value.
The login screen's **Register** button opens `/register`. Direct visits, page
reloads and browser back/forward navigation also open the corresponding page.
The form requests an emailed code, then collects the code, account type, display
name, password and matching password confirmation. It supports both roles,
enforces the new-password policy, shows a resend countdown and permits changing
the email address. API errors keep the form available for correction. Successful
registration updates the session/CSRF token and opens the account's workspace.

## Limits and errors

| Condition | Result |
| --- | --- |
| Malformed JSON / wrong media type / invalid fields | 400 / 415 / 422 |
| Missing CSRF, disallowed Origin or signed-in registration | 403 |
| Email already registered | 409 `EMAIL_ALREADY_REGISTERED` |
| Wrong, expired, missing, superseded or other-session code | 422 `VERIFICATION_CODE_INVALID` |
| Superseded or expired code request during delivery | 409 `VERIFICATION_CODE_INVALID` |
| Delivery missing configuration, refused or failed | 503 `EMAIL_DELIVERY_FAILED` |
| Cooldown, email/IP sending limit or exhausted code attempts | 429 `RATE_LIMITED` |

Codes expire after 10 minutes. Resending requires a 60-second wait and invalidates
the previous code. The requesting session must be retained. Five code submissions
are permitted per code; a correct fifth submission succeeds. Further submissions
require a new code. Sending is limited to 5 requests per normalized email and
20 per connecting IP per hour. Failed deliveries count toward sending limits.
Counters and hashes persist across restarts. Forwarded client IP headers remain
untrusted, consistent with the existing login implementation.

## SMTP configuration and existing installations

Run `init-db` again using the existing database configuration. This adds
`registration_codes` and `registration_attempts` without changing existing
accounts or profiles. Docker startup already runs `init-db`.

Native Windows setup:

```powershell
.\.venv\Scripts\python.exe -m flask --app backend.app init-db
$env:SMTP_HOST = 'your-mail-provider-host'
$env:SMTP_PORT = '587'
$env:SMTP_FROM = 'your-provider-approved-sender'
$env:SMTP_SECURITY = 'starttls'
$env:SMTP_USERNAME = 'your-mail-provider-username'
# Set SMTP_PASSWORD through your local environment or secret management.
```

For Docker, the SMTP-related variables in the root `.env` file are already 
configured, and Docker Compose passes them to the container. Since a native Flask
setup does not load the `backend/.env.example` file, these values ​​must be set within
the backend process's environment variables.

| Variable | Default | Meaning |
| --- | --- | --- |
| `SMTP_HOST` | empty | SMTP hostname; required for registration email |
| `SMTP_PORT` | `587` | SMTP TCP port; use the provider's port |
| `SMTP_FROM` | empty | Provider-approved sender address; required |
| `SMTP_SECURITY` | `starttls` | `starttls`, `ssl` (usually port 465), or `plain` for local SMTP testing |
| `SMTP_USERNAME` / `SMTP_PASSWORD` | empty | Provider credentials; username omission disables SMTP authentication |
| `SMTP_TIMEOUT` | `10` | Connection/read timeout in seconds |

Use `prune-sessions` to remove expired registration codes and old sending counters
alongside existing session/login data. Tests inject an email sender or use a local
SMTP test server; they never email real users.

### Gmail during local development

The current local sender is `3900banana@gmail.com`, configured in the ignored
root `.env` and shared by registration and password reset. Set both `SMTP_FROM`
and `SMTP_USERNAME` to this address. Gmail settings are `SMTP_HOST=smtp.gmail.com`,
`SMTP_PORT=587`, `SMTP_SECURITY=starttls`; set `SMTP_FROM` and `SMTP_USERNAME`
to the chosen Gmail address. Google documents these
[SMTP settings](https://support.google.com/mail/answer/7104828?hl=en).

Enable two-step verification in the Google account, then generate an
[app password](https://support.google.com/accounts/answer/185833?hl=en)
for Banana. Put the generated 16-character value in the local `.env` line
`SMTP_PASSWORD=`. Keep the file ignored by Git. The sender configuration alone
cannot authenticate; no email is sent while its authentication password is empty.

Compose reads the root `.env`; recreate the backend after changing credentials:

```powershell
docker compose up -d --force-recreate backend
```

For native Flask, export the same SMTP values into its process environment;
the application does not automatically read `.env`. Restart the backend after
changing its environment. Do not put credentials in this documentation or
`.env.example`. Live Gmail delivery requires the account owner's app password.

## Verification

`backend/tests/test_us01_registration.py` covers both roles, private defaults,
code hashing/expiry/resends/session binding, durable limits, SMTP configuration,
failed deliveries, replay and transaction rollback. The real HTTP integration in
`frontend/tests/us01-register-live.mjs` registers both roles through the actual
React form against Flask/SQLite, rejects an incorrect code, checks fresh talent
privacy defaults and signs in again with each server-assigned account ID.
`frontend/tests/task-18-registration.test.js` checks registration navigation,
browser history, password confirmation/policy, delivery failures, resend
countdowns, changing email and duplicate-submission protection.

Frontend registration verified on 2026-10-10: all 121 frontend tests, all seven
real HTTP frontend/backend workflows, the production build and formatting check
passed. The HTTP workflows use a test mailer and temporary databases; live Gmail
delivery requires the configured account credentials.

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_us01_registration.py -q
.\.venv\Scripts\python.exe -m pytest -q --require-frontend
```

See the [password-reset supplement](us01-password-reset.md) for both reset methods, password confirmation and the shared policy for newly chosen passwords.
