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

## Source links still need BE-56

The backend README proposes `content.sourceUrl`: an optional HTTP/HTTPS URL,
up to 2048 characters. Sending `null` removes the link. When this frontend work
was added, the backend and OpenAPI did not support saving this field yet.

The input is hidden by default for older records. Once BE-56 is available, set
`VITE_OPPORTUNITY_SOURCE_URLS=true` and restart the dev server or rebuild.
Records that already return a `sourceUrl` field also show the input. Older
records keep this field out of ordinary save requests.

Valid links open in a new tab with `noopener noreferrer`. Empty or invalid links
are not shown. Adding a link does not fetch or import anything from that website.

The source-link tests use sample API responses. Add, edit, remove and reload
still need to be checked against BE-56, along with invalid URLs and attempts to
edit another team's opportunity. US-19 should stay open until those checks pass.

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
