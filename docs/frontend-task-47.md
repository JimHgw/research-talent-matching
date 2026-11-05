# Task 47: opportunity pages

This task builds on the opportunity pages from Sprint 1 and uses the existing
US-14 APIs for search and deadlines.

## Changes

- Show the filters that have been applied. If the end date is the same as or
  earlier than the start date, show an error before sending the search request.
- Use the same component to show source links and deadlines on lists and details.
  Dates are shown in the user's time zone. Requests still send UTC values.
- Add a "Save and reopen opportunity" button. Owners can change the deadline
  and reopen an expired opportunity in one request. The deadline must be in the
  future or left empty. Saving normally keeps the opportunity expired.
- Keep the existing checks for repeated submissions and version conflicts.
  Read-only details reload when the user returns to the window. The backend
  decides whether an opportunity is active or expired.

## Source links

The US-19 backend on main accepts `content.sourceUrl`: an optional HTTP/HTTPS URL,
up to 2048 characters. Sending `null` removes the link.

The input is now enabled by default in Vite, Dockerfile and both Compose files.
After updating, run `docker compose up -d --build frontend`. If an existing root
`.env`, frontend `.env` or shell still sets `VITE_OPPORTUNITY_SOURCE_URLS=false`,
remove that override or change it to `true`. Native Vite needs a restart;
Docker needs a rebuild because the setting is read during `pnpm build`.
Keep an explicit `false` only when using an older API without US-19 support.
Do not copy `.env` into the image; the build needs only this non-secret flag.

New records and records whose link has been cleared both show the input by
default, even when the API omits `sourceUrl`. Empty input sends explicit
`null`; unchanged older records do not acquire a source URL field automatically.
Valid links open in a new tab with `noopener noreferrer`. Adding a link does not
fetch or import anything from that website.

`us19-source-live.mjs` checks create, edit, clear, reload and re-add through the
React editor and real HTTP API without setting the feature flag. It also checks
a talent's read-only link and rejected writes by a different team. Run it with:

```text
python -m pytest backend/tests/test_frontend_integration.py -k 19-source --require-frontend
```

This test skips explicitly until the backend's OpenAPI includes `sourceUrl`.
To test MySQL, add `--run-mysql` and configure `MYSQL_TEST_DATABASE_URL` for an
isolated database ending in `_test`, as required by the existing test fixtures.

## Tests

Run these commands in `frontend`:

```text
pnpm test:47
pnpm test
pnpm build
pnpm format:check
```

The task tests cover source URLs, deadline boundaries, reopening, version
conflicts and old search responses arriving late. The existing US-14 tests
already cover combined filters, pagination, clearing filters and error/empty
results. These cases can also be used for task 51.
