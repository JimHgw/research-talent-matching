# US-05 — Discover matching research talent

Implemented on 2026-10-10 against the checked-in Sprint 1 contract, endpoints 23–24.

## Delivered behavior

- Teams can query rankings and explanations only for their own published opportunities.
  Anonymous requests receive 401, talent accounts 403, and missing, draft or another
  team's opportunities 404.
- Only active talent with discovery consent and a confirmed current profile enter
  scoring, ranking, pagination and the total count.
- Visible fields are selected before matching. Hidden fields do not affect scores,
  gaps, reasons or evidence. Empty visibility is valid and produces anonymous talent
  with UNKNOWN results when requirements exist.
- Both matching directions reuse the existing tag rules and decimal half-up scoring.
  Rankings use score descending, unknown percentage ascending, then talent ID;
  ranks remain continuous across pages. Legacy opportunities without requirements
  produce null percentages and `INSUFFICIENT_CRITERIA`.
- Details contain `VisibleProfile` and `TeamEvidence`, with no account email, document
  provenance, source type or confirmation metadata. Allowed nested records are also
  explicitly projected to public fields.
- Every request checks current consent, confirmation and opportunity ownership.
  There is no stored match cache, and responses use `Cache-Control: no-store`.
  Revocation or a profile edit removes the talent from subsequent lists and makes
  previous detail URLs return 404 until eligible again.
- The frontend supports opportunity selection, pagination, anonymous profiles,
  errors/retry, empty pages and explanations. Entry, focus and **Refresh talent**
  fetch current data; opportunity changes reset pagination. Skill/interest names
  come from the shared vocabulary rather than interpreting IDs.

## Required dependency included

The repository already had privacy tables and a privacy page, but no privacy HTTP
implementation. Added `GET /me/privacy` and `PUT /me/privacy` so talent can actually
opt into US-05 through the application. Defaults stay private. Updates require the
owner's session, CSRF/Origin and expected privacy revision. No-op saves (including
reordered visibility selections) preserve revisions/timestamps, stale saves return
409, and privacy changes leave profile confirmation intact.

Existing US-03 confirmation and US-04 matching are reused. No schema migration,
new dependencies, account provisioning changes or contract changes are needed.
US-09 document upload/extraction is outside this implementation.

## Main files

| Area | Files |
| --- | --- |
| Team access and visible profile reads | `backend/src/features/matching/team_repository.py` |
| Team matching and response shapes | `backend/src/features/matching/team_service.py`, `engine.py`, `service.py`, `routes.py` |
| Owner privacy settings | `backend/src/features/privacy/routes.py` |
| Team UI | `frontend/src/features/matching/TalentPage.jsx`, `MatchDetails.jsx`, `frontend/src/app/workspace-config.jsx` |
| Backend acceptance | `backend/tests/test_us05.py` |
| UI interaction cases | `frontend/tests/task-20-us05.test.js`, existing `task-20-matching.test.js` |
| Real HTTP integration | `frontend/tests/us05-live.mjs`, registered in `backend/tests/test_frontend_integration.py` |

## Reproduce the workflow

1. Start the existing Flask and Vite services using the backend/frontend READMEs.
2. Sign in as talent, save profile information and confirm the current revision.
3. Open **Privacy & visibility**, enable **Allow teams to discover me**, select
   visible fields and save.
4. Sign in as a team, create and publish an opportunity with requirements, then
   choose **Discover talent**. Open **View evidence** on a ranked talent card.
5. Change privacy from a separate talent session. Return focus to the team page or
   select **Refresh talent**. Hidden skills no longer affect scoring; removing all
   fields shows an anonymous result; revoking discovery removes the talent.

## Verification

Results recorded on 2026-10-10:

| Check | Result |
| --- | --- |
| Full Python suite with required real HTTP integration | 167 passed |
| Full frontend suite, including production build checks | 98 passed |
| Frontend formatting | Passed |
| Git whitespace/error check | Passed |

Run from the repository root on Windows:

```powershell
.\.venv\Scripts\python.exe -m pytest --require-frontend -q
```

Run from `frontend/`:

```sh
npm test
npm run format:check
```

The Python suite includes real Flask/SQLite responses and an actual React tree
using HTTP, independent cookies and two simultaneous account sessions. Only its
DOM is simulated by jsdom. Frontend unit tests use synthetic response fixtures;
the frontend suite also checks the production build. These checks do not claim
visual browser, HTTPS transport or document extraction acceptance.
