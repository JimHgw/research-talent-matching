# US-01 supplement: password rules and password reset

Both TALENT and RESEARCH_TEAM can reset passwords from the login screen's
**Reset password** button. Choose **I remember my password** or **Use an email
code**. The endpoints are additions to US-01 (H18ABANANA-9), under
`/api/v1/auth/login/reset`. OpenAPI version: `0.1.2-draft`.

## Password policy

New passwords must contain **8–200 characters**, including at least one ASCII
uppercase letter (`A–Z`), lowercase letter (`a–z`) and digit (`0–9`). Eight is
the minimum length, not an exact length. Symbols are permitted. Registration,
administrative provisioning and both reset methods enforce the same rule.
Existing passwords remain usable for login and original-password verification;
accounts do not change until the user explicitly sets a new password.

For reset, `newPassword` and `confirmPassword` must match exactly and the new
password must differ from the currently stored password. Neither input is
trimmed. The backend checks equality with the current password using Argon2id
verification, not hash-string comparison. Passwords are never returned or logged.
The frontend checks strength and confirmation before submission; the backend
enforces every rule independently.

## Session and CSRF requirements

First obtain the cookie and `csrfToken` using `GET /api/v1/auth/session`.
Every POST requires this cookie, an allowed `Origin` and `X-CSRF-Token`.
The endpoints accept anonymous sessions. A signed-in caller may only reset their
own account. Preserve the same session throughout the email flow.

## Remembered password

`POST /api/v1/auth/login/reset`

```json
{
  "method": "PASSWORD",
  "identifier": "talent@example.test",
  "currentPassword": "Example-only-password-123!",
  "newPassword": "Example-only-new-password-456!",
  "confirmPassword": "Example-only-new-password-456!"
}
```

`identifier` accepts the email address or the server-assigned account ID. Emails
are case-insensitive and IDs are case-sensitive. Original-password checks share
the existing per-account and per-IP login-attempt limits; alternating email and
ID cannot bypass them. An incorrect password, unknown account or inactive
account returns the same `401 INVALID_CREDENTIALS` response.

## Forgotten password

1. `POST /api/v1/auth/login/reset/code` with `{"email":"talent@example.test"}`.
   Returns **202 PasswordResetCodeResponse**:
   `{"expiresAt":"2026-10-10T00:10:00Z","resendAfterSeconds":60}`.
   A six-digit code is sent to an active registered account. Unknown/inactive
   addresses receive the same response shape without an email being sent.
2. `POST /api/v1/auth/login/reset/verify` with the email and emailed code:

   ```json
   {"email":"talent@example.test","code":"012345"}
   ```

   Returns **200 PasswordResetVerifyResponse**:
   `{"verified":true,"expiresAt":"2026-10-10T00:10:00Z"}`. The code is consumed
   as a verification credential and replaced by a server-side permission to
   reset once, bound to this session and the current password hash. The login UI
   only displays the new-password fields after this verification succeeds.
3. `POST /api/v1/auth/login/reset` after successful verification:

   ```json
   {
     "method": "EMAIL_CODE",
     "email": "talent@example.test",
     "newPassword": "Example-only-new-password-456!",
     "confirmPassword": "Example-only-new-password-456!"
   }
   ```

The verification permission expires at the original code expiry (10 minutes
after requesting it). Registration codes and password-reset codes are separate
and cannot be substituted for one another. Codes use cryptographically random
six-digit ASCII strings, including leading zeros, and only their Argon2id hashes
are stored. Unsent or failed deliveries cannot authorize verification.

The latest request replaces the previous code and any already verified reset
permission. Sending has a 60-second cooldown, with limits of 5 requests per
normalized email and 20 per connecting IP per hour. Failed sends count toward
these limits. Each code permits five verification attempts; a correct fifth
attempt succeeds. Attempts and permissions persist across application restarts.

## Successful reset

Both methods return **200 Session** with `user=null`, a new anonymous cookie and
new CSRF token. Password update, code/permission removal, revocation of **all**
login sessions for the account, and anonymous-session replacement commit in one
transaction. Reauthenticate with the new password. ID, email, profile, role and
privacy settings are preserved. No existing application database is modified by
the regression tests.

Weak passwords, different confirmation values and reuse of the current password
return `422 VALIDATION_ERROR`. Missing, wrong, expired, superseded or
other-session email verification returns `422 VERIFICATION_CODE_INVALID`.
Too many checks or emails return `429 RATE_LIMITED`. Concurrent changes to the
password return `409 PASSWORD_RESET_INVALID`; restart verification. SMTP errors
return `503 EMAIL_DELIVERY_FAILED`. Errors use the standard `Error` structure.
Neither the API client nor UI automatically retries password mutations.

## Existing installations and SMTP

Run `init-db` again to add `password_reset_codes` and `password_reset_attempts`:

```powershell
.\.venv\Scripts\python.exe -m flask --app backend.app init-db
```

Docker startup runs this initialization automatically. Email resets reuse the
[registration SMTP configuration](us01-registration.md#smtp-configuration-and-existing-installations).
Set the provider's host, port, sender, security and credentials in the backend
environment (or the ignored root `.env` for Docker). SMTP is required only for
the email path. `prune-sessions` also removes expired reset state and old sending
counters. Forwarded IP headers remain untrusted, matching existing login limits.

## Verification

`backend/tests/test_us01_password_reset.py` checks both methods/roles, strength,
confirmation, old-password reuse, session revocation, hashed codes, expiry,
resends, limits/restarts, SMTP failures, code-purpose isolation, replay and atomic
rollback. Frontend tests check validation, staged email verification and pending
requests. `frontend/tests/us01-reset-live.mjs` drives both paths through the actual
React login screen and Flask/SQLite, then signs in with the new passwords.

Verified on 2026-10-10: **284 backend tests passed**, including all seven real
HTTP frontend workflows; the optional Docker runtime test was skipped.
All **113 frontend tests**, the production build and the formatting check passed.
All 56 OpenAPI schemas, 40 example fixtures and 29 endpoint mappings validated.
Email delivery uses the tested SMTP transport; no live provider email was sent.

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_us01_password_reset.py -q
.\.venv\Scripts\python.exe -m pytest backend/tests -q --require-frontend
```
