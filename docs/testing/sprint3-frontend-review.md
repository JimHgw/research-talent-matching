

# Sprint 3 frontend review and verification

This report covers H18ABANANA-65 (FE-1), H18ABANANA-66 (FE-2) and H18ABANANA-69 (FE-5).

Local run on 11 November 2026 from main at `58c2747`. Windows, Node 24.22.1, pnpm 11.25.0, and Python 3.12.13 for the final integration checks. The browser used an isolated SQLite database seeded with repository synthetic data and the pinned BE-7 MiniLM model.

## FE-1 contract and regression baseline

Before the change, the frontend suite passed 341 tests with zero failures or skips. Vite build and formatting passed separately. The original combined `check` script called npm, which was unavailable in this environment. The new script uses the pinned pnpm commands and adds strict type checking for the new TypeScript modules. GitLab CI runs the type check before frontend tests.

The review repository validates incoming values from the existing API client. It shares the client's session, CSRF handling and request paths. The application creates the repository once. Tests substitute a transport or repository without starting Flask.

| OpenAPI contract | Boundary | Fixtures or checks |
| --- | --- | --- |
| Extraction | `review-contract.ts`, `review-repository.ts` and `loadExtractionReview` | `extraction-ready.json`, malformed sections, mismatched document, non-READY response |
| Profile and Confirmation | `isOwnerProfile` in the repository and profile editor | `profile-confirmed.json`, invalid revision and inconsistent confirmation, older confirmed revision renders as requiring review |
| ApplyExtractionRequest and returned Profile | `applyReviewedExtraction` and the review repository | Selected sections, explicit empty values, loaded revision and canonical unconfirmed result |
| Error and ErrorDetail | `readApiError` and `ApiError` | Existing API tests and malformed fields/revision metadata |
| MatchSummary and RequirementScoring | `requireMatchPage` and `requireMatchDetail` | `owner-match-requirement-semantic.json`, `owner-match-semantic.json`, malformed scores/methods, zero and null |

The pilot uses the checked-in OpenAPI examples. BE-1 contract review with the backend owner is part of shared acceptance.

## FE-2 document review transitions

| Event | Result |
| --- | --- |
| Open review or approve a reload | Read the selected document's READY extraction and the owner profile together. Start a draft with that document and profile revision. |
| Edit a suggestion or change selected sections | Keep the reviewed revision and reset acknowledgement. |
| Apply | Send the reviewed revision and selected sections once. Empty lists and text are sent when selected. Omitted sections are left to the API's existing preservation rules. |
| Successful import | Validate the returned profile identity, incremented revision and unconfirmed status. Open the saved profile for separate review and confirmation. |
| Revision conflict | Keep corrections and block apply. The user can explicitly discard and reload the suggestions or open the latest profile. |
| Unreadable or uncertain write result | Keep corrections and block another apply. The user can inspect the saved profile before trying again. |
| Close, manual entry or document refresh | Respect pending writes and ask before discarding corrections. Obsolete reads and unmounted write callbacks cannot populate another review. |

## FE-5 local verification

- `pnpm check` in `frontend` passed type checking, **348 frontend tests**, Vite build and formatting. Zero failures or skips.
- The real HTTP, document Worker and model suite below passed **44 tests** with zero failures or skips. It covered PDF and DOCX review and import, profile confirmation, account and privacy workflows, BE-7 fallback tests and real MiniLM inference on both sides of matching.
- The US-16 suite passed **6 additional tests** on the prepared dataset, including independent sessions, consent changes, document review recovery and reconfirmation.
- In Chromium, the document-review and matching-detail dialogs fit at **320, 768 and 1280 pixels**. Enter opened the dialog, Escape closed it and focus returned to the opener. The page and dialog body fit the available width after removing the body minimum width that caused overflow when a scrollbar was present.
- Checked English, Simplified Chinese and Arabic on the document and matching screens. Arabic used RTL layout and synthetic file names and opportunity titles retained their original text.
- On the isolated browser database, changing a suggestion after acknowledgement disabled apply. The subsequent import showed the saved correction and an unconfirmed profile. Confirming separately restored the recommendations, and the detail dialog showed the real MiniLM weighted score and per-requirement scores.

```powershell
.venv/Scripts/python.exe -m backend.src.features.matching.prepare_semantic
.venv/Scripts/python.exe -m pytest backend/tests/test_us09_frontend_integration.py backend/tests/test_frontend_integration.py backend/tests/test_semantic_matching.py --require-frontend --require-application-model -q
.venv/Scripts/python.exe -m pytest backend/tests/test_us16.py --require-frontend -q
```

These results cover the API on `58c2747`. Joint acceptance with the BE-2, BE-3 and BE-4 changes and the BE-10 release run remains pending. Docker/MySQL deployment acceptance was outside this SQLite verification.
## Check after updating main

On 13 November, we updated to main at `0d1d923`. The frontend now accepts the optional personal interest description in profile and document review data. `pnpm check` passed again with 348 tests. We also ran 85 backend and integration tests with SQLite, including document review, profile confirmation, personal interest descriptions and MiniLM matching. All passed.
