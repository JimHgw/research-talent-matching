# US-19 opportunity source URLs

The existing opportunity POST/PUT/GET/list routes accept optional `content.sourceUrl`.
Use an absolute HTTP or HTTPS URL, up to 2048 characters. Omission preserves a
stored URL on update; explicit null removes it. Unset URLs are omitted on reads.
The saved destination is returned unchanged, including query strings and fragments.
Invalid URLs receive 422, `VALIDATION_ERROR`, and a clear `content.sourceUrl` message.
Unicode IRIs are supported. Whitespace, controls, backslashes, credentials, missing
hosts, invalid ports and unsupported schemes are rejected without fetching the URL.
There is no domain allowlist, scraper, import, confirmation or matching integration.
Existing ownership, CSRF and expected-revision checks apply unchanged.

## Existing databases

Use the existing database configuration and retain its backup. Stop API/worker writes
before applying the deployment upgrade:

```sh
.venv/bin/python -m flask --app backend.app init-db
.venv/bin/python -m flask --app backend.app upgrade-opportunity-search
```

The additive upgrade creates nullable `opportunities.source_url VARCHAR(2048)`;
existing records remain intact, and rerunning it is harmless. The existing Docker
entrypoint already runs this command. API and worker should deploy the same version.
No database or volume deletion is needed.

## Verification and frontend integration

```sh
.venv/bin/python -m pytest backend/tests/test_us19.py backend/tests/test_us02.py backend/tests/test_us14.py -q
```

Use a disposable `_test` database through `MYSQL_TEST_DATABASE_URL` and add
`--run-mysql` to exercise the same source-column upgrade against MySQL 8.4.
Tests cover create/edit/remove/legacy omission, exact destination round trips,
process restart, clear invalid-input errors, permissions, conflicts, old-table
upgrades and unchanged matching evidence. Source links perform no HTTP fetching.

Enable the existing frontend input with `VITE_OPPORTUNITY_SOURCE_URLS=true`, then
restart the dev server or rebuild. Existing UI components already render valid
links in a separate tab with `noopener noreferrer`, and omit unset links.
`frontend/tests/us19-live.mjs` currently covers generic opportunity lifecycle and
conflict handling; it does not yet prove source-link editing/opening through real
HTTP. Verify the source-specific flow before claiming full UI acceptance.
