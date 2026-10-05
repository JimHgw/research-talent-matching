# Backend Developer README — User Registration and Authentication (auth.py)

Last updated: 2026-10-05  
Project: H18ABANANA / Python Backend  
Document status: Development requirements and API design; this document does not indicate that the features have been implemented.

This task requires the routes and business logic for **email registration, account initialisation, basic information entry, user ID generation, session token issuance and validation, user lookup by ID/token, login, and logout** to be consolidated in `auth.py`. The application entry point should only mount the routes. Database connections and migrations may use shared project infrastructure. User data must be persisted rather than stored only in a Python global dictionary.

## 1. Relationship to the Existing API Contract

Refer to `docs/api/sprint-1-api-contract.md`, version `0.1.0-draft`, in the project. It already defines login, session, logout, profile, and privacy endpoints, but its original scope uses provisioned accounts and does not define complete registration.

**This README follows the latest requirement: register a general account first, then participate in the relevant activities as needed.** Users do not choose between being talent and an opportunity publisher during registration. The same account can create a personal profile, upload a CV, and publish research opportunities. Both activities can take place concurrently, without switching roles or registering again.

This changes the previous assumptions about mutually exclusive `TALENT / RESEARCH_TEAM` roles, automatic profile creation during account setup, and one account representing one team. Existing endpoint paths should be retained where possible, while User responses, profile initialisation timing, and permission semantics must follow this document. Update the API contract, OpenAPI definition, frontend mocks, and tests together during implementation. This document describes development requirements, not completed functionality.

Authentication continues to use the existing contract's **HttpOnly cookies and server-side sessions**. “Automatically issuing a token” means that the backend generates a login credential and delivers it to the browser through `Set-Cookie`. The login token is not exposed in response JSON. Do not introduce a separate Bearer/JWT scheme that would leave the frontend and backend using different authentication protocols.

Successful registration creates only a User and a login Session, automatically assigning a user ID and token. It does not create a TalentProfile, talent privacy settings, a CV, a research team, or an opportunity. `User` no longer contains a business identity field named `role`, and registration does not require `roles`. Talent and publisher describe how users participate in the application; permissions depend on the authenticated account, resource ownership, and business conditions.

## 2. Responsibilities of auth.py

| Feature | Required behaviour |
|---|---|
| Email registration | Validate the email, password, and display name; prevent duplicate emails; create the account and log the user in automatically |
| Account initialisation | Generate a user ID automatically; create only the general account and login session |
| Talent profile after registration | Generate a talent ID and default privacy settings only when the user explicitly creates a personal profile; profile entry and CV upload follow |
| Basic information | Collect only email, password, and account display name during registration; collect detailed talent information separately after profile creation |
| ID lookup | Provide an internal backend function to retrieve an account by user ID |
| Token lookup | Validate the session token, locate the account, and check session expiry and account status |
| Login | Validate email and password; rotate the session token and CSRF token; allow the same session to access both talent and opportunity publishing features |
| Session retrieval | Return the current user and CSRF token; return user=null for anonymous sessions |
| Logout | Revoke the current server-side session and clear the browser cookie |
| Permissions | Centralise authentication, resource ownership, CSRF, and Origin checks without mutually exclusive talent/publisher checks |
| Profile confirmation and privacy | Implement the existing endpoints involved in the post-registration profile workflow |

Account, authentication, talent profile creation, and profile-related logic belong in `auth.py`. Opportunity management, matching algorithms, file uploads, and extraction belong in their respective business modules, which call the authentication and ownership validation functions provided by `auth.py`. The shared tag endpoint continues to follow the original contract. Profile validation must use the same tag data.

## 3. Distinguishing IDs, Login Tokens, and CSRF Tokens

| Name | Purpose | Generation and delivery |
|---|---|---|
| `user.id` | Permanent account identifier; internal function parameters may use `user_id` | Generated by the backend and may be returned in responses to the current user |
| `talentId` | Identifier of a talent profile explicitly created after registration, linked to the account by a foreign key | Generated by the backend only when the profile is created; accounts without a profile have no talent ID |
| session token | Establishes that a request belongs to a valid authenticated session | Generated by the backend and delivered only in the `h18_session` HttpOnly cookie |
| `csrfToken` | Protects state-changing requests against forgery from other sites | Returned by session retrieval, registration, and login responses; sent by the frontend in `X-CSRF-Token` |

**An ID identifies a resource and cannot authenticate a user on its own. A CSRF token cannot replace a login token either.** A session token is a credential that can expire, rotate, or be revoked; it is not a permanent account field. One account may have multiple independent sessions.

Business IDs may use a `user_` or `talent_` prefix followed by a UUID4 hexadecimal string, satisfying the original contract's `^[A-Za-z0-9_-]{1,64}$` pattern. Enforce primary-key or unique constraints in the database and regenerate an ID if a collision occurs.

Generate the login token and CSRF token separately using `secrets.token_urlsafe(32)`. Do not construct them from user IDs, emails, timestamps, or the ordinary `random` module. See the [Python secrets documentation](https://docs.python.org/3/library/secrets.html).

## 4. Persistence Requirements

The following is a logical data model. It does not prescribe a particular ORM or database.

| Data | Main internal fields | Constraints |
|---|---|---|
| User | `id`, `email`, `email_normalized`, `password_hash`, `display_name`, `is_active`, `created_at`, `updated_at` | Unique `email_normalized`; no mutually exclusive business role |
| Session | `token_hash`, `user_id`, `csrf_token`, `created_at`, `expires_at`, `revoked_at` | Unique token digest; user_id=null for anonymous sessions; supports expiry and revocation checks |
| TalentProfile | `talent_id`, `user_id`, `revision`, `content`, `confirmation`, `origins`, `updated_at` | Unique user_id; each general account may have zero or one talent profile |
| PrivacySettings | `user_id`, `revision`, `discoverable`, `visible_fields`, `updated_at` | Created together with the talent profile; initially discoverable=false and visible_fields=[] |
| Opportunity (another business module) | `id`, `owner_user_id`, and the original opportunity fields | An account may own zero or more opportunities; owner_user_id comes from the authenticated account |

- Use a maintained password hashing library to generate salted Argon2id hashes. Do not implement password cryptography yourself or store passwords using a single SHA-256 hash. See [OWASP Password Storage](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html).
- A SHA-256 digest may be used as the lookup key for a high-entropy session token. Compute the digest from the received cookie before querying. Do not store or log the raw session token. This has a different purpose from password hashing.
- Retain the CSRF token in session storage so that `GET /auth/session` can return the current value. Do not write it to logs.
- The registration transaction creates only the User and new login Session and revokes the previous anonymous session. Roll back the whole transaction on failure. An account without a talent profile or opportunity is a valid state.
- When the user explicitly creates a profile, a separate transaction atomically creates the TalentProfile and PrivacySettings. Failure does not affect the registered account or login session. Opportunity creation uses its own business transaction and does not require a talent profile.
- Use foreign keys to maintain referential integrity. The database or shared session store must support multiple server processes, and saved accounts must remain readable after a server restart.

## 5. HTTP Endpoint Overview

All endpoints in the following table are registered in `auth.py` and use the `/api/v1` prefix.

| Method | Path | Permission | Successful result | Status |
|---|---|---|---|---|
| GET | `/api/v1/auth/session` | Anonymous or authenticated | 200 Session | Existing |
| POST | `/api/v1/auth/register` | Anonymous | 201 Session + login cookie | New |
| POST | `/api/v1/auth/login` | Anonymous | 200 Session + login cookie | Existing |
| POST | `/api/v1/auth/logout` | Authenticated | 204, no response body | Existing |
| POST | `/api/v1/me/profile` | Authenticated, with no existing talent profile | 201 Profile | New |
| GET | `/api/v1/me/profile` | Authenticated, reading own profile | 200 Profile; 404 if not yet created | Existing path, revised semantics |
| PUT | `/api/v1/me/profile` | Authenticated owner of an existing profile | 200 Profile | Existing path, revised permissions |
| POST | `/api/v1/me/profile/confirmation` | Authenticated owner of an existing profile | 200 Profile | Existing path, revised permissions |
| GET | `/api/v1/me/privacy` | Authenticated owner of an existing profile | 200 PrivacySettings | Existing path, revised permissions |
| PUT | `/api/v1/me/privacy` | Authenticated owner of an existing profile | 200 PrivacySettings | Existing path, revised permissions |

Use `GET /auth/session` to retrieve the current user through the session token. ID lookup is an internal backend capability. Do not add anonymous `/users/{id}` or `/users?token=...` endpoints.

### 5.1 Email Registration

`POST /api/v1/auth/register`

First call `GET /auth/session` to establish an anonymous session. Include its cookie and `X-CSRF-Token` in the registration request. If the caller is already authenticated, return `409 ALREADY_AUTHENTICATED`; the user must log out before creating another account.

Example request:

```json
{
  "email": "alice@example.test",
  "password": "Example-Only-Passphrase-2026!",
  "displayName": "Alice"
}
```

Validation rules introduced in this iteration:

| Field | Rule |
|---|---|
| email | Required string; trim leading and trailing whitespace, validate email format, and allow at most 254 characters |
| password | Required string; 15–200 characters for registration; preserve case and whitespace, without trimming or truncation |
| displayName | Required string; 1–100 characters after trimming leading and trailing whitespace |

This project trims and lowercases email addresses to produce the unique matching key. Registration and login must use the same rule. Do not remove dots or `+suffix` components from email addresses. This is the project's account matching policy, not a claim that all email providers interpret addresses identically.

Reject unknown fields, especially client-supplied `id`, `userId`, `talentId`, `role`, `roles`, `token`, `passwordHash`, and confirmation state. The registration form does not collect a business identity, detailed talent information, a CV, or opportunity information. Return `409 EMAIL_ALREADY_REGISTERED` for a duplicate email. Handle concurrency through a database unique constraint, not only a query followed by an insert. This response reveals that an email is registered; this iteration adopts that user-facing behaviour alongside registration rate limiting.

Successful backend processing sequence:

1. Validate JSON, the anonymous session, CSRF, Origin, and rate limits.
2. Normalise the email, validate the fields, and compute the password hash.
3. Generate a new user ID, login token, and CSRF token. Do not generate a talent ID or opportunity ID.
4. In one transaction, create only the general account and new session, and revoke the previous anonymous session.
5. Set the cookie and return 201 after the transaction commits. Do not return a valid login credential if the transaction rolls back.

Example response (placeholder values must not be used for real authentication):

```json
{
  "user": {
    "id": "user_demo_001",
    "displayName": "Alice",
    "email": "alice@example.test"
  },
  "csrfToken": "example-only-new-csrf-token"
}
```

```http
Set-Cookie: h18_session=<generated-session-token>; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=86400
Cache-Control: no-store
```

This iteration uses email and password registration without verification codes or activation emails. Successful registration does not mean that email ownership has been verified. Phone numbers, avatars, email changes, password resets, third-party login, and multi-member team management are outside this task. An ordinary authenticated user can proceed directly to creating a research opportunity, without registering a separate publisher account or waiting for the server to assign a RESEARCH_TEAM identity.

### 5.2 Create a Talent Profile After Registration, Then Enter Details or Upload a CV

The account's `User.displayName` comes from the registration form. Completing registration does not require the user to create a profile or publish an opportunity immediately. Users may enter either workflow later or participate in both at the same time.

When the user explicitly selects “Create my talent profile”, call the new `POST /api/v1/me/profile` endpoint with `{}` as the request body. Include the login cookie and CSRF token, and validate Origin. The server obtains user.id from the current session, generates a talent ID, creates an empty TalentProfile and default PrivacySettings in one transaction, and returns **201 Profile**. Do not accept client-supplied userId, talentId, or confirmation state.

Only one profile may exist per user_id. Duplicate or concurrent creation returns `409 PROFILE_ALREADY_EXISTS`, after which the frontend retrieves the existing profile with GET. Before a profile exists, `GET /me/profile` returns `404 NOT_FOUND` and does not create one. PUT, confirmation, privacy, and document endpoints return `409 PROFILE_REQUIRED`, prompting the user to create a profile first. A failed profile creation does not revoke the login session or affect the user's research opportunities.

A new profile starts with `revision=0`, `content.displayName=""`, `disciplineGroup=null`, and empty arrays. The frontend may prefill the profile form with the account display name; it is written to the profile when the user saves. Creating or editing a talent profile does not assign an exclusive role, change the user ID, or require another login.

Example 201 response for talent profile creation (not the registration response):

```json
{
  "talentId": "talent_demo_001",
  "revision": 0,
  "content": {
    "displayName": "",
    "disciplineGroup": null,
    "education": [],
    "courses": [],
    "researchExperience": [],
    "skills": [],
    "researchInterests": [],
    "researchOutputs": []
  },
  "confirmation": {
    "status": "UNCONFIRMED",
    "confirmedRevision": null,
    "confirmedAt": null
  },
  "origins": [],
  "updatedAt": "2026-10-05T00:00:00Z"
}
```

The frontend saves profile details through `PUT /api/v1/me/profile`. Include the current session cookie, `X-CSRF-Token`, and the complete request body below:

```json
{
  "expectedRevision": 0,
  "content": {
    "displayName": "Alice",
    "disciplineGroup": "STEM",
    "education": [
      {
        "id": "edu_demo_001",
        "institution": "UNSW",
        "qualification": "Master of IT",
        "discipline": "Computer Science",
        "startYear": 2025,
        "endYear": null
      }
    ],
    "courses": [],
    "researchExperience": [],
    "skills": [],
    "researchInterests": [],
    "researchOutputs": []
  }
}
```

Field and processing rules:

- All eight fields in `content` are required. PUT replaces the complete content. `[]` clears the corresponding section; omitted fields must not mean “leave unchanged”.
- `displayName` allows at most 100 characters. An empty string is allowed when saving a draft. `disciplineGroup` must be `STEM`, `BUSINESS`, or `null`.
- Each array allows at most 100 items. Validate the child fields of education, courses, experience, and outputs against section 6 of the original contract. Preserve child record IDs when editing; the frontend may generate them for new records. They are not account IDs.
- `skills` uses the `tagId` of a valid SKILL tag; `researchInterests` uses valid INTEREST tag IDs. Reject duplicates and tags of the wrong type.
- Compare `expectedRevision` and perform the update within the same transaction. Increment revision by one when content actually changes. A save with no changes preserves revision. A stale revision returns 409.
- When content changes, reset the state to `UNCONFIRMED` and set both `confirmedRevision` and `confirmedAt` to null. For manually edited academic sections, update the origin to `MANUAL` with documentId=null.
- New consistency rule for this iteration: saving a non-empty profile display name also updates the account display name. If the profile name is cleared, preserve the previous account name so that User.displayName remains non-empty in Session responses. Perform this update in the same transaction as the profile save.
- Return the complete Profile on success: `talentId`, `revision`, `content`, `confirmation`, `origins`, and `updatedAt`. Do not include email or password in ProfileContent.
- Account existence, authentication, and the ability to create research opportunities do not depend on whether a talent profile exists, is complete, or is confirmed.

After creating a profile, the user may enter details manually or upload a CV through the existing `POST /me/documents` endpoint using multipart/form-data. Its fields and file restrictions follow the original contract. Uploading, checking processing status, reviewing extraction results, and importing user-reviewed content are optional post-registration activities. Uploading does not automatically confirm the talent profile. Users can create and complete their profiles manually without uploading a CV. The document module must verify that the current account owns the profile and the relevant document.

### 5.3 Profile Confirmation and Privacy

`POST /me/profile/confirmation` accepts `{"expectedRevision":1}`. The current profile must have a non-empty display name and at least one non-empty array among the six academic/research sections. On success, set the status to `CONFIRMED` and confirmedRevision=revision without increasing the content revision. Reconfirming the same revision preserves the original confirmation time. Profile confirmation is not email verification or verification of academic credentials.

`GET /me/privacy` returns `revision`, `discoverable`, `visibleFields`, and `updatedAt`. Privacy settings are initialised when the talent profile is created, with revision=0, discoverable=false, and visibleFields=[]. They are not created during registration. `PUT /me/privacy` accepts `expectedRevision`, `discoverable`, and `visibleFields`, applies an independent revision check, and returns the complete updated PrivacySettings.

`visibleFields` accepts only the eight ProfileContent fields. Reject duplicates, email fields, and file-related fields. Privacy changes do not reset profile confirmation. Changes to discovery permissions or profile data must notify the matching module to invalidate relevant caches. Opportunity publishers continue to retrieve candidate information through the existing matching endpoints and visible-field allowlist. They must not bypass privacy rules by using internal ID lookup functions to return complete profiles.

### 5.4 Login, Session Retrieval, and Logout

- `POST /auth/login` accepts `email` and `password`; obtain an anonymous CSRF token first. Login continues to accept passwords of 1–200 characters as specified in the original contract, so the new registration minimum does not prevent existing provisioned accounts from logging in.
- Unknown emails, incorrect passwords, and disabled accounts all return `401 INVALID_CREDENTIALS`, without revealing which condition failed. For an unknown email, perform equivalent password verification work through the library to avoid obvious timing differences.
- Successful login generates a new session token and CSRF token and revokes the current old session. The user ID does not change. Return 200 Session and set the new cookie.
- With a valid cookie, `GET /auth/session` returns the current User and the session's csrfToken. Without a valid authenticated session, return `{"user":null,"csrfToken":"<new-anonymous-csrf>"}`, establish or update an anonymous session, and use status 200.
- Private business endpoints return 401 for missing, unknown, expired, or revoked tokens, or for disabled accounts. They must not return an anonymous 200 response as the session retrieval endpoint does.
- `POST /auth/logout` validates the session, CSRF, and Origin, revokes the current session, and returns 204. Clear the cookie using the same Path, no Domain, and Max-Age=0. Sessions on other devices remain unaffected.

### 5.5 Publish Research Opportunities After Registration, Alongside the Talent Workflow

Any account with a valid authenticated session may enter the opportunity creation workflow. There is no prerequisite to create a talent profile, upload a CV, confirm talent information, or apply for a publisher role. The opportunity module implements these endpoints; `auth.py` provides current-user authentication and ownership checks.

| Operation | Permissions and behaviour |
|---|---|
| `POST /opportunities` | Any authenticated user may create their own draft; the server sets owner_user_id=current_user.id; request fields follow the original contract |
| `PUT /opportunities/{opportunityId}` | Only the opportunity owner may edit it; return 404 for other accounts |
| `POST /opportunities/{opportunityId}/publish` | Only the owner may publish; continue to validate expectedRevision, required information, and the original publication conditions |
| `GET /opportunities?scope=mine` | Return opportunities created by the current user ID |
| `GET /opportunities/{opportunityId}/talent-matches` and its detail endpoint | Verify that the current user owns the published opportunity, then return candidate data subject to confirmation status, discovery consent, and field visibility |

If opportunity responses retain the original `ownerId` field, its value becomes the opportunity owner's user.id. Update the field definition accordingly. Clients cannot specify or modify ownerId/owner_user_id. A user must not be prevented from publishing opportunities because they have a talent profile. Likewise, a user must not be prevented from creating a profile, uploading a CV, or viewing their own recommendations because they have published opportunities. Access to other users' information remains subject to resource permissions.

The frontend may provide “My profile” and “My research opportunities” entry points. Switching pages changes only the current view; it does not change a role, token, user ID, or existing business data.

## 6. Session Token Lifecycle

Defaults for this iteration: authenticated sessions have an absolute lifetime of 24 hours, and anonymous sessions last 1 hour. Manage these durations through configuration. Reads and ordinary requests do not automatically extend the lifetime; the user logs in again after expiry. This iteration has no refresh token endpoint.

Set `HttpOnly; SameSite=Lax; Path=/` on the cookie and omit Domain. Set Secure under HTTPS; it may be omitted only for local HTTP development. Browser Max-Age must match the corresponding server-side lifetime. The server's time and revocation records ultimately determine validity.

All state-changing requests, including registration, login, logout, PUT, and confirmation, must validate both `X-CSRF-Token` and the allowed Origin. Bind the CSRF token to the current session and compare it in constant time. A CSRF token alone does not authenticate the caller. After successful registration or login, the frontend must replace its old CSRF token immediately.

Frontend requests use `credentials: 'include'`. Login tokens must not appear in localStorage, response JSON, URLs, or logs. Responses containing personal information use `Cache-Control: no-store`. If the database or session store is unavailable, return the standard service error rather than bypassing authentication.

## 7. User Lookup by ID or Token

Define these functions in `auth.py` for reuse by this module and other backend modules. The following are proposed responsibilities and signatures, not implemented code:

```python
# Registration, validation, and credentials
normalize_email(email: str) -> str
hash_password(password: str) -> str
verify_password(password: str, password_hash: str) -> bool
register_user(payload, request) -> SessionResponse
login_user(payload, request) -> SessionResponse
logout_user(request) -> None
create_session(user_id: str | None) -> IssuedSession
revoke_session(raw_token: str) -> None

# Internal lookup and authentication
get_user_by_id(user_id: str) -> UserRecord | None
get_user_by_email(email: str) -> UserRecord | None
get_user_by_token(raw_token: str) -> UserRecord
get_current_user(request) -> UserRecord
require_profile(user: UserRecord) -> ProfileRecord
require_owner(user: UserRecord, owner_user_id: str) -> None
serialize_user(user: UserRecord) -> dict

# Routes and profile workflows
get_session(request) -> SessionResponse
create_my_profile(request, payload) -> ProfileResponse
get_my_profile(request) -> ProfileResponse
update_my_profile(request, payload) -> ProfileResponse
confirm_my_profile(request, payload) -> ProfileResponse
get_my_privacy(request) -> PrivacyResponse
update_my_privacy(request, payload) -> PrivacyResponse
```

`get_user_by_id` locates an account by its primary key and returns None if it is not found. It does not itself grant the caller permission to view that account. `get_user_by_email` normalises the email first and is primarily used for registration and password verification. These internal functions may read database records, but those records must not be serialised directly into HTTP responses.

`get_user_by_token` must perform the following sequence:

```text
Obtain the raw token
→ Validate its type, non-empty value, and reasonable length
→ Compute the token digest and query Session
→ Check that it has not expired or been revoked, and that user_id is non-null
→ Query the account using session.user_id
→ Check that the account exists and is_active=true
→ Return the trusted internal user record
```

If any step fails the authentication requirements, raise the standard authentication error. `get_current_user` reads the token only from the `h18_session` cookie and calls this function. It must not infer identity from a URL, a userId in the request body, or a CSRF token.

Profile endpoints use the authenticated user.id to retrieve the user's own profile. If an endpoint that accepts a user ID in the URL is added later, it must check access permissions before returning data. This task does not introduce an administrator role or allow anyone to view another account merely by knowing its ID.

`require_profile` looks up the profile associated with the current user.id and returns `409 PROFILE_REQUIRED` if it does not exist. The profile retrieval GET returns 404 instead, as specified by that endpoint. `require_owner` compares the authenticated user.id with the resource's actual owner_user_id; it must not trust ownership information in the request body. Talent profile and opportunity publishing operations no longer use mutually exclusive `require_role(TALENT/RESEARCH_TEAM)` checks.

`serialize_user` uses an allowlist to return only `id`, `displayName`, and `email` in responses to the account owner. Registration, login, and session retrieval must use the same User structure and omit the former role field. Never return password hashes, session digests, login tokens, or internal database fields.

## 8. Errors and Edge Cases

Retain the existing error structure. Successful responses return the business object directly, without an additional `data` or `success` wrapper.

```json
{
  "error": {
    "code": "EMAIL_ALREADY_REGISTERED",
    "message": "This email is already registered. Please log in.",
    "fieldErrors": [
      { "field": "email", "message": "This email is already registered." }
    ]
  },
  "requestId": "req_demo_001"
}
```

| HTTP | error.code | Condition |
|---|---|---|
| 400 | BAD_REQUEST | JSON parsing failed |
| 401 | INVALID_CREDENTIALS | Incorrect login credentials or an account that cannot log in |
| 401 | UNAUTHENTICATED | A private endpoint lacks a valid authenticated session |
| 403 | CSRF_INVALID | CSRF or Origin validation failed |
| 403 | FORBIDDEN | Another explicit business permission is not satisfied; participation in the other workflow alone must not cause rejection |
| 404 | NOT_FOUND | The target resource does not exist or is inaccessible |
| 409 | EMAIL_ALREADY_REGISTERED | New: email uniqueness constraint conflict |
| 409 | ALREADY_AUTHENTICATED | New: registration attempted while logged in |
| 409 | PROFILE_ALREADY_EXISTS | New: duplicate or concurrent creation of the user's talent profile |
| 409 | PROFILE_REQUIRED | New: saving, confirming, accessing privacy or documents, or requesting talent recommendations before creating a talent profile |
| 409 | REVISION_CONFLICT | Profile or privacy revision conflict; include currentRevision |
| 415 | UNSUPPORTED_MEDIA_TYPE | Unsupported request media type |
| 422 | VALIDATION_ERROR | Invalid fields, unknown fields, or unmet confirmation requirements |
| 429 | RATE_LIMITED | Registration or login rate limit exceeded |
| 500 | INTERNAL_ERROR | Internal processing or storage failure |

Add the four new 409 error codes to the contract and OpenAPI enum. Use fieldErrors=[] when there are no field errors. Include currentRevision only for revision conflicts. Do not return stack traces, SQL, passwords, or tokens. Registration and login rate limiting must cover at least the source IP and normalised email; manage the thresholds through configuration.

## 9. Frontend and Backend Integration Sequence

```text
GET /auth/session                       Establish an anonymous session and obtain csrfToken
POST /auth/register                     Register by email; generate an ID and login session
                                        Browser receives the cookie; frontend updates csrfToken
GET /auth/session                       Read the current user using the cookie
                                        Registration is complete; no business identity selection

Optional workflow A: Create research opportunities (no talent profile required)
POST /opportunities                     Create an opportunity draft owned by the current user
PUT /opportunities/{id}                 Edit the user's own opportunity
POST /opportunities/{id}/publish        Publish after meeting the publication conditions

Optional workflow B: Create a personal profile (no prior opportunity publication required)
POST /me/profile                        Explicitly create profile and privacy settings; revision=0
GET /tags + GET /me/profile             Retrieve tags and the user's own profile
PUT /me/profile                         Enter and save profile details manually
POST /me/documents                      Optional: upload a CV and review extraction results
POST /me/documents/{id}/apply           Optional: import selected content after user review
POST /me/profile/confirmation           Confirm the latest revision after user review
PUT /me/privacy                         Let the user choose discovery consent and visible fields

Choose either or both workflows, concurrently or sequentially, using the same account and session
POST /auth/logout                       Revoke the current session and clear frontend personal-data caches
GET /auth/session → POST /auth/login    Obtain anonymous CSRF, then log in again with the existing account
```

Do not automatically repeat a registration or login POST after a timeout. Query the current session first to determine whether the operation succeeded. Clear frontend profile, document, and recommendation caches on login, logout, and account changes. After CSRF validation fails, retrieve the session again and let the user retry the state-changing operation.

## 10. Backend Acceptance Checklist

- [ ] Registering a new email returns 201 and creates only User and Session; no talent ID, talent profile, privacy settings, CV, or opportunity is created.
- [ ] Registration does not require choosing talent or publisher; registration, login, and session responses no longer contain a mutually exclusive role.
- [ ] Successful responses issue an HttpOnly cookie; JSON contains no login token; only password hashes are stored.
- [ ] Email case and leading/trailing whitespace follow one normalisation rule; only one concurrent registration for the same email succeeds.
- [ ] Invalid emails, short passwords, empty names, unknown fields, and client-supplied role/id values are rejected.
- [ ] Registration initialisation is transactional; a simulated database failure leaves no account or valid session behind.
- [ ] GET returns 404 when no profile exists after registration and does not create one automatically; profile-dependent operations return PROFILE_REQUIRED.
- [ ] A talent ID is generated only after explicit profile creation, with revision=0, UNCONFIRMED status, and privacy settings that disable discovery by default.
- [ ] Only one concurrent profile creation succeeds; others return PROFILE_ALREADY_EXISTS. Failure rolls back the profile and privacy settings without affecting the existing account.
- [ ] An authenticated user without a talent profile, CV, or profile confirmation can still create and publish research opportunities that satisfy publication requirements.
- [ ] A user who has published opportunities can create a talent profile and upload a CV; a user with a profile can publish opportunities without registering again or switching roles.
- [ ] ID lookup locates the correct account, but knowing an ID alone cannot bypass authentication to read profile information.
- [ ] A valid token locates the correct user; invalid, expired, revoked, or disabled-account tokens are rejected.
- [ ] A CSRF token alone cannot access private endpoints; state-changing requests with missing CSRF or an invalid Origin fail.
- [ ] Login and registration rotate tokens and invalidate the previous session; logging in again preserves the account's user ID.
- [ ] Profile data persists across restarts; saving unchanged content preserves revision; a concurrent stale save returns 409.
- [ ] Profile changes require reconfirmation; privacy changes do not reset confirmation; display-name synchronisation behaves consistently on repeated verification.
- [ ] The same account can manage its own profile and opportunities; different accounts cannot modify each other's profiles, documents, or opportunities.
- [ ] Publishers' access to candidate data still respects confirmation, discovery consent, and field visibility; participation in both workflows does not expand read permissions.
- [ ] Logout returns 204 with no response body; replaying the previous token fails; sessions on other devices remain valid.
- [ ] An unauthenticated GET /auth/session returns 200 with user=null; private endpoints return 401.
- [ ] Registration and login rate limiting returns 429, and error responses always follow the standard structure.
- [ ] Endpoints retain camelCase and UTC RFC3339 timestamps; remove the old mutually exclusive business-role checks and authorise by account and resource ownership.
- [ ] The API contract, OpenAPI definition, frontend request examples, and mocks reflect registration, separate profile creation, the User structure, ownerId semantics, and the new error codes.

## 11. Updates to the Previous Contract and Existing Data

- Remove `User.role` from the public User structure. Update registration, login, session retrieval, and frontend route guards together, not only the registration response.
- Replace the former `Talent owner` permission with “the current account owns the relevant talent profile” and `Team owner` with “the current account owns the relevant research opportunity”. Update document, recommendation, and matching modules as well; do not leave exclusive TALENT/RESEARCH_TEAM checks in place.
- Replace automatic profile provisioning for every account with explicit POST creation by the user. Distinguish an absent profile from an empty profile. GET must not create data.
- Preserve existing user IDs, passwords, saved profiles, and opportunities. Associate previous opportunity owners with their actual account user IDs and validate the mapping before migration. Do not infer ownership from display names.
- Existing provisioned team accounts may also create personal profiles, and existing individual accounts may publish opportunities. Multi-member team collaboration and membership management are separate features outside this change.
- This iteration updates only this README. The contract, code, database, and frontend changes described above remain implementation tasks.

The acceptance checklist defines completion criteria for development. It is not a record of tests already executed or passed as part of this README.
