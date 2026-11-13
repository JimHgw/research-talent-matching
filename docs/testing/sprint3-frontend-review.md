# Sprint 3 frontend review and verification

This report covers H18ABANANA-65 (FE-1) and H18ABANANA-66 (FE-2).

The changes use main at `0d1d923` and support the optional personal interest description in profile and document review data.

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
