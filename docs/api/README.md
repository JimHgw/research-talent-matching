# Sprint 1 API contract

Proposed API contract for the H18ABANANA JavaScript frontend and Python backend.
Version: `0.1.0-draft`. Covers US-01–US-09 with 24 HTTP operations.

## Start here

- [Complete API contract](sprint-1-api-contract.md): request/response fields, examples, permissions, errors, workflows and integration acceptance cases. All documentation and examples are in English.
- [OpenAPI 3.1 definition](openapi.json): machine-readable paths and 47 public schemas.
- [Endpoint index](endpoint-index.json): HTTP operations and related Jira implementation tasks.
- [Example index](examples/index.json): maps 30 synthetic JSON fixtures to their schemas.

## Review before implementation

Section 1.3 of the contract lists proposed decisions that need team agreement,
including session authentication, whole-profile confirmation, upload limits and
matching weights. This is a design contract; it does not claim the backend is
implemented or the product has passed integration testing.

Only the current confirmed profile revision may be used for matching. Team-facing
matching must filter by discovery consent and field visibility **before** calculating
scores or producing evidence. Original uploaded documents remain owner-only.

## Validation

The OpenAPI document and the 30 JSON fixtures were schema-validated during
preparation. The full Markdown contract includes integration cases for backend
implementation. All example accounts, credentials and profile data are placeholders
or synthetic data.

Keep this contract, the OpenAPI definition and the examples aligned when changing
an endpoint. Backlog features beyond Sprint 1 are not included in this version.
