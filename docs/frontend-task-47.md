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

The backend README proposes `content.sourceUrl`: an optional HTTP/HTTPS URL,
up to 2048 characters. Sending `null` removes the link. When this frontend work
was added, the backend and OpenAPI did not support saving this field yet.

The US-19 backend is now merged into main and accepts this field. The frontend build flag still defaults to false.
After deploying the US-19 backend, enable it in the repository root `.env`:

```text
VITE_OPPORTUNITY_SOURCE_URLS=true
```

Then run `docker compose up -d --build frontend`. Both Compose files pass this
setting as a build argument. Dockerfile applies it before `pnpm build`; changing
a running container's environment without rebuilding will not change the UI.
For native Vite development, use the same setting in `frontend/.env` and restart.
Do not copy `.env` into the image; the build needs only this non-secret flag.

With the flag enabled, new records and records whose link has been cleared both
show the input, even when the API omits `sourceUrl`. Empty input sends explicit
`null`; unchanged older records do not acquire a source URL field automatically.
Valid links open in a new tab with `noopener noreferrer`. Adding a link does not
fetch or import anything from that website.

`us19-source-live.mjs` checks create, edit, clear, reload and re-add through the
React editor and real HTTP API. It also checks a talent's read-only link and
rejected writes by a different team. Run it with:

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
