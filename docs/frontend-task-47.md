# H18ABANANA-47: opportunity search, source links and deadlines

This frontend change extends the shared Sprint 1 opportunity components. It uses
the US-14 search and lifecycle APIs already on main. It does not change the backend.

## Delivered

- Existing combined filters and page reset are reused. Applied values are shown;
  equal or reversed deadline ranges are rejected before a search request.
- The list/detail views share a source-link and deadline component. Deadlines
  display in the browser's named time zone, while API values remain UTC.
- Owner editors can save changes and explicitly reopen an expired opportunity
  in one PUT with `expectedRevision` and `reopen: true`. A future or cleared
  deadline is required. Ordinary saving does not request reopening.
- Existing pending-write guards and revision-conflict recovery are retained.
- Read-only details refresh on window focus. Availability remains authoritative
  on the server; the frontend does not infer reopening from a changed date.

## BE-56 dependency: source URL

`README_SPRINT2_BACKEND_EN.md` specifies the proposed `content.sourceUrl` field:
optional absolute HTTP/HTTPS URL, maximum 2048 characters, explicit `null` to
remove. Current main's OpenAPI and backend do not yet accept or persist this field.

The source input is therefore disabled by default for legacy records. Enable
`VITE_OPPORTUNITY_SOURCE_URLS=true` at build/dev-server startup only after BE-56
deploys the agreed contract. Existing responses containing `sourceUrl` also enable
editing that field. Omitted legacy fields stay omitted on ordinary saves.

Links use a separate tab with `noopener noreferrer`; missing or invalid links
are not rendered. No URL is fetched, scraped or imported by this frontend.

URL DOM tests use synthetic responses, so they do not certify backend persistence.
Before marking US-19 complete, run create, edit, remove and reload against the
BE-56 service, including malformed URLs and another owner's write attempt.

## Verification

Run from `frontend`:

```text
pnpm test:47
pnpm test
pnpm build
pnpm format:check
```

Task 47 covers URL validation and add/edit/remove payloads, separate-tab links,
deadline boundaries, explicit reopening, retained expiry after ordinary saves,
revision conflicts, invalid filter ranges and stale search responses. Existing
US-14 tests cover composed queries, pagination reset, clear/error/empty states.
QA-51 should reuse these cases rather than duplicate them.
