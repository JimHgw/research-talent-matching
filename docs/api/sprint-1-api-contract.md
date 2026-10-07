# H18ABANANA — Sprint 1 Frontend and Backend API Contract

Version: `0.1.0-draft`

Prepared: 2026-10-03. English edition: 2026-10-05.

Frontend language: JavaScript. Backend language: Python.

Scope: **US-01 through US-09 in the current Sprint 1, comprising 24 HTTP operations**. This draft supports team review and parallel development. It does not mean that the backend has been implemented or that every design choice has been approved by the team.

This document can be shared on its own: it contains endpoints, field definitions, request and response examples, permissions, errors and integration requirements. The accompanying `openapi.json` provides the machine-readable definition of the same version.

## 1. Scope and collaboration

### 1.1 Coverage

| User story | Jira parent issue | API coverage in this version |
|---|---|---|
| US-01 Login and talent profile | H18ABANANA-9 | Session, login, logout, profile retrieval and storage, shared tags |
| US-02 Research opportunity management | H18ABANANA-10 | Create drafts, edit, publish, list and view details |
| US-03 Review and confirmation | H18ABANANA-11 | Confirm the current profile revision; reconfirm after changes |
| US-04 Talent discovers opportunities | H18ABANANA-13 | Ranked recommendations and requirement-level explanations |
| US-05 Teams discover talent | H18ABANANA-12 | Ranked talent for an opportunity and requirement-level explanations |
| US-06 Sprint flow testing | H18ABANANA-14 | Test these APIs using synthetic examples; no additional public test endpoint |
| US-07 Privacy and field visibility | H18ABANANA-15 | Discovery consent and a whitelist of visible profile fields |
| US-08 Requirement-level evidence | H18ABANANA-1 | Matched / Partial / Gap / Unknown, evidence, ranking and scores |
| US-09 Document upload and extraction | H18ABANANA-2 | PDF/DOCX upload, processing status, extraction drafts and reviewed imports |

“All endpoints” here means all endpoints for **Sprint 1**. Backlog features such as favourites, advanced filters, semantic matching, full registration/password reset and complex role switching are outside v0.1. Opportunity deletion, unpublishing and team membership management are also not defined in this version.

The client meeting on 2026-09-30 allowed manual entry for Demo 1 if extraction was not ready. US-09 is now in the Jira Sprint, so its complete interface is retained here. Manual entry must remain available when extraction is unavailable.

### 1.2 Parallel development responsibilities

| Frontend module | Main endpoints | Python backend responsibility |
|---|---|---|
| FE-1 Layout and login | 01–03 | Authentication, sessions and role checks |
| FE-2 Talent profile, review and privacy | 04–09, 14 | Persistence, validation, revision conflicts, confirmation and privacy rules |
| FE-3 Opportunity creation and management | 04, 16–20 | Ownership, editing and publishing |
| FE-4 Bidirectional matching and explanations | 21–24 | Ranking, statuses, evidence and filtering team-visible data |
| FE-5 Upload and extraction review | 10–15, followed by 05–07 | Private file storage, extraction and importing profile sections |

The frontend can use mock responses while the backend is developed, then switch the API address and request adapter for integration. **The Python backend is authoritative for permissions, confirmation, evidence selection, ranking and scores.** The frontend displays its results. A mock implementation does not replace server-side access controls.

### 1.3 Proposed defaults for team review

These choices make the draft explicit so the two implementations do not make incompatible assumptions. The team should agree on them before locking the version; they are not presented as technical requirements already approved in Jira.

| Topic | Proposed v0.1 default |
|---|---|
| API style | REST + JSON with the `/api/v1` prefix |
| Login | Provisioned accounts, cookie sessions and server-assigned roles |
| Team model | One `RESEARCH_TEAM` account represents one research team |
| Confirmation granularity | Confirm the entire current profile revision; content changes require reconfirmation |
| Upload | PDF and DOCX, at most 10 MiB per file; legacy `.doc` is not accepted |
| Prototype discipline scope | STEM and BUSINESS, following the latest client meeting allocation |
| Matching baseline | Structured skill and interest tags, without requiring embeddings |
| Scores | Required weight 2, preferred weight 1; Matched=1, Partial=0.5, other statuses=0 |
| Editing published opportunities | Changes affect subsequent matching immediately; publication status is preserved |

## 2. Shared conventions

### 2.1 Addresses, data and naming

- Paths are relative to `/api/v1`. For example, `GET /me/profile` uses `/api/v1/me/profile`.
- Requests and responses use UTF-8. Normal bodies use `application/json`; uploads use `multipart/form-data`; original file downloads are binary.
- JSON fields use `camelCase`, such as `researchInterests`. Internal Python names may differ, but the external names must remain consistent.
- Enum spelling and case are fixed, including `TALENT`, `RESEARCH_TEAM` and `CONFIRMED`.
- Timestamps are UTC RFC3339 strings, such as `2026-10-03T00:00:00Z`. The frontend converts these for local display.
- IDs are opaque strings of 1–64 ASCII letters, digits, underscores or hyphens. The frontend must not infer business meaning from their structure.
- Required fields must be present. Allowing `null` is different from allowing omission. An empty array `[]` means no records or an explicit request to clear a section.
- Objects accept only the documented fields. Reject unknown fields, duplicate record IDs, duplicate skill tag IDs and incorrectly typed tags with 422.
- Text is plain text by default. The frontend must render it as text rather than inserting it as HTML.
- Successful responses return the business object directly, without an extra `data` or `success` wrapper. A 204 response has no body.

### 2.2 Sessions, permissions and headers

`h18_session` is an opaque server-side session cookie with `HttpOnly; SameSite=Lax; Path=/` and no Domain attribute. Add `Secure` on HTTPS; local HTTP development may omit it. JavaScript does not read its value, and response JSON never contains the session ID.

Session flow:

1. On startup, call `GET /auth/session`. Anonymous users receive 200 with `user: null`; the server initialises an anonymous session and returns `csrfToken`.
2. Include `X-CSRF-Token` when logging in. Successful login rotates the session and CSRF token.
3. Use the new token returned by login. Every POST/PUT request, including upload and logout, must include it.
4. The backend validates both CSRF and the allowed Origin. Role comes from the account, not a client-supplied role field.
5. Logout invalidates the server session and expires the cookie. The frontend clears account and personal-data caches and reads the session again before the next login.

```http
Accept: application/json
Content-Type: application/json
X-CSRF-Token: <csrfToken returned by session; required for mutations>
```

Use same-origin requests: the JavaScript frontend requests `/api/v1`, and a development proxy forwards to Python, for example `http://127.0.0.1:8000`. The proxy preserves the browser Origin, which the Python service explicitly allows. Cookie requests use `credentials: 'include'`. Do not manually set Content-Type for FormData; the browser supplies its boundary.

Permission labels:

| Label | Meaning |
|---|---|
| Anonymous | No login required; used only for session retrieval and login |
| Signed-in | Either TALENT or RESEARCH_TEAM |
| Talent owner | TALENT; the backend identifies the current talent from the session, not the request body |
| Team owner | RESEARCH_TEAM; may operate only on opportunities owned by that team |

Missing/expired authentication returns 401. An incorrect role returns 403. A missing or inaccessible resource returns 404. Login errors must not reveal whether an account exists. Personalised responses use `Cache-Control: no-store`.

### 2.3 Pagination, sorting and empty results

List parameters are `page` (default 1, minimum 1) and `pageSize` (default 20, range 1–100). Non-integers or out-of-range values return 422 rather than being silently corrected. No results, or a page beyond the last page, returns 200 with `items: []`.

```json
{ "items": [], "page": 1, "pageSize": 20, "total": 0 }
```

- `total` counts all results the caller may access, not just the current page.
- Opportunity lists sort by `updatedAt` descending, then `id` ascending. Documents sort by `createdAt` descending, then `id` ascending.
- Match lists sort by `score` descending, `unknownWeightPercent` ascending, then object ID ascending. Null scores come last.
- `rank` is the global rank before pagination, starting at 1. It does not restart on each page.
- Each request uses current data; there is no cross-request pagination snapshot. Refetch after profile, opportunity or privacy changes.
- The small shared tag vocabulary is returned without pagination.

### 2.4 Saving, revision conflicts and retries

Profiles, privacy settings and opportunities have independent `revision` counters. Send the last retrieved value as `expectedRevision` when writing; extraction imports use `expectedProfileRevision`.

The backend checks the revision and permissions and writes the changes atomically in a transaction. A stale revision returns `409 REVISION_CONFLICT` with `currentRevision`. The frontend preserves local input and asks the user to reload and compare; it must not silently overwrite newer content.

An ordinary PUT that changes nothing preserves the revision. Actual changes increment it by one. New profiles and privacy settings start at revision 0; newly created opportunities start at 1. Confirming a profile does not increment its content revision. Publishing a draft increments its opportunity revision. Importing extraction fields always increments the profile revision and requires reconfirmation, even if the values are identical.

Do not automatically retry a POST after a network timeout: the server may already have applied it. Read the resource again first; creation/upload can be checked against the latest list. v0.1 does not define Idempotency-Key and does not promise idempotent creation requests.

## 3. Endpoint overview

| No. | Method | Path (without /api/v1) | Purpose | Permission |
|---|---|---|---|---|
| [01](#api-01) | GET | `/auth/session` | Read the current session and obtain a CSRF token | Anonymous |
| [02](#api-02) | POST | `/auth/login` | Log in with a provisioned account | Anonymous |
| [03](#api-03) | POST | `/auth/logout` | Log out of the current session | Signed-in |
| [04](#api-04) | GET | `/tags` | List shared skill and interest tags | Signed-in |
| [05](#api-05) | GET | `/me/profile` | Read the current talent profile | Talent owner |
| [06](#api-06) | PUT | `/me/profile` | Save the complete talent profile | Talent owner |
| [07](#api-07) | POST | `/me/profile/confirmation` | Confirm the current profile revision | Talent owner |
| [08](#api-08) | GET | `/me/privacy` | Read discovery consent and field visibility | Talent owner |
| [09](#api-09) | PUT | `/me/privacy` | Save discovery consent and field visibility | Talent owner |
| [10](#api-10) | GET | `/me/documents` | List documents uploaded by the current talent | Talent owner |
| [11](#api-11) | POST | `/me/documents` | Upload a PDF or DOCX and start extraction | Talent owner |
| [12](#api-12) | GET | `/me/documents/{documentId}` | Read document processing status | Talent owner |
| [13](#api-13) | GET | `/me/documents/{documentId}/extraction` | Read extraction suggestions for review | Talent owner |
| [14](#api-14) | POST | `/me/documents/{documentId}/apply` | Save user-reviewed extraction fields to the profile | Talent owner |
| [15](#api-15) | GET | `/me/documents/{documentId}/file` | Download an original document owned by the current talent | Talent owner |
| [16](#api-16) | GET | `/opportunities` | List published opportunities or team-owned opportunities | Signed-in |
| [17](#api-17) | POST | `/opportunities` | Create a draft research opportunity | Team owner |
| [18](#api-18) | GET | `/opportunities/{opportunityId}` | Read research opportunity details | Signed-in |
| [19](#api-19) | PUT | `/opportunities/{opportunityId}` | Save research opportunity changes | Team owner |
| [20](#api-20) | POST | `/opportunities/{opportunityId}/publish` | Publish a research opportunity | Team owner |
| [21](#api-21) | GET | `/me/recommendations` | List ranked opportunity recommendations for the current talent | Talent owner |
| [22](#api-22) | GET | `/me/opportunity-matches/{opportunityId}` | Read requirement-level matching explanations for the current talent | Talent owner |
| [23](#api-23) | GET | `/opportunities/{opportunityId}/talent-matches` | List matching talent for a team-owned opportunity | Team owner |
| [24](#api-24) | GET | `/opportunities/{opportunityId}/talent-matches/{talentId}` | Read permitted talent information and matching explanations | Team owner |

## 4. Endpoint details

Request and response models link to the complete field definitions in section 6. The JSON examples below are parseable and contain no omitted fields or pseudo-JSON. IDs and accounts are synthetic. Examples illustrate individual operations; only the workflows in section 7 specify a sequence. Do not treat every example as part of one continuous database history.

All operations may return 500. Parameter validation can return 422. Each entry lists its declared error statuses; the shared error structure is in section 5.


<a id="api-01"></a>

### 01. Read the current session and obtain a CSRF token

`GET /api/v1/auth/session`

Permission: **Anonymous**.

An initial request may create anonymous session state. Being logged out is not an error: return user=null. The CSRF token is used by subsequent mutations; the real session ID remains only in the HttpOnly cookie.


Path/query parameters: none.

Request body: none.

Success: **200**, [Session](#model-session).

```json
{
  "user": null,
  "csrfToken": "mock-csrf-token-not-a-real-credential"
}
```


Error statuses: `500`.

Related Jira subtasks: H18ABANANA-16, H18ABANANA-18.

<a id="api-02"></a>

### 02. Log in with a provisioned account

`POST /api/v1/auth/login`

Permission: **Anonymous**.

Read the session first and include its CSRF token. The backend validates the provisioned account and rotates the session and CSRF token. The frontend replaces its old token immediately. Role is derived from the account. Invalid credentials return 401 INVALID_CREDENTIALS without identifying which credential failed.


| Parameter | Location | Required | Type / allowed values | Constraints |
|---|---|---|---|---|
| `X-CSRF-Token` | header | Yes | string | minimum length: 1 |

Request body: `application/json`, [LoginRequest](#model-loginrequest).

```json
{
  "email": "talent@example.test",
  "password": "EXAMPLE_ONLY_NOT_A_REAL_PASSWORD"
}
```


Success: **200**, [Session](#model-session).

```json
{
  "user": {
    "id": "user_demo_001",
    "displayName": "Demo Talent A",
    "email": "talent@example.test",
    "role": "TALENT"
  },
  "csrfToken": "mock-csrf-after-login"
}
```


Error statuses: `400`, `401`, `403`, `415`, `422`, `429`, `500`.

Related Jira subtasks: H18ABANANA-16, H18ABANANA-18.

<a id="api-03"></a>

### 03. Log out of the current session

`POST /api/v1/auth/logout`

Permission: **Signed-in**.

Invalidate the server session and expire the cookie. Clear frontend profile, document and recommendation caches. Return 204 without JSON.


| Parameter | Location | Required | Type / allowed values | Constraints |
|---|---|---|---|---|
| `X-CSRF-Token` | header | Yes | string | minimum length: 1 |

Request body: none.

Success: **204 No Content**, without a response body.

Error statuses: `401`, `403`, `422`, `500`.

Related Jira subtasks: H18ABANANA-16, H18ABANANA-18.

<a id="api-04"></a>

### 04. List shared skill and interest tags

`GET /api/v1/tags`

Permission: **Signed-in**.

Return the vocabulary shared by profile and opportunity forms. Without kind, return both types; SKILL or INTEREST filters the response. Submit tag IDs rather than labels as matching keys. v0.1 has no tag creation or editing endpoint.


| Parameter | Location | Required | Type / allowed values | Constraints |
|---|---|---|---|---|
| `kind` | query | No | `SKILL` / `INTEREST` | — |

Request body: none.

Success: **200**, [TagList](#model-taglist).

```json
{
  "items": [
    {
      "id": "skill_python",
      "label": "Python",
      "kind": "SKILL",
      "disciplineGroups": [
        "STEM",
        "BUSINESS"
      ]
    },
    {
      "id": "skill_sql",
      "label": "SQL",
      "kind": "SKILL",
      "disciplineGroups": [
        "STEM",
        "BUSINESS"
      ]
    },
    {
      "id": "skill_interviews",
      "label": "Research interviews",
      "kind": "SKILL",
      "disciplineGroups": [
        "STEM",
        "BUSINESS"
      ]
    },
    {
      "id": "skill_r",
      "label": "R",
      "kind": "SKILL",
      "disciplineGroups": [
        "STEM",
        "BUSINESS"
      ]
    },
    {
      "id": "interest_ml",
      "label": "Machine learning",
      "kind": "INTEREST",
      "disciplineGroups": [
        "STEM",
        "BUSINESS"
      ]
    }
  ]
}
```


Error statuses: `401`, `403`, `422`, `500`.

Related Jira subtasks: H18ABANANA-27, H18ABANANA-28.

<a id="api-05"></a>

### 05. Read the current talent profile

`GET /api/v1/me/profile`

Permission: **Talent owner**.

A profile is provisioned with each talent account. An untouched profile has revision=0, UNCONFIRMED status, empty arrays, displayName="" and disciplineGroup=null; it does not return 404. Only the owner may read it.


Path/query parameters: none.

Request body: none.

Success: **200**, [Profile](#model-profile).

```json
{
  "talentId": "talent_demo_001",
  "revision": 3,
  "content": {
    "displayName": "Demo Talent A",
    "disciplineGroup": "STEM",
    "education": [
      {
        "id": "edu_001",
        "institution": "UNSW",
        "qualification": "Master of IT",
        "discipline": "Computer Science",
        "startYear": 2025,
        "endYear": null
      }
    ],
    "courses": [],
    "researchExperience": [
      {
        "id": "exp_001",
        "title": "Sample research project",
        "organisation": "Demo lab",
        "description": "Used Python to prepare a small synthetic dataset."
      }
    ],
    "skills": [
      {
        "tagId": "skill_python",
        "claim": "HAS",
        "evidenceText": "Used Python in a user-reviewed demo project."
      },
      {
        "tagId": "skill_interviews",
        "claim": "DOES_NOT_HAVE",
        "evidenceText": "I have not conducted research interviews."
      }
    ],
    "researchInterests": [
      "interest_ml"
    ],
    "researchOutputs": []
  },
  "confirmation": {
    "status": "CONFIRMED",
    "confirmedRevision": 3,
    "confirmedAt": "2026-10-03T00:00:00Z"
  },
  "origins": [
    {
      "field": "education",
      "sourceType": "MANUAL",
      "documentId": null
    },
    {
      "field": "courses",
      "sourceType": "MANUAL",
      "documentId": null
    },
    {
      "field": "researchExperience",
      "sourceType": "MANUAL",
      "documentId": null
    },
    {
      "field": "skills",
      "sourceType": "MANUAL",
      "documentId": null
    },
    {
      "field": "researchInterests",
      "sourceType": "MANUAL",
      "documentId": null
    },
    {
      "field": "researchOutputs",
      "sourceType": "MANUAL",
      "documentId": null
    }
  ],
  "updatedAt": "2026-10-03T00:00:00Z"
}
```


Error statuses: `401`, `403`, `422`, `500`.

Related Jira subtasks: H18ABANANA-21, H18ABANANA-27.

<a id="api-06"></a>

### 06. Save the complete talent profile

`PUT /api/v1/me/profile`

Permission: **Talent owner**.

content fully replaces the profile content and must include all eight fields. Read first, retain unedited fields, then submit. Actual changes increment revision, set confirmation to UNCONFIRMED and clear confirmedRevision and confirmedAt. An exact no-op preserves all three. Changed sections receive MANUAL provenance; unchanged sections keep their origin.


| Parameter | Location | Required | Type / allowed values | Constraints |
|---|---|---|---|---|
| `X-CSRF-Token` | header | Yes | string | minimum length: 1 |

Request body: `application/json`, [ProfileWrite](#model-profilewrite).

```json
{
  "expectedRevision": 3,
  "content": {
    "displayName": "Demo Talent A",
    "disciplineGroup": "STEM",
    "education": [
      {
        "id": "edu_001",
        "institution": "UNSW",
        "qualification": "Master of IT",
        "discipline": "Computer Science",
        "startYear": 2025,
        "endYear": null
      }
    ],
    "courses": [],
    "researchExperience": [
      {
        "id": "exp_001",
        "title": "Sample research project",
        "organisation": "Demo lab",
        "description": "Used Python to prepare a small synthetic dataset."
      }
    ],
    "skills": [
      {
        "tagId": "skill_python",
        "claim": "HAS",
        "evidenceText": "Reviewed and corrected Python evidence."
      },
      {
        "tagId": "skill_interviews",
        "claim": "DOES_NOT_HAVE",
        "evidenceText": "I have not conducted research interviews."
      }
    ],
    "researchInterests": [
      "interest_ml"
    ],
    "researchOutputs": []
  }
}
```


Success: **200**, [Profile](#model-profile).

```json
{
  "talentId": "talent_demo_001",
  "revision": 4,
  "content": {
    "displayName": "Demo Talent A",
    "disciplineGroup": "STEM",
    "education": [
      {
        "id": "edu_001",
        "institution": "UNSW",
        "qualification": "Master of IT",
        "discipline": "Computer Science",
        "startYear": 2025,
        "endYear": null
      }
    ],
    "courses": [],
    "researchExperience": [
      {
        "id": "exp_001",
        "title": "Sample research project",
        "organisation": "Demo lab",
        "description": "Used Python to prepare a small synthetic dataset."
      }
    ],
    "skills": [
      {
        "tagId": "skill_python",
        "claim": "HAS",
        "evidenceText": "Reviewed and corrected Python evidence."
      },
      {
        "tagId": "skill_interviews",
        "claim": "DOES_NOT_HAVE",
        "evidenceText": "I have not conducted research interviews."
      }
    ],
    "researchInterests": [
      "interest_ml"
    ],
    "researchOutputs": []
  },
  "confirmation": {
    "status": "UNCONFIRMED",
    "confirmedRevision": null,
    "confirmedAt": null
  },
  "origins": [
    {
      "field": "education",
      "sourceType": "MANUAL",
      "documentId": null
    },
    {
      "field": "courses",
      "sourceType": "MANUAL",
      "documentId": null
    },
    {
      "field": "researchExperience",
      "sourceType": "MANUAL",
      "documentId": null
    },
    {
      "field": "skills",
      "sourceType": "MANUAL",
      "documentId": null
    },
    {
      "field": "researchInterests",
      "sourceType": "MANUAL",
      "documentId": null
    },
    {
      "field": "researchOutputs",
      "sourceType": "MANUAL",
      "documentId": null
    }
  ],
  "updatedAt": "2026-10-03T00:00:00Z"
}
```


Error statuses: `400`, `401`, `403`, `409`, `415`, `422`, `500`.

Related Jira subtasks: H18ABANANA-21, H18ABANANA-27, H18ABANANA-29.

<a id="api-07"></a>

### 07. Confirm the current profile revision

`POST /api/v1/me/profile/confirmation`

Permission: **Talent owner**.

Confirm the complete current profile at expectedRevision. Require a non-empty displayName and at least one non-empty academic/research section, otherwise return 422. Set confirmedRevision=revision without incrementing revision. Repeating confirmation for the same revision preserves the result and original confirmation time. This is user review, not external credential verification.


| Parameter | Location | Required | Type / allowed values | Constraints |
|---|---|---|---|---|
| `X-CSRF-Token` | header | Yes | string | minimum length: 1 |

Request body: `application/json`, [RevisionRequest](#model-revisionrequest).

```json
{
  "expectedRevision": 4
}
```


Success: **200**, [Profile](#model-profile).

```json
{
  "talentId": "talent_demo_001",
  "revision": 4,
  "content": {
    "displayName": "Demo Talent A",
    "disciplineGroup": "STEM",
    "education": [
      {
        "id": "edu_001",
        "institution": "UNSW",
        "qualification": "Master of IT",
        "discipline": "Computer Science",
        "startYear": 2025,
        "endYear": null
      }
    ],
    "courses": [],
    "researchExperience": [
      {
        "id": "exp_001",
        "title": "Sample research project",
        "organisation": "Demo lab",
        "description": "Used Python to prepare a small synthetic dataset."
      }
    ],
    "skills": [
      {
        "tagId": "skill_python",
        "claim": "HAS",
        "evidenceText": "Reviewed and corrected Python evidence."
      },
      {
        "tagId": "skill_interviews",
        "claim": "DOES_NOT_HAVE",
        "evidenceText": "I have not conducted research interviews."
      }
    ],
    "researchInterests": [
      "interest_ml"
    ],
    "researchOutputs": []
  },
  "confirmation": {
    "status": "CONFIRMED",
    "confirmedRevision": 4,
    "confirmedAt": "2026-10-03T00:01:00Z"
  },
  "origins": [
    {
      "field": "education",
      "sourceType": "MANUAL",
      "documentId": null
    },
    {
      "field": "courses",
      "sourceType": "MANUAL",
      "documentId": null
    },
    {
      "field": "researchExperience",
      "sourceType": "MANUAL",
      "documentId": null
    },
    {
      "field": "skills",
      "sourceType": "MANUAL",
      "documentId": null
    },
    {
      "field": "researchInterests",
      "sourceType": "MANUAL",
      "documentId": null
    },
    {
      "field": "researchOutputs",
      "sourceType": "MANUAL",
      "documentId": null
    }
  ],
  "updatedAt": "2026-10-03T00:01:00Z"
}
```


Error statuses: `400`, `401`, `403`, `409`, `415`, `422`, `500`.

Related Jira subtasks: H18ABANANA-21, H18ABANANA-29.

<a id="api-08"></a>

### 08. Read discovery consent and field visibility

`GET /api/v1/me/privacy`

Permission: **Talent owner**.

New accounts default to discoverable=false, visibleFields=[] and revision=0. Return privacy settings only to the owner. This revision is independent of the profile revision.


Path/query parameters: none.

Request body: none.

Success: **200**, [Privacy](#model-privacy).

```json
{
  "revision": 0,
  "discoverable": false,
  "visibleFields": [],
  "updatedAt": "2026-10-03T00:00:00Z"
}
```


Error statuses: `401`, `403`, `422`, `500`.

Related Jira subtasks: H18ABANANA-21, H18ABANANA-30.

<a id="api-09"></a>

### 09. Save discovery consent and field visibility

`PUT /api/v1/me/privacy`

Permission: **Talent owner**.

Replace discoverable and visibleFields together. Actual changes increment the privacy revision; a no-op preserves it. Do not invalidate profile confirmation. Revoking discovery excludes the talent from the next team list/detail request and invalidates stale match caches. Hidden fields must never affect team-visible scores or explanations.


| Parameter | Location | Required | Type / allowed values | Constraints |
|---|---|---|---|---|
| `X-CSRF-Token` | header | Yes | string | minimum length: 1 |

Request body: `application/json`, [PrivacyWrite](#model-privacywrite).

```json
{
  "expectedRevision": 0,
  "discoverable": true,
  "visibleFields": [
    "displayName"
  ]
}
```


Success: **200**, [Privacy](#model-privacy).

```json
{
  "revision": 1,
  "discoverable": true,
  "visibleFields": [
    "displayName"
  ],
  "updatedAt": "2026-10-03T00:00:00Z"
}
```


Error statuses: `400`, `401`, `403`, `409`, `415`, `422`, `500`.

Related Jira subtasks: H18ABANANA-21, H18ABANANA-30.

<a id="api-10"></a>

### 10. List documents uploaded by the current talent

`GET /api/v1/me/documents`

Permission: **Talent owner**.

Return only documents uploaded by the current talent, ordered by createdAt descending and id ascending. Include metadata, not public download URLs.


| Parameter | Location | Required | Type / allowed values | Constraints |
|---|---|---|---|---|
| `page` | query | No | integer | minimum: 1; default: 1 |
| `pageSize` | query | No | integer | minimum: 1; maximum: 100; default: 20 |

Request body: none.

Success: **200**, [DocumentPage](#model-documentpage).

```json
{
  "items": [
    {
      "id": "doc_demo_001",
      "kind": "CV",
      "fileName": "synthetic-cv.pdf",
      "mediaType": "application/pdf",
      "sizeBytes": 2048,
      "status": "READY",
      "createdAt": "2026-10-03T00:00:00Z",
      "updatedAt": "2026-10-03T00:00:00Z",
      "error": null
    }
  ],
  "page": 1,
  "pageSize": 20,
  "total": 1
}
```


Error statuses: `401`, `403`, `422`, `500`.

Related Jira subtasks: H18ABANANA-22, H18ABANANA-23.

<a id="api-11"></a>

### 11. Upload a PDF or DOCX and start extraction

`POST /api/v1/me/documents`

Permission: **Talent owner**.

Upload one file using multipart/form-data. Both file and kind are required; kind is CV or TRANSCRIPT. Proposed limit: 10 MiB (10,485,760 bytes), PDF/DOCX only, no legacy .doc. Validate actual content, format and size on the server, not just the extension. Return 202 with a QUEUED document immediately after acceptance and process extraction asynchronously. Uploading or extracting never automatically overwrites, confirms or publishes profile information.


| Parameter | Location | Required | Type / allowed values | Constraints |
|---|---|---|---|---|
| `X-CSRF-Token` | header | Yes | string | minimum length: 1 |

Request body: `multipart/form-data`.

| Field | Type | Required | Description |
|---|---|---|---|
| file | binary | Yes | One non-empty PDF/DOCX, at most 10 MiB |
| kind | string | Yes | CV / TRANSCRIPT |

```javascript
const form = new FormData();
form.append("file", selectedFile);
form.append("kind", "CV");
await fetch("/api/v1/me/documents", {
  method: "POST",
  credentials: "include",
  headers: { "X-CSRF-Token": csrfToken },
  body: form
});
```


Success: **202**, [Document](#model-document).

```json
{
  "id": "doc_demo_001",
  "kind": "CV",
  "fileName": "synthetic-cv.pdf",
  "mediaType": "application/pdf",
  "sizeBytes": 2048,
  "status": "QUEUED",
  "createdAt": "2026-10-03T00:00:00Z",
  "updatedAt": "2026-10-03T00:00:00Z",
  "error": null
}
```


Error statuses: `400`, `401`, `403`, `413`, `415`, `422`, `429`, `500`.

Related Jira subtasks: H18ABANANA-22, H18ABANANA-23, H18ABANANA-24.

<a id="api-12"></a>

### 12. Read document processing status

`GET /api/v1/me/documents/{documentId}`

Permission: **Talent owner**.

The lifecycle is QUEUED → PROCESSING → READY or FAILED. Poll every two seconds while the view is open and stop at a terminal state. After 60 seconds, pause automatic polling and offer manual refresh; a frontend timeout does not mean the backend status is FAILED. FAILED includes a safe error; other states have error=null.


| Parameter | Location | Required | Type / allowed values | Constraints |
|---|---|---|---|---|
| `documentId` | path | Yes | string | pattern: `^[A-Za-z0-9_-]{1,64}$` |

Request body: none.

Success: **200**, [Document](#model-document).

```json
{
  "id": "doc_demo_001",
  "kind": "CV",
  "fileName": "synthetic-cv.pdf",
  "mediaType": "application/pdf",
  "sizeBytes": 2048,
  "status": "PROCESSING",
  "createdAt": "2026-10-03T00:00:00Z",
  "updatedAt": "2026-10-03T00:00:00Z",
  "error": null
}
```


Error statuses: `401`, `403`, `404`, `422`, `500`.

Related Jira subtasks: H18ABANANA-22, H18ABANANA-23, H18ABANANA-24.

<a id="api-13"></a>

### 13. Read extraction suggestions for review

`GET /api/v1/me/documents/{documentId}/extraction`

Permission: **Talent owner**.

Owner-only. READY returns 200; QUEUED/PROCESSING returns 409 EXTRACTION_NOT_READY; FAILED returns 422 EXTRACTION_FAILED. suggestedSections contains review suggestions and does not mutate the profile. Put unreliable information in uncertainFields rather than inventing positive skill claims.


| Parameter | Location | Required | Type / allowed values | Constraints |
|---|---|---|---|---|
| `documentId` | path | Yes | string | pattern: `^[A-Za-z0-9_-]{1,64}$` |

Request body: none.

Success: **200**, [Extraction](#model-extraction).

```json
{
  "documentId": "doc_demo_001",
  "status": "READY",
  "suggestedSections": {
    "education": [
      {
        "id": "edu_001",
        "institution": "UNSW",
        "qualification": "Master of IT",
        "discipline": "Computer Science",
        "startYear": 2025,
        "endYear": null
      }
    ],
    "skills": [
      {
        "tagId": "skill_python",
        "claim": "HAS",
        "evidenceText": "Used Python in a user-reviewed demo project."
      }
    ]
  },
  "uncertainFields": [
    {
      "field": "researchOutputs",
      "status": "NOT_RECOGNISED",
      "reason": "No reliable output information was found."
    }
  ],
  "warnings": [
    "Review suggestions before saving."
  ],
  "reviewRequired": true
}
```


Error statuses: `401`, `403`, `404`, `409`, `422`, `500`.

Related Jira subtasks: H18ABANANA-22, H18ABANANA-24.

<a id="api-14"></a>

### 14. Save user-reviewed extraction fields to the profile

`POST /api/v1/me/documents/{documentId}/apply`

Permission: **Talent owner**.

Require a READY document owned by the current talent and validate expectedProfileRevision. Not ready returns 409; failed extraction returns 422. sections must contain at least one section. Replace only submitted sections; preserve omitted sections; an explicit [] clears a section. Values are user-reviewed and may correct extraction suggestions. Atomically save, increment revision, mark the entire profile UNCONFIRMED and record USER_REVIEWED_DOCUMENT provenance for the submitted sections. A separate confirmation request is mandatory.


| Parameter | Location | Required | Type / allowed values | Constraints |
|---|---|---|---|---|
| `documentId` | path | Yes | string | pattern: `^[A-Za-z0-9_-]{1,64}$` |
| `X-CSRF-Token` | header | Yes | string | minimum length: 1 |

Request body: `application/json`, [ApplyExtractionRequest](#model-applyextractionrequest).

```json
{
  "expectedProfileRevision": 3,
  "sections": {
    "skills": [
      {
        "tagId": "skill_python",
        "claim": "HAS",
        "evidenceText": "Used Python in a user-reviewed demo project."
      }
    ]
  }
}
```


Success: **200**, [Profile](#model-profile).

```json
{
  "talentId": "talent_demo_001",
  "revision": 4,
  "content": {
    "displayName": "Demo Talent A",
    "disciplineGroup": "STEM",
    "education": [
      {
        "id": "edu_001",
        "institution": "UNSW",
        "qualification": "Master of IT",
        "discipline": "Computer Science",
        "startYear": 2025,
        "endYear": null
      }
    ],
    "courses": [],
    "researchExperience": [
      {
        "id": "exp_001",
        "title": "Sample research project",
        "organisation": "Demo lab",
        "description": "Used Python to prepare a small synthetic dataset."
      }
    ],
    "skills": [
      {
        "tagId": "skill_python",
        "claim": "HAS",
        "evidenceText": "Used Python in a user-reviewed demo project."
      }
    ],
    "researchInterests": [
      "interest_ml"
    ],
    "researchOutputs": []
  },
  "confirmation": {
    "status": "UNCONFIRMED",
    "confirmedRevision": null,
    "confirmedAt": null
  },
  "origins": [
    {
      "field": "education",
      "sourceType": "MANUAL",
      "documentId": null
    },
    {
      "field": "courses",
      "sourceType": "MANUAL",
      "documentId": null
    },
    {
      "field": "researchExperience",
      "sourceType": "MANUAL",
      "documentId": null
    },
    {
      "field": "skills",
      "sourceType": "USER_REVIEWED_DOCUMENT",
      "documentId": "doc_demo_001"
    },
    {
      "field": "researchInterests",
      "sourceType": "MANUAL",
      "documentId": null
    },
    {
      "field": "researchOutputs",
      "sourceType": "MANUAL",
      "documentId": null
    }
  ],
  "updatedAt": "2026-10-03T00:03:00Z"
}
```


Error statuses: `400`, `401`, `403`, `404`, `409`, `415`, `422`, `500`.

Related Jira subtasks: H18ABANANA-21, H18ABANANA-22, H18ABANANA-24, H18ABANANA-29.

<a id="api-15"></a>

### 15. Download an original document owned by the current talent

`GET /api/v1/me/documents/{documentId}/file`

Permission: **Talent owner**.

Check file ownership on every request. A research team cannot download original documents even if the talent is discoverable. Stream through the authenticated endpoint without a public URL. Content-Type must match PDF/DOCX; use Content-Disposition: attachment with a safely encoded filename and X-Content-Type-Options: nosniff.


| Parameter | Location | Required | Type / allowed values | Constraints |
|---|---|---|---|---|
| `documentId` | path | Yes | string | pattern: `^[A-Za-z0-9_-]{1,64}$` |

Request body: none.

Success: **200**, a binary file stream.

```http
Content-Type: application/pdf
Content-Disposition: attachment; filename="synthetic-cv.pdf"
Cache-Control: no-store
X-Content-Type-Options: nosniff

<PDF binary bytes>
```


Error statuses: `401`, `403`, `404`, `422`, `500`.

Related Jira subtasks: H18ABANANA-23.

<a id="api-16"></a>

### 16. List published opportunities or team-owned opportunities

`GET /api/v1/opportunities`

Permission: **Signed-in**.

scope defaults to published and returns published opportunities. scope=mine is team-only and includes that team’s drafts and published opportunities; a talent account requesting mine receives 403. PUBLISHED means active in v0.1. This list is not personalised; use endpoint 21 for talent recommendations.


| Parameter | Location | Required | Type / allowed values | Constraints |
|---|---|---|---|---|
| `scope` | query | No | `published` / `mine` | — |
| `page` | query | No | integer | minimum: 1; default: 1 |
| `pageSize` | query | No | integer | minimum: 1; maximum: 100; default: 20 |

Request body: none.

Success: **200**, [OpportunityPage](#model-opportunitypage).

```json
{
  "items": [
    {
      "id": "opp_demo_001",
      "revision": 2,
      "status": "PUBLISHED",
      "content": {
        "title": "Research assistant in data analysis",
        "university": "UNSW",
        "disciplineGroup": "STEM",
        "discipline": "Computer Science",
        "researchArea": "Research data analysis",
        "description": "Synthetic opportunity for the prototype demonstration.",
        "requirements": [
          {
            "id": "req_python",
            "label": "Python experience",
            "kind": "SKILL",
            "importance": "REQUIRED",
            "tagIds": [
              "skill_python"
            ]
          },
          {
            "id": "req_analysis",
            "label": "Python and SQL",
            "kind": "SKILL",
            "importance": "REQUIRED",
            "tagIds": [
              "skill_python",
              "skill_sql"
            ]
          },
          {
            "id": "req_interviews",
            "label": "Research interview experience",
            "kind": "SKILL",
            "importance": "PREFERRED",
            "tagIds": [
              "skill_interviews"
            ]
          },
          {
            "id": "req_r",
            "label": "R experience",
            "kind": "SKILL",
            "importance": "PREFERRED",
            "tagIds": [
              "skill_r"
            ]
          }
        ]
      },
      "createdAt": "2026-10-03T00:00:00Z",
      "updatedAt": "2026-10-03T00:00:00Z"
    }
  ],
  "page": 1,
  "pageSize": 20,
  "total": 1
}
```


Error statuses: `401`, `403`, `422`, `500`.

Related Jira subtasks: H18ABANANA-19, H18ABANANA-28.

<a id="api-17"></a>

### 17. Create a draft research opportunity

`POST /api/v1/opportunities`

Permission: **Team owner**.

Team-only. The backend assigns id, ownership, revision=1 and status=DRAFT. Clients cannot choose the owner or publication status. Basic fields are required, but a draft may have requirements=[].


| Parameter | Location | Required | Type / allowed values | Constraints |
|---|---|---|---|---|
| `X-CSRF-Token` | header | Yes | string | minimum length: 1 |

Request body: `application/json`, [OpportunityContent](#model-opportunitycontent).

```json
{
  "title": "Research assistant in data analysis",
  "university": "UNSW",
  "disciplineGroup": "STEM",
  "discipline": "Computer Science",
  "researchArea": "Research data analysis",
  "description": "Synthetic opportunity for the prototype demonstration.",
  "requirements": [
    {
      "id": "req_python",
      "label": "Python experience",
      "kind": "SKILL",
      "importance": "REQUIRED",
      "tagIds": [
        "skill_python"
      ]
    },
    {
      "id": "req_analysis",
      "label": "Python and SQL",
      "kind": "SKILL",
      "importance": "REQUIRED",
      "tagIds": [
        "skill_python",
        "skill_sql"
      ]
    },
    {
      "id": "req_interviews",
      "label": "Research interview experience",
      "kind": "SKILL",
      "importance": "PREFERRED",
      "tagIds": [
        "skill_interviews"
      ]
    },
    {
      "id": "req_r",
      "label": "R experience",
      "kind": "SKILL",
      "importance": "PREFERRED",
      "tagIds": [
        "skill_r"
      ]
    }
  ]
}
```


Success: **201**, [Opportunity](#model-opportunity).

```json
{
  "id": "opp_demo_001",
  "revision": 1,
  "status": "DRAFT",
  "content": {
    "title": "Research assistant in data analysis",
    "university": "UNSW",
    "disciplineGroup": "STEM",
    "discipline": "Computer Science",
    "researchArea": "Research data analysis",
    "description": "Synthetic opportunity for the prototype demonstration.",
    "requirements": [
      {
        "id": "req_python",
        "label": "Python experience",
        "kind": "SKILL",
        "importance": "REQUIRED",
        "tagIds": [
          "skill_python"
        ]
      },
      {
        "id": "req_analysis",
        "label": "Python and SQL",
        "kind": "SKILL",
        "importance": "REQUIRED",
        "tagIds": [
          "skill_python",
          "skill_sql"
        ]
      },
      {
        "id": "req_interviews",
        "label": "Research interview experience",
        "kind": "SKILL",
        "importance": "PREFERRED",
        "tagIds": [
          "skill_interviews"
        ]
      },
      {
        "id": "req_r",
        "label": "R experience",
        "kind": "SKILL",
        "importance": "PREFERRED",
        "tagIds": [
          "skill_r"
        ]
      }
    ]
  },
  "createdAt": "2026-10-03T00:00:00Z",
  "updatedAt": "2026-10-03T00:00:00Z"
}
```


Error statuses: `400`, `401`, `403`, `415`, `422`, `500`.

Related Jira subtasks: H18ABANANA-19, H18ABANANA-28.

<a id="api-18"></a>

### 18. Read research opportunity details

`GET /api/v1/opportunities/{opportunityId}`

Permission: **Signed-in**.

Signed-in users may read published opportunities. Only the owner may read a draft; other callers receive 404. Do not return internal team account data or database objects.


| Parameter | Location | Required | Type / allowed values | Constraints |
|---|---|---|---|---|
| `opportunityId` | path | Yes | string | pattern: `^[A-Za-z0-9_-]{1,64}$` |

Request body: none.

Success: **200**, [Opportunity](#model-opportunity).

```json
{
  "id": "opp_demo_001",
  "revision": 2,
  "status": "PUBLISHED",
  "content": {
    "title": "Research assistant in data analysis",
    "university": "UNSW",
    "disciplineGroup": "STEM",
    "discipline": "Computer Science",
    "researchArea": "Research data analysis",
    "description": "Synthetic opportunity for the prototype demonstration.",
    "requirements": [
      {
        "id": "req_python",
        "label": "Python experience",
        "kind": "SKILL",
        "importance": "REQUIRED",
        "tagIds": [
          "skill_python"
        ]
      },
      {
        "id": "req_analysis",
        "label": "Python and SQL",
        "kind": "SKILL",
        "importance": "REQUIRED",
        "tagIds": [
          "skill_python",
          "skill_sql"
        ]
      },
      {
        "id": "req_interviews",
        "label": "Research interview experience",
        "kind": "SKILL",
        "importance": "PREFERRED",
        "tagIds": [
          "skill_interviews"
        ]
      },
      {
        "id": "req_r",
        "label": "R experience",
        "kind": "SKILL",
        "importance": "PREFERRED",
        "tagIds": [
          "skill_r"
        ]
      }
    ]
  },
  "createdAt": "2026-10-03T00:00:00Z",
  "updatedAt": "2026-10-03T00:00:00Z"
}
```


Error statuses: `401`, `403`, `404`, `422`, `500`.

Related Jira subtasks: H18ABANANA-19, H18ABANANA-28.

<a id="api-19"></a>

### 19. Save research opportunity changes

`PUT /api/v1/opportunities/{opportunityId}`

Permission: **Team owner**.

Owner-only, with expectedRevision checking and full content replacement. Actual changes increment revision; a no-op preserves it. Keep publication status unchanged. Subsequent matching uses the edited version of a published opportunity. A published opportunity must retain at least one valid requirement, otherwise return 422.


| Parameter | Location | Required | Type / allowed values | Constraints |
|---|---|---|---|---|
| `opportunityId` | path | Yes | string | pattern: `^[A-Za-z0-9_-]{1,64}$` |
| `X-CSRF-Token` | header | Yes | string | minimum length: 1 |

Request body: `application/json`, [OpportunityWrite](#model-opportunitywrite).

```json
{
  "expectedRevision": 2,
  "content": {
    "title": "Research assistant in research data systems",
    "university": "UNSW",
    "disciplineGroup": "STEM",
    "discipline": "Computer Science",
    "researchArea": "Research data analysis",
    "description": "Synthetic opportunity for the prototype demonstration.",
    "requirements": [
      {
        "id": "req_python",
        "label": "Python experience",
        "kind": "SKILL",
        "importance": "REQUIRED",
        "tagIds": [
          "skill_python"
        ]
      },
      {
        "id": "req_analysis",
        "label": "Python and SQL",
        "kind": "SKILL",
        "importance": "REQUIRED",
        "tagIds": [
          "skill_python",
          "skill_sql"
        ]
      },
      {
        "id": "req_interviews",
        "label": "Research interview experience",
        "kind": "SKILL",
        "importance": "PREFERRED",
        "tagIds": [
          "skill_interviews"
        ]
      },
      {
        "id": "req_r",
        "label": "R experience",
        "kind": "SKILL",
        "importance": "PREFERRED",
        "tagIds": [
          "skill_r"
        ]
      }
    ]
  }
}
```


Success: **200**, [Opportunity](#model-opportunity).

```json
{
  "id": "opp_demo_001",
  "revision": 3,
  "status": "PUBLISHED",
  "content": {
    "title": "Research assistant in research data systems",
    "university": "UNSW",
    "disciplineGroup": "STEM",
    "discipline": "Computer Science",
    "researchArea": "Research data analysis",
    "description": "Synthetic opportunity for the prototype demonstration.",
    "requirements": [
      {
        "id": "req_python",
        "label": "Python experience",
        "kind": "SKILL",
        "importance": "REQUIRED",
        "tagIds": [
          "skill_python"
        ]
      },
      {
        "id": "req_analysis",
        "label": "Python and SQL",
        "kind": "SKILL",
        "importance": "REQUIRED",
        "tagIds": [
          "skill_python",
          "skill_sql"
        ]
      },
      {
        "id": "req_interviews",
        "label": "Research interview experience",
        "kind": "SKILL",
        "importance": "PREFERRED",
        "tagIds": [
          "skill_interviews"
        ]
      },
      {
        "id": "req_r",
        "label": "R experience",
        "kind": "SKILL",
        "importance": "PREFERRED",
        "tagIds": [
          "skill_r"
        ]
      }
    ]
  },
  "createdAt": "2026-10-03T00:00:00Z",
  "updatedAt": "2026-10-03T00:02:00Z"
}
```


Error statuses: `400`, `401`, `403`, `404`, `409`, `415`, `422`, `500`.

Related Jira subtasks: H18ABANANA-19, H18ABANANA-28.

<a id="api-20"></a>

### 20. Publish a research opportunity

`POST /api/v1/opportunities/{opportunityId}/publish`

Permission: **Team owner**.

Owner-only. Check the current revision, basic fields and at least one valid requirement whose tags exist and have the correct kind. DRAFT → PUBLISHED increments revision. Repeating publication with the current published revision does not increment it again; a stale revision still returns 409.


| Parameter | Location | Required | Type / allowed values | Constraints |
|---|---|---|---|---|
| `opportunityId` | path | Yes | string | pattern: `^[A-Za-z0-9_-]{1,64}$` |
| `X-CSRF-Token` | header | Yes | string | minimum length: 1 |

Request body: `application/json`, [RevisionRequest](#model-revisionrequest).

```json
{
  "expectedRevision": 1
}
```


Success: **200**, [Opportunity](#model-opportunity).

```json
{
  "id": "opp_demo_001",
  "revision": 2,
  "status": "PUBLISHED",
  "content": {
    "title": "Research assistant in data analysis",
    "university": "UNSW",
    "disciplineGroup": "STEM",
    "discipline": "Computer Science",
    "researchArea": "Research data analysis",
    "description": "Synthetic opportunity for the prototype demonstration.",
    "requirements": [
      {
        "id": "req_python",
        "label": "Python experience",
        "kind": "SKILL",
        "importance": "REQUIRED",
        "tagIds": [
          "skill_python"
        ]
      },
      {
        "id": "req_analysis",
        "label": "Python and SQL",
        "kind": "SKILL",
        "importance": "REQUIRED",
        "tagIds": [
          "skill_python",
          "skill_sql"
        ]
      },
      {
        "id": "req_interviews",
        "label": "Research interview experience",
        "kind": "SKILL",
        "importance": "PREFERRED",
        "tagIds": [
          "skill_interviews"
        ]
      },
      {
        "id": "req_r",
        "label": "R experience",
        "kind": "SKILL",
        "importance": "PREFERRED",
        "tagIds": [
          "skill_r"
        ]
      }
    ]
  },
  "createdAt": "2026-10-03T00:00:00Z",
  "updatedAt": "2026-10-03T00:00:00Z"
}
```


Error statuses: `400`, `401`, `403`, `404`, `409`, `415`, `422`, `500`.

Related Jira subtasks: H18ABANANA-19, H18ABANANA-28.

<a id="api-21"></a>

### 21. List ranked opportunity recommendations for the current talent

`GET /api/v1/me/recommendations`

Permission: **Talent owner**.

Talent owner only. Return 409 PROFILE_UNCONFIRMED unless the current profile is confirmed and confirmedRevision equals revision. Otherwise evaluate all published opportunities using the owner’s confirmed content. Private owner fields may be used for this owner-only result. Apply the global ranking rules before pagination. No opportunities returns 200 with an empty list.


| Parameter | Location | Required | Type / allowed values | Constraints |
|---|---|---|---|---|
| `page` | query | No | integer | minimum: 1; default: 1 |
| `pageSize` | query | No | integer | minimum: 1; maximum: 100; default: 20 |

Request body: none.

Success: **200**, [RecommendationPage](#model-recommendationpage).

```json
{
  "items": [
    {
      "rank": 1,
      "opportunity": {
        "id": "opp_demo_001",
        "revision": 2,
        "status": "PUBLISHED",
        "content": {
          "title": "Research assistant in data analysis",
          "university": "UNSW",
          "disciplineGroup": "STEM",
          "discipline": "Computer Science",
          "researchArea": "Research data analysis",
          "description": "Synthetic opportunity for the prototype demonstration.",
          "requirements": [
            {
              "id": "req_python",
              "label": "Python experience",
              "kind": "SKILL",
              "importance": "REQUIRED",
              "tagIds": [
                "skill_python"
              ]
            },
            {
              "id": "req_analysis",
              "label": "Python and SQL",
              "kind": "SKILL",
              "importance": "REQUIRED",
              "tagIds": [
                "skill_python",
                "skill_sql"
              ]
            },
            {
              "id": "req_interviews",
              "label": "Research interview experience",
              "kind": "SKILL",
              "importance": "PREFERRED",
              "tagIds": [
                "skill_interviews"
              ]
            },
            {
              "id": "req_r",
              "label": "R experience",
              "kind": "SKILL",
              "importance": "PREFERRED",
              "tagIds": [
                "skill_r"
              ]
            }
          ]
        },
        "createdAt": "2026-10-03T00:00:00Z",
        "updatedAt": "2026-10-03T00:00:00Z"
      },
      "summary": {
        "score": 50,
        "unknownWeightPercent": 16.67,
        "requiredGapCount": 0,
        "evaluationStatus": "EVALUATED",
        "algorithmVersion": "tag-coverage-v1"
      }
    }
  ],
  "page": 1,
  "pageSize": 20,
  "total": 1
}
```


Error statuses: `401`, `403`, `409`, `422`, `500`.

Related Jira subtasks: H18ABANANA-20, H18ABANANA-31, H18ABANANA-32.

<a id="api-22"></a>

### 22. Read requirement-level matching explanations for the current talent

`GET /api/v1/me/opportunity-matches/{opportunityId}`

Permission: **Talent owner**.

Talent owner only. The opportunity must be published, otherwise return 404. The current profile must be confirmed, otherwise return 409. Return each requirement, status, reasonCode, reason and evidence using current profile/opportunity revisions, not a stale score. Owner evidence may reference owner documents but must not contain fabricated claims.


| Parameter | Location | Required | Type / allowed values | Constraints |
|---|---|---|---|---|
| `opportunityId` | path | Yes | string | pattern: `^[A-Za-z0-9_-]{1,64}$` |

Request body: none.

Success: **200**, [OwnerMatch](#model-ownermatch).

```json
{
  "opportunity": {
    "id": "opp_demo_001",
    "revision": 2,
    "status": "PUBLISHED",
    "content": {
      "title": "Research assistant in data analysis",
      "university": "UNSW",
      "disciplineGroup": "STEM",
      "discipline": "Computer Science",
      "researchArea": "Research data analysis",
      "description": "Synthetic opportunity for the prototype demonstration.",
      "requirements": [
        {
          "id": "req_python",
          "label": "Python experience",
          "kind": "SKILL",
          "importance": "REQUIRED",
          "tagIds": [
            "skill_python"
          ]
        },
        {
          "id": "req_analysis",
          "label": "Python and SQL",
          "kind": "SKILL",
          "importance": "REQUIRED",
          "tagIds": [
            "skill_python",
            "skill_sql"
          ]
        },
        {
          "id": "req_interviews",
          "label": "Research interview experience",
          "kind": "SKILL",
          "importance": "PREFERRED",
          "tagIds": [
            "skill_interviews"
          ]
        },
        {
          "id": "req_r",
          "label": "R experience",
          "kind": "SKILL",
          "importance": "PREFERRED",
          "tagIds": [
            "skill_r"
          ]
        }
      ]
    },
    "createdAt": "2026-10-03T00:00:00Z",
    "updatedAt": "2026-10-03T00:00:00Z"
  },
  "profileRevision": 3,
  "summary": {
    "score": 50,
    "unknownWeightPercent": 16.67,
    "requiredGapCount": 0,
    "evaluationStatus": "EVALUATED",
    "algorithmVersion": "tag-coverage-v1"
  },
  "requirements": [
    {
      "requirement": {
        "id": "req_python",
        "label": "Python experience",
        "kind": "SKILL",
        "importance": "REQUIRED",
        "tagIds": [
          "skill_python"
        ]
      },
      "status": "MATCHED",
      "reasonCode": "ALL_TAGS_SUPPORTED",
      "reason": "Confirmed Python claim supports this requirement.",
      "evidence": [
        {
          "field": "skills",
          "recordId": "skill_python",
          "valueSummary": "Has Python experience.",
          "confirmedRevision": 3,
          "sourceType": "MANUAL",
          "documentId": null
        }
      ]
    },
    {
      "requirement": {
        "id": "req_analysis",
        "label": "Python and SQL",
        "kind": "SKILL",
        "importance": "REQUIRED",
        "tagIds": [
          "skill_python",
          "skill_sql"
        ]
      },
      "status": "PARTIAL",
      "reasonCode": "SOME_TAGS_SUPPORTED",
      "reason": "Python is supported; there is insufficient evidence for SQL.",
      "evidence": [
        {
          "field": "skills",
          "recordId": "skill_python",
          "valueSummary": "Has Python experience.",
          "confirmedRevision": 3,
          "sourceType": "MANUAL",
          "documentId": null
        }
      ]
    },
    {
      "requirement": {
        "id": "req_interviews",
        "label": "Research interview experience",
        "kind": "SKILL",
        "importance": "PREFERRED",
        "tagIds": [
          "skill_interviews"
        ]
      },
      "status": "GAP",
      "reasonCode": "EXPLICIT_NEGATIVE_CLAIM",
      "reason": "The user explicitly confirmed no research interview experience.",
      "evidence": [
        {
          "field": "skills",
          "recordId": "skill_interviews",
          "valueSummary": "Explicitly reports no research interview experience.",
          "confirmedRevision": 3,
          "sourceType": "MANUAL",
          "documentId": null
        }
      ]
    },
    {
      "requirement": {
        "id": "req_r",
        "label": "R experience",
        "kind": "SKILL",
        "importance": "PREFERRED",
        "tagIds": [
          "skill_r"
        ]
      },
      "status": "UNKNOWN",
      "reasonCode": "INSUFFICIENT_EVIDENCE",
      "reason": "There is insufficient confirmed evidence for this requirement.",
      "evidence": []
    }
  ],
  "evaluatedAt": "2026-10-03T00:00:00Z"
}
```


Error statuses: `401`, `403`, `404`, `409`, `422`, `500`.

Related Jira subtasks: H18ABANANA-20, H18ABANANA-31, H18ABANANA-32.

<a id="api-23"></a>

### 23. List matching talent for a team-owned opportunity

`GET /api/v1/opportunities/{opportunityId}/talent-matches`

Permission: **Team owner**.

Only the owner of a published opportunity may call this endpoint. Missing, non-owned or unpublished opportunities return 404. Exclude opted-out and currently unconfirmed talent before scoring, ranking, paginating and counting total. Use only each talent’s allowed visible fields; hidden fields count as insufficient evidence. visibleFields=[] is allowed: an anonymous talent object can appear with UNKNOWN results.


| Parameter | Location | Required | Type / allowed values | Constraints |
|---|---|---|---|---|
| `opportunityId` | path | Yes | string | pattern: `^[A-Za-z0-9_-]{1,64}$` |
| `page` | query | No | integer | minimum: 1; default: 1 |
| `pageSize` | query | No | integer | minimum: 1; maximum: 100; default: 20 |

Request body: none.

Success: **200**, [TalentMatchPage](#model-talentmatchpage).

```json
{
  "items": [
    {
      "rank": 1,
      "talent": {
        "talentId": "talent_demo_001",
        "fields": {
          "displayName": "Demo Talent A"
        }
      },
      "summary": {
        "score": 0,
        "unknownWeightPercent": 100,
        "requiredGapCount": 0,
        "evaluationStatus": "EVALUATED",
        "algorithmVersion": "tag-coverage-v1"
      }
    }
  ],
  "page": 1,
  "pageSize": 20,
  "total": 1
}
```


Error statuses: `401`, `403`, `404`, `422`, `500`.

Related Jira subtasks: H18ABANANA-20, H18ABANANA-30, H18ABANANA-31, H18ABANANA-33.

<a id="api-24"></a>

### 24. Read permitted talent information and matching explanations

`GET /api/v1/opportunities/{opportunityId}/talent-matches/{talentId}`

Permission: **Team owner**.

Re-check opportunity ownership/publication, discovery consent, current confirmation and field visibility on every request. Opted-out or unconfirmed talent returns 404 even if previously listed. Return only permitted fields and TeamEvidence: no email, document IDs, original filenames, download links, private field values or origin metadata.


| Parameter | Location | Required | Type / allowed values | Constraints |
|---|---|---|---|---|
| `opportunityId` | path | Yes | string | pattern: `^[A-Za-z0-9_-]{1,64}$` |
| `talentId` | path | Yes | string | pattern: `^[A-Za-z0-9_-]{1,64}$` |

Request body: none.

Success: **200**, [TeamMatch](#model-teammatch).

```json
{
  "opportunityId": "opp_demo_001",
  "opportunityRevision": 2,
  "talent": {
    "talentId": "talent_demo_001",
    "fields": {
      "displayName": "Demo Talent A"
    }
  },
  "summary": {
    "score": 0,
    "unknownWeightPercent": 100,
    "requiredGapCount": 0,
    "evaluationStatus": "EVALUATED",
    "algorithmVersion": "tag-coverage-v1"
  },
  "requirements": [
    {
      "requirement": {
        "id": "req_python",
        "label": "Python experience",
        "kind": "SKILL",
        "importance": "REQUIRED",
        "tagIds": [
          "skill_python"
        ]
      },
      "status": "UNKNOWN",
      "reasonCode": "INSUFFICIENT_EVIDENCE",
      "reason": "There is insufficient shared evidence for this requirement.",
      "evidence": []
    },
    {
      "requirement": {
        "id": "req_analysis",
        "label": "Python and SQL",
        "kind": "SKILL",
        "importance": "REQUIRED",
        "tagIds": [
          "skill_python",
          "skill_sql"
        ]
      },
      "status": "UNKNOWN",
      "reasonCode": "INSUFFICIENT_EVIDENCE",
      "reason": "There is insufficient shared evidence for this requirement.",
      "evidence": []
    },
    {
      "requirement": {
        "id": "req_interviews",
        "label": "Research interview experience",
        "kind": "SKILL",
        "importance": "PREFERRED",
        "tagIds": [
          "skill_interviews"
        ]
      },
      "status": "UNKNOWN",
      "reasonCode": "INSUFFICIENT_EVIDENCE",
      "reason": "There is insufficient shared evidence for this requirement.",
      "evidence": []
    },
    {
      "requirement": {
        "id": "req_r",
        "label": "R experience",
        "kind": "SKILL",
        "importance": "PREFERRED",
        "tagIds": [
          "skill_r"
        ]
      },
      "status": "UNKNOWN",
      "reasonCode": "INSUFFICIENT_EVIDENCE",
      "reason": "There is insufficient shared evidence for this requirement.",
      "evidence": []
    }
  ],
  "evaluatedAt": "2026-10-03T00:00:00Z"
}
```


Error statuses: `401`, `403`, `404`, `422`, `500`.

Related Jira subtasks: H18ABANANA-20, H18ABANANA-30, H18ABANANA-31, H18ABANANA-33.

## 5. Shared error handling

Use the structure below for every error response. The frontend branches on `error.code`, not the wording of message. message is suitable for display. Field paths use dot notation and array indices, for example `content.education[0].institution`. Use `fieldErrors=[]` if there are no field errors. Include `currentRevision` only for revision conflicts; otherwise omit it.


```json
{
  "error": {
    "code": "REVISION_CONFLICT",
    "message": "Reload the latest resource before saving.",
    "fieldErrors": [],
    "currentRevision": 4
  },
  "requestId": "req_demo_001"
}
```


| HTTP | error.code | Condition | Frontend response |
|---|---|---|---|
| 400 | BAD_REQUEST | Unparseable JSON or malformed multipart framing | Show failure and preserve input |
| 401 | UNAUTHENTICATED | Missing or expired session | Clear account caches and return to login |
| 401 | INVALID_CREDENTIALS | Invalid login credentials | Show a generic login error |
| 403 | FORBIDDEN | Role lacks permission | Show access denied; do not retry |
| 403 | CSRF_INVALID | CSRF or Origin validation failed | Read the session again and offer retry; do not automatically replay a mutation |
| 404 | NOT_FOUND | Missing/inaccessible resource or talent whose visibility was revoked | Show unavailable and refetch the list |
| 405 | BAD_REQUEST | HTTP method is unsupported; `Allow` lists supported methods | Correct the request method; do not replay unchanged |
| 409 | REVISION_CONFLICT | Stale expectedRevision | Preserve local input, reload and compare |
| 409 | PROFILE_UNCONFIRMED | Owner requests recommendations with an unconfirmed current profile | Direct the user to review and confirm |
| 409 | EXTRACTION_NOT_READY | Extraction is queued or processing | Continue status checks without importing |
| 413 | UPLOAD_TOO_LARGE | File exceeds 10 MiB | Explain the size limit |
| 415 | UNSUPPORTED_FILE_TYPE | Upload is not a supported PDF/DOCX | Explain accepted formats |
| 415 | UNSUPPORTED_MEDIA_TYPE | Incorrect request Content-Type | Correct the request adapter |
| 422 | VALIDATION_ERROR | Invalid fields or unmet publication/confirmation prerequisites | Display fieldErrors beside the relevant inputs |
| 422 | EXTRACTION_FAILED | Extraction/import requested for a failed document | Offer manual entry and preserve existing profile content |
| 429 | RATE_LIMITED | Login or upload rate limit exceeded | Ask the user to try later and stop repeated requests |
| 500 | INTERNAL_ERROR | Unexpected server failure | Preserve input and requestId and offer a later retry |

Do not expose stack traces, database errors or filesystem paths in message. `requestId` supports log investigation. `Document.error` uses ErrorDetail without a nested requestId. A document status request may successfully return 200 with status=FAILED; requesting or importing that failed extraction returns 422.

## 6. Complete data model definitions

Referenced types link to their definitions below. Array entries must match their item type. All objects reject additional fields. Required means the key must exist; nullable required fields must still be sent.

This section defines all 47 public models. The binary upload request is the additional request shape described in endpoint 11.


<a id="model-id"></a>

### Id

All business IDs follow this format. The backend generates top-level resource IDs. The frontend may generate stable UUID strings for education, course, experience, output and requirement records. Retain IDs when editing, create new IDs for new records and do not use array indices as persistent IDs.

Type: string. pattern: `^[A-Za-z0-9_-]{1,64}$`.

<a id="model-profilefield"></a>

### ProfileField

Privacy applies to an entire field/section in this version, not an individual education record or skill. This enum is the complete whitelist for visibleFields.

Type: `displayName` / `disciplineGroup` / `education` / `courses` / `researchExperience` / `skills` / `researchInterests` / `researchOutputs`. .

<a id="model-user"></a>

### User

| Field | Type / allowed values | Required | Description and constraints |
|---|---|---|---|
| `id` | string | Yes | Object identifier; preserve IDs when editing existing records; pattern: `^[A-Za-z0-9_-]{1,64}$` |
| `displayName` | string | Yes | Display name; also subject to visibility controls in team responses; minimum length: 1 |
| `email` | string | Yes | Login email, visible only to the account owner; format: email |
| `role` | `TALENT` / `RESEARCH_TEAM` | Yes | Account role assigned by the backend |

<a id="model-session"></a>

### Session

| Field | Type / allowed values | Required | Description and constraints |
|---|---|---|---|
| `user` | [User](#model-user) / null | Yes | null for anonymous sessions; otherwise the account object |
| `csrfToken` | string | Yes | Token for subsequent mutations; not the session ID; minimum length: 1 |

<a id="model-loginrequest"></a>

### LoginRequest

| Field | Type / allowed values | Required | Description and constraints |
|---|---|---|---|
| `email` | string | Yes | Login email, visible only to the account owner; format: email |
| `password` | string | Yes | Request-only; never return or log plaintext passwords; minimum length: 1; maximum length: 200 |

<a id="model-tag"></a>

### Tag

| Field | Type / allowed values | Required | Description and constraints |
|---|---|---|---|
| `id` | string | Yes | Object identifier; preserve IDs when editing existing records; pattern: `^[A-Za-z0-9_-]{1,64}$` |
| `label` | string | Yes | Human-readable label; minimum length: 1 |
| `kind` | `SKILL` / `INTEREST` | Yes | Category; use the specified enum values |
| `disciplineGroups` | `STEM` / `BUSINESS`[] | Yes | Discipline groups in which the tag is available; unique items |

<a id="model-taglist"></a>

### TagList

| Field | Type / allowed values | Required | Description and constraints |
|---|---|---|---|
| `items` | [Tag](#model-tag)[] | Yes | Current page items; for tags, the complete vocabulary result |

<a id="model-education"></a>

### Education

| Field | Type / allowed values | Required | Description and constraints |
|---|---|---|---|
| `id` | string | Yes | Object identifier; preserve IDs when editing existing records; pattern: `^[A-Za-z0-9_-]{1,64}$` |
| `institution` | string | Yes | University or institution name; minimum length: 1; maximum length: 200 |
| `qualification` | string | Yes | Degree or qualification name; minimum length: 1; maximum length: 200 |
| `discipline` | string | Yes | Discipline name; maximum length: 200 |
| `startYear` | integer / null | Yes | Starting year; null if unknown; minimum: 1900; maximum: 2200 |
| `endYear` | integer / null | Yes | Ending year; null if ongoing or unknown; minimum: 1900; maximum: 2200 |

<a id="model-course"></a>

### Course

| Field | Type / allowed values | Required | Description and constraints |
|---|---|---|---|
| `id` | string | Yes | Object identifier; preserve IDs when editing existing records; pattern: `^[A-Za-z0-9_-]{1,64}$` |
| `name` | string | Yes | Name; minimum length: 1; maximum length: 200 |
| `code` | string / null | Yes | Course code; null if unknown. In an error object, this is the error code; maximum length: 200 |
| `description` | string | Yes | Plain-text description; maximum length: 5000 |

<a id="model-researchexperience"></a>

### ResearchExperience

| Field | Type / allowed values | Required | Description and constraints |
|---|---|---|---|
| `id` | string | Yes | Object identifier; preserve IDs when editing existing records; pattern: `^[A-Za-z0-9_-]{1,64}$` |
| `title` | string | Yes | Title; minimum length: 1; maximum length: 200 |
| `organisation` | string | Yes | Research institution or organisation; maximum length: 200 |
| `description` | string | Yes | Plain-text description; maximum length: 5000 |

<a id="model-skillclaim"></a>

### SkillClaim

An unselected skill is unknown, not absent. DOES_NOT_HAVE is entered or reviewed explicitly by the user; extraction must not infer it from a skill not being found.

| Field | Type / allowed values | Required | Description and constraints |
|---|---|---|---|
| `tagId` | string | Yes | Shared tag ID; do not substitute display text; pattern: `^[A-Za-z0-9_-]{1,64}$` |
| `claim` | `HAS` / `DOES_NOT_HAVE` | Yes | HAS is an affirmative user claim; DOES_NOT_HAVE is an explicit negative claim, never inferred from omission |
| `evidenceText` | string | Yes | User-reviewed evidence description; may be empty, in which case only the tag claim itself can be cited; maximum length: 2000 |

<a id="model-researchoutput"></a>

### ResearchOutput

Only HTTP/HTTPS URLs are accepted. The frontend should use appropriate link attributes when opening a new tab. The backend must not automatically fetch arbitrary addresses from this field.

| Field | Type / allowed values | Required | Description and constraints |
|---|---|---|---|
| `id` | string | Yes | Object identifier; preserve IDs when editing existing records; pattern: `^[A-Za-z0-9_-]{1,64}$` |
| `title` | string | Yes | Title; minimum length: 1; maximum length: 300 |
| `type` | `PUBLICATION` / `PROJECT` / `OTHER` | Yes | Research output type |
| `url` | string / null | Yes | HTTP/HTTPS link to an output; null if absent; format: uri; pattern: `^https?://` |
| `description` | string | Yes | Plain-text description; maximum length: 5000 |

<a id="model-profilecontent"></a>

### ProfileContent

PUT fully replaces all eight required fields. Use [] for an unfilled section and null for an unknown discipline group. Keep an existing child record ID when editing, assign a new ID when adding and remove a record from its array to delete it. Each section allows up to 100 items.

| Field | Type / allowed values | Required | Description and constraints |
|---|---|---|---|
| `displayName` | string | Yes | Display name; also subject to visibility controls in team responses; maximum length: 100 |
| `disciplineGroup` | `STEM` / `BUSINESS` / null | Yes | STEM or BUSINESS; nullable for talent who has not selected a group |
| `education` | [Education](#model-education)[] | Yes | Education records; maximum items: 100 |
| `courses` | [Course](#model-course)[] | Yes | Course records; maximum items: 100 |
| `researchExperience` | [ResearchExperience](#model-researchexperience)[] | Yes | Research experience records; maximum items: 100 |
| `skills` | [SkillClaim](#model-skillclaim)[] | Yes | Skill claims; tagId must be unique and refer to a SKILL tag; maximum items: 100 |
| `researchInterests` | string[] | Yes | Interest tag IDs, each referring to an INTEREST tag; maximum items: 100; unique items |
| `researchOutputs` | [ResearchOutput](#model-researchoutput)[] | Yes | Research output records; maximum items: 100 |

<a id="model-profilesections"></a>

### ProfileSections

Partial import object with at least one section. Omitted sections are unchanged; [] clears a section. Only the six academic/research sections are accepted; displayName and disciplineGroup are not imported here.

| Field | Type / allowed values | Required | Description and constraints |
|---|---|---|---|
| `education` | [Education](#model-education)[] | No | Education records; maximum items: 100 |
| `courses` | [Course](#model-course)[] | No | Course records; maximum items: 100 |
| `researchExperience` | [ResearchExperience](#model-researchexperience)[] | No | Research experience records; maximum items: 100 |
| `skills` | [SkillClaim](#model-skillclaim)[] | No | Skill claims; tagId must be unique and refer to a SKILL tag; maximum items: 100 |
| `researchInterests` | string[] | No | Interest tag IDs, each referring to an INTEREST tag; maximum items: 100; unique items |
| `researchOutputs` | [ResearchOutput](#model-researchoutput)[] | No | Research output records; maximum items: 100 |

<a id="model-confirmation"></a>

### Confirmation

Matching requires status=CONFIRMED and confirmedRevision=Profile.revision. For UNCONFIRMED, both confirmedRevision and confirmedAt must be null.

| Field | Type / allowed values | Required | Description and constraints |
|---|---|---|---|
| `status` | `UNCONFIRMED` / `CONFIRMED` | Yes | Status enum; see the relevant business rules |
| `confirmedRevision` | integer / null | Yes | Confirmed revision; null while unconfirmed; minimum: 0 |
| `confirmedAt` | string / null | Yes | Time of user confirmation; null while unconfirmed; format: date-time |

<a id="model-fieldorigin"></a>

### FieldOrigin

Provenance is tracked per section, not as a verified sentence-level file citation or independent credential check. Manually editing an imported section changes its origin to MANUAL. The backend sets provenance; PUT cannot specify it.

| Field | Type / allowed values | Required | Description and constraints |
|---|---|---|---|
| `field` | `education` / `courses` / `researchExperience` / `skills` / `researchInterests` / `researchOutputs` | Yes | Associated field or section |
| `sourceType` | `MANUAL` / `USER_REVIEWED_DOCUMENT` | Yes | Server-maintained origin: MANUAL or USER_REVIEWED_DOCUMENT |
| `documentId` | string / null | Yes | Owner-only document source reference; null for manual input; never disclosed to research teams; pattern: `^[A-Za-z0-9_-]{1,64}$` |

<a id="model-profile"></a>

### Profile

| Field | Type / allowed values | Required | Description and constraints |
|---|---|---|---|
| `talentId` | string | Yes | Talent identifier assigned by the backend; pattern: `^[A-Za-z0-9_-]{1,64}$` |
| `revision` | integer | Yes | Current resource version, independent of other resources; minimum: 0 |
| `content` | [ProfileContent](#model-profilecontent) | Yes | Business content of the resource |
| `confirmation` | [Confirmation](#model-confirmation) | Yes | Confirmation state of the current profile |
| `origins` | [FieldOrigin](#model-fieldorigin)[] | Yes | Section provenance visible only to the owner |
| `updatedAt` | string | Yes | Last update time in UTC; format: date-time |

<a id="model-profilewrite"></a>

### ProfileWrite

| Field | Type / allowed values | Required | Description and constraints |
|---|---|---|---|
| `expectedRevision` | integer | Yes | Resource revision most recently read by the frontend; minimum: 0 |
| `content` | [ProfileContent](#model-profilecontent) | Yes | Business content of the resource |

<a id="model-revisionrequest"></a>

### RevisionRequest

| Field | Type / allowed values | Required | Description and constraints |
|---|---|---|---|
| `expectedRevision` | integer | Yes | Resource revision most recently read by the frontend; minimum: 0 |

<a id="model-privacy"></a>

### Privacy

| Field | Type / allowed values | Required | Description and constraints |
|---|---|---|---|
| `revision` | integer | Yes | Current resource version, independent of other resources; minimum: 0 |
| `discoverable` | boolean | Yes | Consent to discovery by teams; defaults to false |
| `visibleFields` | [ProfileField](#model-profilefield)[] | Yes | Whitelist of fields teams may see and use for matching; empty for new accounts; unique items |
| `updatedAt` | string | Yes | Last update time in UTC; format: date-time |

<a id="model-privacywrite"></a>

### PrivacyWrite

| Field | Type / allowed values | Required | Description and constraints |
|---|---|---|---|
| `expectedRevision` | integer | Yes | Resource revision most recently read by the frontend; minimum: 0 |
| `discoverable` | boolean | Yes | Consent to discovery by teams; defaults to false |
| `visibleFields` | [ProfileField](#model-profilefield)[] | Yes | Whitelist of fields teams may see and use for matching; empty for new accounts; unique items |

<a id="model-fielderror"></a>

### FieldError

| Field | Type / allowed values | Required | Description and constraints |
|---|---|---|---|
| `field` | string | Yes | Associated field or section |
| `message` | string | Yes | Displayable explanation; do not branch on its wording |

<a id="model-errordetail"></a>

### ErrorDetail

| Field | Type / allowed values | Required | Description and constraints |
|---|---|---|---|
| `code` | `UNAUTHENTICATED` / `INVALID_CREDENTIALS` / `FORBIDDEN` / `CSRF_INVALID` / `NOT_FOUND` / `VALIDATION_ERROR` / `REVISION_CONFLICT` / `PROFILE_UNCONFIRMED` / `EXTRACTION_NOT_READY` / `EXTRACTION_FAILED` / `UPLOAD_TOO_LARGE` / `UNSUPPORTED_FILE_TYPE` / `RATE_LIMITED` / `INTERNAL_ERROR` / `BAD_REQUEST` / `UNSUPPORTED_MEDIA_TYPE` | Yes | Course code; null if unknown. In an error object, this is the error code |
| `message` | string | Yes | Displayable explanation; do not branch on its wording |
| `fieldErrors` | [FieldError](#model-fielderror)[] | Yes | Field validation problems; empty if none |
| `currentRevision` | integer | No | Server revision on conflict; omitted for other errors; minimum: 0 |

<a id="model-error"></a>

### Error

| Field | Type / allowed values | Required | Description and constraints |
|---|---|---|---|
| `error` | [ErrorDetail](#model-errordetail) | Yes | Error details; null for a Document unless status is FAILED |
| `requestId` | string | Yes | Server-generated identifier for investigating a request |

<a id="model-document"></a>

### Document

| Field | Type / allowed values | Required | Description and constraints |
|---|---|---|---|
| `id` | string | Yes | Object identifier; preserve IDs when editing existing records; pattern: `^[A-Za-z0-9_-]{1,64}$` |
| `kind` | `CV` / `TRANSCRIPT` | Yes | Category; use the specified enum values |
| `fileName` | string | Yes | Original filename, visible only to its owner |
| `mediaType` | `application/pdf` / `application/vnd.openxmlformats-officedocument.wordprocessingml.document` | Yes | Actual file MIME type |
| `sizeBytes` | integer | Yes | File size in bytes; minimum: 1; maximum: 10485760 |
| `status` | `QUEUED` / `PROCESSING` / `READY` / `FAILED` | Yes | Status enum; see the relevant business rules |
| `createdAt` | string | Yes | Creation timestamp; format: date-time |
| `updatedAt` | string | Yes | Last update time in UTC; format: date-time |
| `error` | [ErrorDetail](#model-errordetail) / null | Yes | Error details; null for a Document unless status is FAILED |

<a id="model-uncertainfield"></a>

### UncertainField

| Field | Type / allowed values | Required | Description and constraints |
|---|---|---|---|
| `field` | `education` / `courses` / `researchExperience` / `skills` / `researchInterests` / `researchOutputs` | Yes | Associated field or section |
| `status` | `UNKNOWN` / `NOT_RECOGNISED` | Yes | Status enum; see the relevant business rules |
| `reason` | string | Yes | Displayable explanation based only on evidence the caller may use |

<a id="model-extraction"></a>

### Extraction

suggestedSections may be empty. In that case, show uncertainty and manual entry rather than sending an empty sections import. Extraction completion, importing and profile confirmation are separate stages.

| Field | Type / allowed values | Required | Description and constraints |
|---|---|---|---|
| `documentId` | string | Yes | Owner-only document source reference; null for manual input; never disclosed to research teams; pattern: `^[A-Za-z0-9_-]{1,64}$` |
| `status` | `READY` | Yes | Status enum; see the relevant business rules |
| `suggestedSections` | object (optional subset of six sections) | Yes | Any subset of the six profile sections, including an empty object; same field shapes as ProfileSections without the minimum-one-field requirement |
| `uncertainFields` | [UncertainField](#model-uncertainfield)[] | Yes | Sections that could not be reliably extracted, with reasons |
| `warnings` | string[] | Yes | Review guidance |
| `reviewRequired` | `true` | Yes | Always true; extraction suggestions require user review |

<a id="model-applyextractionrequest"></a>

### ApplyExtractionRequest

| Field | Type / allowed values | Required | Description and constraints |
|---|---|---|---|
| `expectedProfileRevision` | integer | Yes | Owner profile revision read before importing; minimum: 0 |
| `sections` | [ProfileSections](#model-profilesections) | Yes | Replace submitted sections only; omitted sections stay unchanged and [] explicitly clears a section |

<a id="model-requirement"></a>

### Requirement

This version deterministically evaluates SKILL and INTEREST tag requirements. Education, courses and outputs may be displayed as profile information, but free text is not used to invent skill evidence.

| Field | Type / allowed values | Required | Description and constraints |
|---|---|---|---|
| `id` | string | Yes | Object identifier; preserve IDs when editing existing records; pattern: `^[A-Za-z0-9_-]{1,64}$` |
| `label` | string | Yes | Human-readable label; minimum length: 1; maximum length: 300 |
| `kind` | `SKILL` / `INTEREST` | Yes | Category; use the specified enum values |
| `importance` | `REQUIRED` / `PREFERRED` | Yes | REQUIRED or PREFERRED |
| `tagIds` | string[] | Yes | AND group within a requirement; each tag kind must match kind; minimum items: 1; maximum items: 20; unique items |

<a id="model-opportunitycontent"></a>

### OpportunityContent

Published opportunities require at least one requirement. Drafts may have an empty requirements array, but basic text fields are still required. This version has no closed/deleted/application states.

| Field | Type / allowed values | Required | Description and constraints |
|---|---|---|---|
| `title` | string | Yes | Title; minimum length: 1; maximum length: 200 |
| `university` | string | Yes | University offering the opportunity; minimum length: 1; maximum length: 200 |
| `disciplineGroup` | `STEM` / `BUSINESS` | Yes | STEM or BUSINESS; nullable for talent who has not selected a group |
| `discipline` | string | Yes | Discipline name; minimum length: 1; maximum length: 200 |
| `researchArea` | string | Yes | Research area name; minimum length: 1; maximum length: 300 |
| `description` | string | Yes | Plain-text description; minimum length: 1; maximum length: 10000 |
| `requirements` | [Requirement](#model-requirement)[] | Yes | Requirements; may be empty in a draft, but publication requires at least one; maximum items: 50 |

<a id="model-opportunity"></a>

### Opportunity

| Field | Type / allowed values | Required | Description and constraints |
|---|---|---|---|
| `id` | string | Yes | Object identifier; preserve IDs when editing existing records; pattern: `^[A-Za-z0-9_-]{1,64}$` |
| `revision` | integer | Yes | Current resource version, independent of other resources; minimum: 0 |
| `status` | `DRAFT` / `PUBLISHED` | Yes | Status enum; see the relevant business rules |
| `content` | [OpportunityContent](#model-opportunitycontent) | Yes | Business content of the resource |
| `createdAt` | string | Yes | Creation timestamp; format: date-time |
| `updatedAt` | string | Yes | Last update time in UTC; format: date-time |

<a id="model-opportunitywrite"></a>

### OpportunityWrite

| Field | Type / allowed values | Required | Description and constraints |
|---|---|---|---|
| `expectedRevision` | integer | Yes | Resource revision most recently read by the frontend; minimum: 0 |
| `content` | [OpportunityContent](#model-opportunitycontent) | Yes | Business content of the resource |

<a id="model-matchstatus"></a>

### MatchStatus

Type: `MATCHED` / `PARTIAL` / `GAP` / `UNKNOWN`. .

<a id="model-ownerevidence"></a>

### OwnerEvidence

Used only for the talent owner’s match details. documentId is a source reference, not a public link. MANUAL sourceType requires documentId=null.

| Field | Type / allowed values | Required | Description and constraints |
|---|---|---|---|
| `field` | [ProfileField](#model-profilefield) | Yes | Associated field or section |
| `recordId` | string | Yes | Evidence record ID; tagId for skills/interests and child record id for other sections; pattern: `^[A-Za-z0-9_-]{1,64}$` |
| `valueSummary` | string | Yes | Brief evidence text without invented facts |
| `confirmedRevision` | integer | Yes | Confirmed revision; null while unconfirmed; minimum: 0 |
| `sourceType` | `MANUAL` / `USER_REVIEWED_DOCUMENT` | Yes | Server-maintained origin: MANUAL or USER_REVIEWED_DOCUMENT |
| `documentId` | string / null | Yes | Owner-only document source reference; null for manual input; never disclosed to research teams; pattern: `^[A-Za-z0-9_-]{1,64}$` |

<a id="model-teamevidence"></a>

### TeamEvidence

A reduced shape compared with OwnerEvidence: no documentId, sourceType or confirmedRevision. Evidence must come from currently shared fields, and explanation text must not disclose hidden information.

| Field | Type / allowed values | Required | Description and constraints |
|---|---|---|---|
| `field` | [ProfileField](#model-profilefield) | Yes | Associated field or section |
| `recordId` | string | Yes | Evidence record ID; tagId for skills/interests and child record id for other sections; pattern: `^[A-Za-z0-9_-]{1,64}$` |
| `valueSummary` | string | Yes | Brief evidence text without invented facts |

<a id="model-ownerrequirementresult"></a>

### OwnerRequirementResult

| Field | Type / allowed values | Required | Description and constraints |
|---|---|---|---|
| `requirement` | [Requirement](#model-requirement) | Yes | Complete original requirement object |
| `status` | [MatchStatus](#model-matchstatus) | Yes | Status enum; see the relevant business rules |
| `reasonCode` | `ALL_TAGS_SUPPORTED` / `SOME_TAGS_SUPPORTED` / `EXPLICIT_NEGATIVE_CLAIM` / `INSUFFICIENT_EVIDENCE` | Yes | Stable explanation category for frontend use |
| `reason` | string | Yes | Displayable explanation based only on evidence the caller may use |
| `evidence` | [OwnerEvidence](#model-ownerevidence)[] | Yes | Evidence records; must be empty for UNKNOWN |

<a id="model-teamrequirementresult"></a>

### TeamRequirementResult

| Field | Type / allowed values | Required | Description and constraints |
|---|---|---|---|
| `requirement` | [Requirement](#model-requirement) | Yes | Complete original requirement object |
| `status` | [MatchStatus](#model-matchstatus) | Yes | Status enum; see the relevant business rules |
| `reasonCode` | `ALL_TAGS_SUPPORTED` / `SOME_TAGS_SUPPORTED` / `EXPLICIT_NEGATIVE_CLAIM` / `INSUFFICIENT_EVIDENCE` | Yes | Stable explanation category for frontend use |
| `reason` | string | Yes | Displayable explanation based only on evidence the caller may use |
| `evidence` | [TeamEvidence](#model-teamevidence)[] | Yes | Evidence records; must be empty for UNKNOWN |

<a id="model-matchsummary"></a>

### MatchSummary

Display the backend summary rather than recalculating from a page of results. Values use two decimal places. The product may choose whether to display numeric scores, but must preserve ranking and requirement-level explanations.

| Field | Type / allowed values | Required | Description and constraints |
|---|---|---|---|
| `score` | number / null | Yes | Weighted evidence coverage from 0 to 100, not an admission probability; null if there are no criteria; minimum: 0; maximum: 100 |
| `unknownWeightPercent` | number / null | Yes | Percentage of requirement weight classified UNKNOWN; null if there are no criteria; minimum: 0; maximum: 100 |
| `requiredGapCount` | integer | Yes | Number of REQUIRED requirements classified GAP; minimum: 0 |
| `evaluationStatus` | `EVALUATED` / `INSUFFICIENT_CRITERIA` | Yes | Evaluated or insufficient criteria |
| `algorithmVersion` | `tag-coverage-v1` | Yes | Version of the matching rules |

<a id="model-ownermatch"></a>

### OwnerMatch

| Field | Type / allowed values | Required | Description and constraints |
|---|---|---|---|
| `opportunity` | [Opportunity](#model-opportunity) | Yes | Complete opportunity object |
| `profileRevision` | integer | Yes | Confirmed profile revision used for this evaluation; minimum: 0 |
| `summary` | [MatchSummary](#model-matchsummary) | Yes | Matching overview |
| `requirements` | [OwnerRequirementResult](#model-ownerrequirementresult)[] | Yes | Requirements; may be empty in a draft, but publication requires at least one |
| `evaluatedAt` | string | Yes | Evaluation timestamp; format: date-time |

<a id="model-visibleprofile"></a>

### VisibleProfile

fields may contain any subset of ProfileContent fields, all optional. Present values follow the corresponding ProfileContent types. If displayName is absent, display “Anonymous talent”; do not bypass visibility through another endpoint to retrieve the name.

| Field | Type / allowed values | Required | Description and constraints |
|---|---|---|---|
| `talentId` | string | Yes | Talent identifier assigned by the backend; pattern: `^[A-Za-z0-9_-]{1,64}$` |
| `fields` | object (subset of [ProfileContent](#model-profilecontent) fields) | Yes | Only permitted ProfileContent fields; omit hidden keys entirely |

<a id="model-teammatch"></a>

### TeamMatch

| Field | Type / allowed values | Required | Description and constraints |
|---|---|---|---|
| `opportunityId` | string | Yes | Opportunity being evaluated; pattern: `^[A-Za-z0-9_-]{1,64}$` |
| `opportunityRevision` | integer | Yes | Opportunity revision used for the evaluation; minimum: 0 |
| `talent` | [VisibleProfile](#model-visibleprofile) | Yes | Filtered, visible talent profile |
| `summary` | [MatchSummary](#model-matchsummary) | Yes | Matching overview |
| `requirements` | [TeamRequirementResult](#model-teamrequirementresult)[] | Yes | Requirements; may be empty in a draft, but publication requires at least one |
| `evaluatedAt` | string | Yes | Evaluation timestamp; format: date-time |

<a id="model-recommendationitem"></a>

### RecommendationItem

| Field | Type / allowed values | Required | Description and constraints |
|---|---|---|---|
| `rank` | integer | Yes | Global rank before pagination, starting at 1; minimum: 1 |
| `opportunity` | [Opportunity](#model-opportunity) | Yes | Complete opportunity object |
| `summary` | [MatchSummary](#model-matchsummary) | Yes | Matching overview |

<a id="model-talentmatchitem"></a>

### TalentMatchItem

| Field | Type / allowed values | Required | Description and constraints |
|---|---|---|---|
| `rank` | integer | Yes | Global rank before pagination, starting at 1; minimum: 1 |
| `talent` | [VisibleProfile](#model-visibleprofile) | Yes | Filtered, visible talent profile |
| `summary` | [MatchSummary](#model-matchsummary) | Yes | Matching overview |

<a id="model-opportunitypage"></a>

### OpportunityPage

| Field | Type / allowed values | Required | Description and constraints |
|---|---|---|---|
| `items` | [Opportunity](#model-opportunity)[] | Yes | Current page items; for tags, the complete vocabulary result |
| `page` | integer | Yes | Current page number; minimum: 1 |
| `pageSize` | integer | Yes | Maximum items per page; minimum: 1; maximum: 100 |
| `total` | integer | Yes | Total number of accessible results; minimum: 0 |

<a id="model-documentpage"></a>

### DocumentPage

| Field | Type / allowed values | Required | Description and constraints |
|---|---|---|---|
| `items` | [Document](#model-document)[] | Yes | Current page items; for tags, the complete vocabulary result |
| `page` | integer | Yes | Current page number; minimum: 1 |
| `pageSize` | integer | Yes | Maximum items per page; minimum: 1; maximum: 100 |
| `total` | integer | Yes | Total number of accessible results; minimum: 0 |

<a id="model-recommendationpage"></a>

### RecommendationPage

| Field | Type / allowed values | Required | Description and constraints |
|---|---|---|---|
| `items` | [RecommendationItem](#model-recommendationitem)[] | Yes | Current page items; for tags, the complete vocabulary result |
| `page` | integer | Yes | Current page number; minimum: 1 |
| `pageSize` | integer | Yes | Maximum items per page; minimum: 1; maximum: 100 |
| `total` | integer | Yes | Total number of accessible results; minimum: 0 |

<a id="model-talentmatchpage"></a>

### TalentMatchPage

| Field | Type / allowed values | Required | Description and constraints |
|---|---|---|---|
| `items` | [TalentMatchItem](#model-talentmatchitem)[] | Yes | Current page items; for tags, the complete vocabulary result |
| `page` | integer | Yes | Current page number; minimum: 1 |
| `pageSize` | integer | Yes | Maximum items per page; minimum: 1; maximum: 100 |
| `total` | integer | Yes | Total number of accessible results; minimum: 0 |

## 7. Business rules and call sequences

### 7.1 Manual profile entry

```text
GET /auth/session → POST /auth/login
GET /tags + GET /me/profile
Edit the local form
PUT /me/profile (expectedRevision + complete content)
Read the new revision and UNCONFIRMED state
User reviews → POST /me/profile/confirmation (new revision)
GET /me/recommendations → GET /me/opportunity-matches/{opportunityId}
```

Privacy-only changes do not require profile reconfirmation. Content changes suspend the entire profile from matching until the user confirms its current revision. This version does not mix individually confirmed and unconfirmed fields in one evaluation.

### 7.2 Document extraction alongside manual entry

```text
POST /me/documents → 202 QUEUED
GET /me/documents/{documentId} → PROCESSING → READY / FAILED
READY → GET /me/documents/{documentId}/extraction
User selects sections and corrects/removes inaccurate suggestions
GET /me/profile (read current content and revision)
POST /me/documents/{documentId}/apply (expectedProfileRevision + sections)
New UNCONFIRMED profile → user reviews → POST /me/profile/confirmation
```

- Show which sections the import will replace. To merge old and new skills, combine them locally by tagId, let the user review and submit the complete merged skills array.
- An extraction response must not overwrite a form the user is currently editing. Submit the last known revision and handle conflicts through comparison, not silent replacement.
- `READY` means extraction completed, not that the user confirmed it or that it is accurate.
- `UNKNOWN` means the value cannot be determined; `NOT_RECOGNISED` means no reliable information was identified. Neither becomes an affirmative or negative skill claim automatically.
- Keep manual entry available after extraction failure. v0.1 has no separate extraction retry endpoint; uploading again starts a new attempt.

### 7.3 Team opportunities and talent discovery

```text
Team login → GET /opportunities?scope=mine
GET /tags → POST /opportunities (create DRAFT)
PUT /opportunities/{opportunityId} (edit)
POST /opportunities/{opportunityId}/publish (current revision)
GET /opportunities/{opportunityId}/talent-matches
GET /opportunities/{opportunityId}/talent-matches/{talentId}
```

Create a draft and then publish it; creation does not accept status=PUBLISHED. Teams use the VisibleProfile in match details rather than a new full-profile `/talents/{id}` endpoint that could bypass visibility controls.

### 7.4 Apply privacy before calculating matches

Owner recommendations use the talent’s complete current confirmed profile. The talent may still receive recommendations when discoverable=false.

For team-facing reverse matching:

1. Verify that the team owns the published opportunity.
2. Exclude talent with discoverable=false or an unconfirmed current revision.
3. Select only fields allowed by visibleFields.
4. Compute statuses, scores and explanations from those fields, then rank, paginate and count total.
5. Return VisibleProfile and TeamEvidence. Recheck permission on every list/detail request. Any result cache must be invalidated when profile, opportunity or privacy revisions change.

For example, a talent may receive a score of 50 in their own view. If they share only their name, the team view has all requirements UNKNOWN, score=0 and unknownWeightPercent=100. Different evidence permissions legitimately produce different results. **Do not calculate a score from private skills and merely hide those skills in the interface.**

Original CVs/transcripts, raw extracted text, file provenance and login email are not part of the visible-field whitelist. Wording such as “this user hid Python” would disclose private information. Missing and hidden evidence must use the same generic explanation.

Revocation affects subsequent responses; it cannot retract information that another person has already seen or saved. Refetch when the team page is entered, refreshed or focused rather than retaining stale results indefinitely.

### 7.5 Deterministic status rules

Use only authorised information from a confirmed revision. Multiple tagIds in one requirement form an AND group. SKILL requirements look up claims in skills; INTEREST requirements look up researchInterests. Other sections do not automatically imply tags in v0.1.

Evaluate in this order:

| Priority | Condition | status | reasonCode |
|---|---|---|---|
| 1 | Any requested skill has an explicit DOES_NOT_HAVE claim | GAP | EXPLICIT_NEGATIVE_CLAIM |
| 2 | Every requested tag has affirmative evidence | MATCHED | ALL_TAGS_SUPPORTED |
| 3 | Some tags have affirmative evidence and the rest are unknown | PARTIAL | SOME_TAGS_SUPPORTED |
| 4 | No usable affirmative or explicit negative evidence | UNKNOWN | INSUFFICIENT_EVIDENCE |

Thus an AND requirement with “has Python” and “explicitly does not have SQL” is GAP. “Has Python” with no SQL information is PARTIAL. No information for either is UNKNOWN. Unconfirmed profiles never enter matching. Missing documents, omitted skills or hidden skills must not automatically become GAP.

MATCHED/PARTIAL evidence cites actual supporting claims; GAP cites the explicit negative claim; UNKNOWN has evidence=[]. An interest uses its tagId as recordId. If evidenceText is empty, the explanation may cite the user’s confirmed tag claim, but cannot invent project or course experience.

### 7.6 Scores and ranking

```text
Requirement weight w: REQUIRED = 2; PREFERRED = 1
Status value v: MATCHED = 1; PARTIAL = 0.5; GAP = 0; UNKNOWN = 0

score = round_half_up(100 × sum(w × v) / sum(w), 2)
unknownWeightPercent = round_half_up(100 × sum(w for UNKNOWN) / sum(w), 2)
requiredGapCount = count(requirements where importance=REQUIRED and status=GAP)
```

Use decimal half-up rounding to two places; Python can use Decimal with ROUND_HALF_UP to avoid differences between language defaults. The frontend does not recalculate authoritative scores. If total weight is zero, both score and unknownWeightPercent are null and evaluationStatus=INSUFFICIENT_CRITERIA; never divide by zero or return NaN. Publication rejects empty requirements, so this branch protects against legacy data.

Example: Python REQUIRED is MATCHED (weight 2); Python+SQL REQUIRED is PARTIAL (weight 2); interviews PREFERRED is GAP (weight 1); R PREFERRED is UNKNOWN (weight 1). The result is score=50, unknownWeightPercent=16.67 and requiredGapCount=0. Endpoint 22 contains the complete response.

In this version, REQUIRED increases weight and exposes an explicit gap count; it does not automatically exclude candidates with a GAP. Changing that eligibility rule requires a coordinated algorithm-version and fixture update. Scores represent evidence coverage, not admission probability or verified credentials.

## 8. JavaScript / Python integration examples

### 8.1 JavaScript request adapter

This snippet demonstrates the protocol only. The actual frontend also needs loading states, field errors, session-expiry handling and request cancellation.

```javascript
let csrfToken = '';

async function apiRequest(path, { method = 'GET', body } = {}) {
  const headers = { Accept: 'application/json' };
  const isForm = body instanceof FormData;
  if (body && !isForm) headers['Content-Type'] = 'application/json';
  if (method !== 'GET') headers['X-CSRF-Token'] = csrfToken;

  const response = await fetch(`/api/v1${path}`, {
    method,
    credentials: 'include',
    headers,
    body: body ? (isForm ? body : JSON.stringify(body)) : undefined,
  });
  if (response.status === 204) return;
  const result = await response.json();
  if (!response.ok) {
    const error = new Error(result.error.message);
    Object.assign(error, result.error, { status: response.status });
    throw error;
  }
  if (result.csrfToken) csrfToken = result.csrfToken;
  return result;
}

await apiRequest('/auth/session');
await apiRequest('/auth/login', {
  method: 'POST',
  body: { email: 'talent@example.test', password: '<provisioned-test-account-password>' },
});
const profile = await apiRequest('/me/profile');
const content = structuredClone(profile.content);
content.displayName = 'Demo Talent A';
const saved = await apiRequest('/me/profile', {
  method: 'PUT',
  body: { expectedRevision: profile.revision, content },
});
// Run only after the user has reviewed the content and selected Confirm:
await apiRequest('/me/profile/confirmation', {
  method: 'POST', body: { expectedRevision: saved.revision },
});
```

### 8.2 Python backend requirements

The contract does not prescribe a Python web framework or database. The implementation must:

- Keep external JSON names in camelCase. Return UTC strings and JSON boolean/null values, not raw datetime or database model objects.
- Identify the account and resource owner from the session. Do not trust client-supplied talentId, ownerId, role or confirmation state.
- Check revisions and update within a transaction. Reading a revision followed by an unconditional UPDATE does not prevent concurrent overwrites.
- Store uploads privately without public static URLs. Endpoint 15 rechecks ownership before downloads.
- Expose extraction status and results through the agreed endpoints. The backend may use its framework’s background processing facilities without exposing queue details to the frontend.
- Construct separate response shapes for each audience: OwnerEvidence for the talent owner, TeamEvidence for teams. Do not send complete profiles for the frontend to filter.
- Implement confirmation, privacy and scoring centrally on the backend to avoid divergent frontend rules.
- Convert validation and framework errors into the Error structure in section 5, including a Python framework’s default 422 output.

## 9. Integration acceptance cases

| Case | Expected result |
|---|---|
| Open the app while logged out | Session returns 200 with user=null; private endpoints return 401 |
| Talent/team login | Correct role returned; endpoints for other roles reject access |
| New talent profile | revision=0, unconfirmed and not discoverable by default |
| Save and reread a profile | Content agrees; refresh retrieves the saved backend values |
| Edit a confirmed profile | Becomes unconfirmed; recommendations return 409 until reconfirmed |
| Edit from two pages | Stale save returns 409 without overwriting newer content |
| Change privacy only | Profile confirmation is preserved; privacy revision changes independently |
| Upload PDF/DOCX | 202 is followed by queryable processing and terminal states |
| Oversized/unsupported upload | 413 / 415 respectively; existing profile is preserved |
| Failed or uncertain extraction | Manual entry remains available; no automatic confirmed facts |
| Import reviewed sections | Only selected sections are replaced; others remain; result is unconfirmed |
| Create, edit and publish an opportunity | Only published opportunities enter recommendations; no publication without requirements |
| Four match statuses | A synthetic case displays MATCHED / PARTIAL / GAP / UNKNOWN |
| Missing/hidden skills | No fabricated evidence and no automatic GAP |
| Team views talent | Only opted-in talent with a confirmed current profile appears |
| Name/skills are private | Corresponding keys are omitted; hidden skills do not affect team scores |
| Talent revokes discovery | Absent from the next list; old detail URL returns 404 |
| Team requests an original document | Denied; matching responses contain no original-file links or provenance IDs |
| Pagination, ordering and empty lists | Global ranks, permission-filtered total and 200 for empty results |
| Logout and log in as another account | No previous account profile or match cache remains |

US-06 prepares synthetic/de-identified data and records these test results. No additional public management API is needed for testing. The examples establish contract structure; they do not demonstrate that a real backend or the whole product has passed integration acceptance.

## 10. Later scope

US-10 through US-16 remain in the Backlog: broader file/confirmation protection, systematic quality evaluation, favourites, semantic matching, advanced search, full registration/identity management and whole-project testing. Overlapping privacy and testing foundations are specified for this Sprint without bringing all those later stories into scope.

When adding capabilities, update the contract version, field definitions, mock fixtures and tests before coordinating both implementations. Do not unilaterally change field casing, enums, replacement semantics, confirmation granularity or the use of hidden fields in scoring.

## 11. Companion files and references

- [openapi.json](openapi.json): the corresponding OpenAPI 3.1.0 definition for tooling and validation.
- [endpoint-index.json](endpoint-index.json): methods, paths and related Jira tasks for all 24 operations.
- [examples/](examples/): 30 synthetic request/response fixtures; [index.json](examples/index.json) maps each fixture to its model.
- Business inputs: the Sprint 1 Jira work items provided in the discussion, `Client_Meeting_Minutes_2026-09-30.docx` and the Week 3 meeting minutes in the working folder. No unprovided backend implementation is assumed to exist.
- Format reference: [OpenAPI 3.1.0 specification](https://spec.openapis.org/oas/v3.1.0.html). Cookie attributes: [MDN Set-Cookie](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Set-Cookie).

After the team agrees on the defaults in section 1.3, the version can be promoted to `0.1.0` for parallel development. Until then, mock endpoints should follow this draft’s fields rather than introduce inconsistent structures while building pages.
