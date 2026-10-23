# Sprint 1 API contract

Proposed API contract for the H18ABANANA JavaScript frontend and Python backend.
Version: `0.1.2-draft`. Covers US-01–US-09 with 29 HTTP operations.

## Start here

- [Complete API contract](sprint-1-api-contract.md): request/response fields, examples, permissions, errors, workflows and integration acceptance cases. All documentation and examples are in English.
- [OpenAPI 3.1 definition](openapi.json): machine-readable paths and public schemas.
- [Endpoint index](endpoint-index.json): HTTP operations and related Jira implementation tasks.
- [Example index](examples/index.json): maps 42 synthetic JSON fixtures to their schemas.

## Review before implementation

Section 1.3 of the contract lists proposed decisions that need team agreement,
including session authentication, whole-profile confirmation, upload limits and
matching weights. This is a design contract; it does not claim the backend is
implemented or the product has passed integration testing.

Only the current confirmed profile revision may be used for matching. Team-facing
matching must filter by discovery consent and field visibility **before** calculating
scores or producing evidence. Original uploaded documents remain owner-only.

## Validation

The OpenAPI document and the 42 JSON fixtures were schema-validated during
preparation. The full Markdown contract includes integration cases for backend
implementation. All example accounts, credentials and profile data are placeholders
or synthetic data.

Keep this contract, the OpenAPI definition and the examples aligned when changing
an endpoint. Implemented extensions are documented below; other backlog features remain outside this baseline.

US-01 now includes [verified-email registration and email/ID login](../us01-registration.md). `POST /auth/register/code` sends a six-digit code; `POST /auth/register` creates either supported account role after verification. Existing provisioned accounts remain supported.

US-01 also includes [password rules and both password-reset methods](../us01-password-reset.md): original-password verification or staged email-code verification, confirmation, and session revocation.

US-11 adds [resume tags, free text and a unified owner-only description](../us11-resume-extraction.md), including optional compatible profile/import fields, personal labels and per-component provenance. Existing methods and paths are retained.

Skills now use [free-text titles and supporting evidence](../free-text-skills.md)
with record IDs, replacing the skill-tag/claim shape in profile, extraction and
team-visible records. Deploy the API and frontend together; legacy stored data
and old READY results have read adapters.
