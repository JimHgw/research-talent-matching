# Sprint 3 Frontend and Backend Improvement Development Guide

Project: COMP3900 / H18ABANANA Research Talent and Opportunity Matching System  
Prepared: 2 November 2026 (Sydney)  
Code baseline: local commit `7af83f2`, `Integrate MiniLM into every requirement`

This English-language document supports Sprint 3 frontend and backend task assignment, implementation and acceptance. It contains **5 frontend tasks (`FE-1` through `FE-5`) and 10 backend tasks (`BE-1` through `BE-10`)**. These are planning identifiers, not Jira issues that have already been created, and do not replace historical US/BE identifiers. Sprint 3 is the planning scope requested for this guide; no sprint dates or named assignments are inferred.

The source plan and frontend extension were prepared by statically reviewing the local code and the architecture reference, *TypeScript MVVM Guide.pdf*. The remote repository was not synchronised, frontend/backend tests were not run for this planning work, and production behaviour was not verified. References to the current implementation mean that code or tests exist in the reviewed checkout. Acceptance criteria describe checks that must be executed and supported by evidence during this iteration; they are not statements that those checks have already passed.

## 1. Iteration Objectives and Development Guidance

The objective is to make the frontend and backend easier to understand, test independently and change safely, while preserving API compatibility and business behaviour. Use the import of reviewed document extraction results into a profile as the first coordinated layering pilot, then improve profile confirmation, matching, queries and user feedback.

The PDF describes a React/TypeScript frontend architecture. Apply its separation of responsibilities using the guidance below. Its directories, class names and example code are reference material, not instructions from the user to reproduce the example mechanically.

### Frontend Responsibilities

| Frontend layer | Responsibility | Constraint |
|---|---|---|
| View / page | Render forms, lists, dialogs and accessible feedback; forward user actions | Keep multi-request orchestration and draft/revision transitions in a dedicated Hook or UseCase |
| ViewModel Hook | Own interaction state, drafts, selection, acknowledgements, request lifecycle and derived action availability | Preserve existing unsaved/pending guards and stale-response protection; do not duplicate state in both the View and Hook |
| UseCase | Express meaningful operations such as loading a review or applying selected sections | Accept dependencies explicitly and remain independent of JSX, React state and translation functions; use plain functions where sufficient |
| Repository / boundary adapter | Define business-facing data operations, validate critical responses and perform necessary conversion | Reuse the existing API client; avoid wrappers that only rename every client method |
| API client | Handle HTTP, sessions, CSRF, JSON, uploads, downloads and transport failures | Preserve existing session bootstrap and CSRF generation protection; expose read cancellation through business methods where needed |

Create stable dependencies at the application or feature composition entry point and pass them to ViewModels/UseCases. Preserve the existing feature boundaries, including the documented reuse of profile fields by document review. Introduce types incrementally around this pilot rather than making a whole-application migration a prerequisite.

### Backend Responsibilities

| Backend layer | Responsibility | Constraint |
|---|---|---|
| HTTP routes | Read parameters, invoke authentication and CSRF checks, validate request DTOs, invoke business operations and return responses | Keep complete business workflows, such as profile updates, tag creation and provenance updates, outside route handlers |
| Application services / UseCases | Express a business operation and coordinate revision checks, state transitions and data access | Do not read Flask's `request` or depend on UI state. Functions are sufficient; a class is not required for every operation |
| Repositories | Perform queries, read and write related records, load data in batches and persist changes | Use the Session supplied by the caller; do not commit transactions independently |
| DTOs / serialisation | Produce contract fields, format timestamps and expose permitted fields | Distinguish the owner's complete profile from the profile projection visible to research teams |
| ORM / database | Define tables, uniqueness constraints, foreign keys and persistence guarantees | Define explicit response structures instead of exposing ORM objects as every endpoint's response |

**Transaction convention:** business operations define which changes must be atomic. The HTTP, Worker or CLI entry point opens the transaction, and authentication, application services and repositories use the same Session. Repositories do not call `commit()`, and services do not open a separate nested write transaction. File parsing and model inference stay outside write transactions. Retain the existing database write lock until concurrency acceptance checks have passed.

**Scope:** continue using React/Vite, Flask, SQLAlchemy, MySQL and the existing `/api/v1` routes. Prefer incremental internal improvements. Any new field, error code or request semantics must be reflected in the contract, examples and frontend/backend tests. The frontend scope includes a limited TypeScript pilot, review ViewModels, query/polling state, editing consistency and matching presentation. The backend remains responsible for final authorisation, revisions, transaction integrity and scoring. Changes to the product workflow, new public endpoints or a whole-application rewrite require a separately defined scope.

### Confirmed Foundations and Improvement Opportunities

| Fact observed in the current code | Implication for this iteration |
|---|---|
| The document apply route already checks ownership, extraction state and profile revision, and invalidates confirmation | Extract the business service and verify its behaviour while preserving import rules |
| Document routes import `own_profile` and `serialize_profile` from profile routes | Move reusable queries and serialisation out of route modules to remove the cross-route dependency |
| Ordinary profile saves already handle unchanged content, provenance updates and personal interest tag resolution | Organise these behaviours into directly testable profile operations and preserve no-op save semantics |
| MySQL write transactions are serialised through `DatabaseWriteLock` | Concurrency protection already exists; use measurements to decide whether finer locking is justified |
| The Worker already implements leases, timeout recovery, attempt limits and rejection of stale results | Focus on process restarts and multiple Workers, reusing the existing queue mechanism |
| Team matching already filters by current profile confirmation, discovery consent and field visibility | Preserve a consistent authorisation boundary for every query and scoring entry point |
| Semantic scores are already calculated per requirement, using a weighted mean with REQUIRED=2 and PREFERRED=1 | Historical descriptions stating that semantic matching is not integrated into the application are outdated; verify the current per-requirement implementation |
| Some opportunity and talent queries load candidates before filtering, sorting and paginating in Python | Improve filtering and batch queries while preserving scoring across all eligible candidates before recommendation pagination |
| SQLite, MySQL, frontend/backend integration and semantic evaluation CI jobs already exist | Extend the existing pipeline with evidence for this iteration and mandatory checks of the actual application model |
| The frontend uses React/Vite and JavaScript/JSX; TypeScript is not currently a declared dependency | Add a small, independently checked TypeScript pilot under FE-1; retain JS/JSX interoperability |
| The frontend API client already handles sessions, CSRF, HTTP errors, uploads and downloads; its internal request function accepts a signal | Reuse it and thread read cancellation through the relevant public methods instead of replacing the client |
| `useResource` already ignores stale responses, but resets data on each refresh; `useMutation` prevents duplicate submissions and suppresses callbacks after unmount | Add explicit initial-loading/background-refresh semantics without losing existing safeguards |
| `ExtractionReview.jsx` currently combines parallel loading, identity/state checks, draft selection, acknowledgement, import and rendering | Extract this workflow into a dedicated ViewModel and meaningful UseCases under FE-2 |
| Documents currently poll every two seconds and pause after 60 seconds | Consolidate polling lifecycle in FE-3 while preserving pause/resume and manual-entry behaviour |
| Account generation protection, navigation guards, `useOpportunityEditor` and matching score components already exist | Extend and verify these implementations rather than rebuilding them as new features |

### Business Rules Every Task Must Preserve

1. A document being `READY` means extraction has finished. Extraction, profile import and profile confirmation are separate actions. Import must not confirm the profile automatically.
2. Every successful import increments the profile revision by one, clears `confirmedRevision` and `confirmedAt`, and sets the status to `UNCONFIRMED`. An ordinary no-op save preserves the revision and confirmation information.
3. Team discovery and matching require a confirmed current profile, a confirmed revision equal to the current revision, and discovery consent. Scoring, ranking, filtering and evidence must use only fields the team is permitted to access.
4. Owners may use their own data when viewing their matches. Team endpoints must use the team-visible projection. The complete resume, original files, document provenance and storage paths remain owner-only.
5. A partial import preserves the values and provenance of omitted sections. Use `[]` to clear lists and `""` to clear text where the contract permits clearing. Preserve the existing shared-tag resolution rules and return the canonical result.
6. Concurrent writes that change content must not overwrite each other. Conflicts return `409 / REVISION_CONFLICT` with `error.currentRevision`; failed operations leave no partial writes.
7. An opportunity expires at its deadline. Changing the deadline alone must not reopen it. Reopening requires an explicit request and successful ownership, revision and publication-condition checks.
8. When the model is unavailable, use the existing structured fallback. Missing evidence must not be presented as a successful match, and semantic similarity must not override explicit gaps or hard requirements such as qualification levels.
9. A background refresh must not silently replace an unsaved draft. A read started for an older document, filter, page or account must not populate the current context.
10. A timed-out or aborted write may already have committed on the server. Do not present cancellation as rollback or automatically replay a write whose outcome is uncertain; preserve the draft and provide a read/compare recovery path.
11. The browser displays server-authoritative confirmation, privacy and matching results. It does not confirm an imported profile, calculate replacement recommendation totals or enforce backend permissions on the server's behalf.

## 2. Overview of the 15 Tasks

Owners are suggested by responsibility; the team should assign actual names. One developer may hold several responsibilities. A task may be delivered through multiple small merge requests (MRs), but its acceptance scope remains unchanged.

P0 identifies a prerequisite safeguard or release gate, not a confirmed production incident. P1 covers core implementation improvements. P2 covers optimisation after correctness is stable.

**Difficulty scale (1-10; assessed 4 November 2026):** a relative planning estimate for a developer familiar with the current stack, considering implementation complexity, affected scope, dependencies and acceptance effort, with existing code/tests reused. Scores are separate from priority and are not effort or story-point estimates. 1-2: small local edits; 3-4: straightforward single-module changes; 5-6: moderate changes across several files with contract/regression work; 7-8: difficult cross-module state, data or recovery work; 9-10: very difficult algorithm, concurrency or platform work with demanding correctness checks.

### Frontend Tasks

| ID | Task | Priority | Difficulty (1-10) | Suggested owner | Dependencies |
|---|---|---|---|---|---|
| FE-1 | Establish typed data boundaries and the frontend regression baseline | P0 | 7/10 | Frontend API / architecture maintainer | Coordinate the contract baseline with BE-1 |
| FE-2 | Extract the document review ViewModel and UseCases | P1 | 7/10 | Document / profile frontend developer | FE-1; integration with BE-2, BE-3 and BE-4 |
| FE-3 | Improve query refresh, read cancellation and document polling | P1 | 8/10 | Shared Hooks / document frontend developer | FE-1; shared state contract coordinated with FE-2; integration with BE-6 and BE-8 |
| FE-4 | Align editing, confirmation, privacy and account state | P1 | 8/10 | Profile / opportunity / account frontend developer | FE-1 and FE-3; integration with BE-3, BE-4 and BE-5 |
| FE-5 | Verify matching presentation, accessibility and frontend delivery | P1; final release gate | 7/10 | Matching frontend developer, frontend lead and QA | Matching work after FE-1 and BE-7; final acceptance covers FE-2 through FE-4 and coordinates with BE-10 |

Development against agreed fixtures can proceed before backend refactoring is merged. Final acceptance requires the relevant real API/Worker/model paths; frontend mocks alone cannot establish backend guarantees.

### Backend Tasks

| ID | Task | Priority | Difficulty (1-10) | Suggested owner | Dependencies |
|---|---|---|---|---|---|
| BE-1 | Establish API contracts, error semantics and a regression baseline | P0 | 5/10 | API maintainer | None |
| BE-2 | Extract the reviewed document import application service | P1 | 7/10 | Document module developer | BE-1, BE-3, BE-4 |
| BE-3 | Organise profile save and confirmation services | P1 | 6/10 | Profile module developer | BE-1, BE-4 |
| BE-4 | Verify concurrent revision control and transaction atomicity | P0 | 8/10 | Database / core business developer | BE-1 |
| BE-5 | Unify authorisation and team-visible data boundaries | P0 | 8/10 | Authorisation / matching developer | BE-1 |
| BE-6 | Verify Worker recovery and state consistency | P1 | 8/10 | Document / background processing developer | BE-1, BE-4 |
| BE-7 | Establish per-requirement scoring and model fallback behaviour | P1 | 9/10 | Matching module developer | BE-1, BE-5 |
| BE-8 | Optimise queries, filtering and pagination | P2 | 9/10 | Query / matching developer | BE-5, BE-7 |
| BE-9 | Standardise database upgrades and pre-release checks | P1 | 8/10 | Database / deployment maintainer | BE-1; final review of database changes from BE-2 through BE-8 |
| BE-10 | Complete integration, diagnostics and delivery acceptance | P0, throughout the iteration | 7/10 | Backend integration lead, with QA | BE-1 through BE-9; frontend evidence from FE-1 through FE-5 for the joint release gate |

## 3. Frontend Development Requirements and Acceptance Criteria

### FE-1: Establish Typed Data Boundaries and the Frontend Regression Baseline

**Difficulty: 7/10.** Combines incremental JS/TS integration, runtime contract validation and stable dependency composition while preserving session behaviour.

**Objective:** introduce a small, verifiable TypeScript foundation for the review pilot and align critical frontend data assumptions with the existing API contract.

**Development requirements**

1. Review the existing API client, shared Hooks, document review and frontend tests. Record a baseline with commit, environment, executed checks and passed/failed/skipped counts. Agree the request/response and error fixtures with BE-1.
2. Add TypeScript tooling and a dedicated `typecheck` script using `tsc --noEmit`. Enable JS/TS interoperability and strict checking for the new typed modules. Scope the check explicitly so unrelated legacy JavaScript migration does not block this pilot.
3. Define the profile revision/confirmation, extraction, reviewed-section input, API error and matching-score DTO types needed by the changed flows. Distinguish transport data from editable UI state. Reuse a type where the structures genuinely match.
4. Introduce a document/profile repository boundary and stable feature/application dependency composition. Reuse `createApi`, its session/CSRF behaviour and existing business methods. Add a Repository or UseCase only where it provides validation, conversion, orchestration or a useful substitution boundary.
5. Validate critical external data at runtime before accepting it into the application: review extraction, profile/revision responses, apply results and changed matching-score structures. Treat incoming JSON as untrusted until validated; a type assertion alone is insufficient. Keep validators and fixtures aligned with the shared contract.

**Acceptance criteria**

- The new `typecheck` script and Vite build pass with mixed JS/TS modules. Changed typed boundaries do not use `any`, blanket assertions or suppression directives to bypass validation.
- Contract-valid fixtures load successfully. Malformed revisions, confirmation structures, extraction sections and score data produce a controlled invalid-response state rather than a render crash or an enabled destructive action.
- Invalid successful write responses are treated as an uncertain outcome requiring reconciliation; they must not be interpreted as proof that the server rolled back.
- Existing API method signatures remain compatible for unchanged callers. Cookies, CSRF pairing, upload/download behaviour and in-flight session bootstrap remain covered by regression checks.
- A test can supply an in-memory/fake Repository to a business operation without mounting the application or starting Flask. Production dependencies are stable across renders.
- Deliver a frontend baseline report, a contract-to-validator/fixture map and the agreed interface expectations for BE-1. Existing failures/skips are recorded explicitly.

**Deliverables:** scoped TypeScript configuration and script, typed DTOs and repository boundary, critical response validators, dependency composition, boundary tests and the frontend baseline report.

### FE-2: Extract the Document Review ViewModel and UseCases

**Difficulty: 7/10.** Separates a stateful review workflow without losing draft, revision, acknowledgement or submission safeguards.

**Objective:** separate the review workflow from rendering while preserving the existing document identity, user corrections, acknowledgement and import safeguards.

**Development requirements**

1. Extract a dedicated `useExtractionReviewViewModel` from `ExtractionReview.jsx`. It owns the draft, selected sections, acknowledgement, loading/submitting/error/conflict states, dirty state, close protection and derived `canApply` value.
2. Extract meaningful plain business operations such as `LoadExtractionReview` and `ApplyReviewedExtraction`. Load extraction and the current profile, validate the selected document's identity and READY status, and submit selected reviewed values with the revision actually loaded for review.
3. Keep JSX, labels, translation and layout in the View. Inject the Repository/UseCases from FE-1 and reuse existing `useMutation`, navigation guards, profile field editors and recovery components.
4. Coordinate query-state changes with FE-3. Background results must not silently replace a review draft or update its submission revision. Document changes or explicit reloads establish a new review context after the existing discard/pending checks.
5. Preserve partial replacement/clearing semantics and explicit acknowledgement. Applying reviewed content must lead to the updated unconfirmed profile and must never invoke the confirmation endpoint automatically.

**Acceptance criteria**

- The View no longer directly orchestrates parallel API calls, revision selection or import state transitions. Load/apply operations can be tested independently with supplied dependencies.
- Loading document A and then document B, with A resolving last, cannot show A's suggestions in B's review. A mismatched document ID or non-READY result cannot enable import.
- Editing values or changing the selected sections resets acknowledgement. No selection, no acknowledgement, pending submission or unresolved conflict prevents submission; rapid repeated clicks issue one apply request.
- A successful request submits only selected sections and the revision loaded for that review. Omitted content is preserved by the API, and the UI displays the canonical saved result with a separate confirmation step.
- On `409 / REVISION_CONFLICT`, corrections remain available and no automatic retry occurs. Loading/comparing the latest profile or explicitly discarding/reloading provides a clear recovery path.
- Closing, manual-entry navigation and reload preserve existing dirty/pending protections. An unmounted review cannot run a stale success callback in another review/account.
- Reuse and pass the relevant `task-61-document-review.test.js` and document mutation tests. Complete the real API review/import/confirmation sequence with BE-2, BE-3 and BE-4 before acceptance.

**Deliverables:** review ViewModel, load/apply UseCases, simplified View, state-transition documentation and direct-operation/UI/integration regression evidence.

### FE-3: Improve Query Refresh, Read Cancellation and Document Polling

**Difficulty: 8/10.** Changes shared query semantics across consumers and must handle cancellation, races, polling timers and permission loss correctly.

**Objective:** keep useful content visible during safe background refreshes and make read/polling lifecycles explicit without displaying stale or unauthorised data.

**Development requirements**

1. Extend the shared query contract to distinguish initial loading, background refreshing, current data and refresh failure. Retain existing stale-response protection. Update affected consumers explicitly rather than changing the meaning of `loading` underneath them.
2. For refreshes of the same authorised resource context, retain the last successful data and show refresh status. Clear old-context data when the account, selected entity, page or filters change. On permission loss, remove protected content rather than retaining it behind a refresh-error notice.
3. Thread `AbortSignal` through the relevant public API read methods and loaders. Abort obsolete reads on context change/unmount; expected `AbortError` is not a user-facing network failure. Do not abort shared session bootstrap on behalf of a single consumer or treat write cancellation as rollback.
4. Move document-list polling into a dedicated documents ViewModel/Hook. Retain the two-second check interval and 60-second pause budget; do not start overlapping polls. A new upload or explicit refresh starts a new budget, and reaching READY/FAILED stops unnecessary polling.
5. Define visibility/unmount behaviour: hidden pages do not start new polling requests; returning to the page rechecks only if pending work remains and the existing budget has not expired. An expired budget stays paused until an explicit refresh. Preserve manual entry and error recovery.

**Acceptance criteria**

- Initial entry shows loading; refreshing the same context keeps its list visible with a refreshing indicator. A recoverable transport failure explains the failed refresh while retaining the last authorised result.
- A slower old page/filter/document request cannot overwrite the latest result, including if abort is unsupported or the response has already arrived. Changing accounts clears private data and prevents late repopulation.
- `401`, `403`, inaccessible-resource `404` and current-profile eligibility failures remove the relevant protected data/dialogs and show the appropriate recovery state. Retaining previous data must not bypass consent or confirmation changes.
- With fake timers, polling runs at most one request at a time, stops on terminal states/unmount/hidden pages, pauses after the documented budget and resumes only under the defined rules. Remounts and effect re-runs create no duplicate timers/listeners.
- A document still PROCESSING after the budget is shown as waiting/paused, not FAILED. Manual refresh and a newly successful upload start fresh checks, while manual profile entry remains usable.
- Regress affected document, recommendation, talent, collection and focus-refresh consumers. Verify slow Worker processing with BE-6 and preserve the query/ranking semantics of BE-8.

**Deliverables:** shared query-state/API read updates, documents polling ViewModel, cancellation/race/timer tests, updated consumers and real slow-processing integration evidence.

### FE-4: Align Editing, Confirmation, Privacy and Account State

**Difficulty: 8/10.** Coordinates multiple editors, uncertain write recovery, dependent-view invalidation and account isolation.

**Objective:** make saved server state, local drafts, revisions and recovery behaviour consistent across profile, privacy and opportunity editing, while preserving account isolation.

**Development requirements**

1. Separate each editor's saved server snapshot, draft, submission revision and latest comparison result. Extract dedicated profile/privacy ViewModels where needed; extend the existing `useOpportunityEditor` rather than replacing its working save/publish/reopen recovery.
2. Reuse `useMutation` and navigation guards to prevent duplicate writes and accidental draft loss. A focus refresh must not replace dirty input; applying a newer baseline requires a deliberate user decision after comparison/discard handling.
3. Preserve the separate save, import and confirm actions. Confirmation sends the revision the user reviewed and is unavailable while content is unsaved, pending or conflicted. Privacy UI distinguishes saved settings from unsaved choices and preserves its independent revision.
4. Handle stale revisions and uncertain write outcomes consistently. Keep user input, stop blind resubmission, and provide a read/compare recovery path. Do not silently substitute a newer revision into a failed write.
5. Preserve `useAccountSession` generation checks, workspace reset and guard behaviour. Clear private state on a confirmed identity/session change; late reads or write callbacks must not restore a previous account's content. An elective account switch may prompt for unsaved work while the current session remains valid.
6. Invalidate or revalidate affected recommendation/detail/collection views after confirmed saves, confirmation changes and privacy changes. Opportunity expiry and reopen use server results and the existing explicit reopen operation.

**Acceptance criteria**

- Profile save, privacy save, opportunity save/publish/reopen each send the saved revision and issue one write when clicked repeatedly. Dirty state resets only after a valid server result or an explicit discard/reconciliation decision.
- Focus refresh, a late query and a revision conflict preserve drafts. Choosing to discard/reload uses the canonical server state; choosing to compare does not silently retry a write.
- An edited/imported profile displays that confirmation is required. A clean reviewed profile can be explicitly confirmed, and the UI accepts the server's returned confirmation revision/status.
- Unsaved privacy toggles are not presented as saved consent. After privacy changes or confirmation loss, the next relevant refresh removes unavailable evidence and handles protected-resource errors without displaying old private content.
- Simulate a network error after the server commits and an unreadable successful response: the UI reports uncertainty, keeps recoverable input and reads current state before offering a new write. It must not report that cancellation undid the change.
- Switching between two accounts, logout, expiry and old responses completing afterwards expose no previous account data or notifications. Pending/discard safeguards remain covered by existing account/navigation tests.
- Editing a deadline alone does not display an expired opportunity as reopened. Only a successful explicit reopen result changes that state. Complete revision/privacy/session checks with BE-3, BE-4 and BE-5.

**Deliverables:** consistent editor ViewModels/recovery behaviour, invalidation rules, deferred-request/session tests and profile/privacy/opportunity API integration evidence.

### FE-5: Verify Matching Presentation, Accessibility and Frontend Delivery

**Difficulty: 7/10.** Requires consistent scoring presentation plus localisation, accessibility and real-backend acceptance across several views.

**Objective:** present current server scoring faithfully and verify that the complete frontend iteration is usable, localised and ready for integration release.

**Development requirements**

1. Extend the existing matching components and typed boundaries to consume current per-requirement scores, weights, contributions, methods and permitted supporting records. Keep recommendation score, evidence coverage, unknown evidence and interest diagnostics distinct.
2. Display server-authoritative totals/ranks; do not introduce a frontend scoring formula or add an interest bonus. Preserve contract-supported historical response handling without describing current per-requirement scoring as an old hybrid-weight algorithm.
3. Explain unavailable-model fallback and missing evidence without inventing a percentage, qualification or match. Protected-resource/eligibility errors use the FE-3/FE-4 recovery rules and clear obsolete details.
4. Apply existing localisation to new states, validation and recovery messages. Preserve user-entered content, existing language fallback and direction handling. Verify changed forms/dialogs with keyboard navigation, visible labels, focus management and announced status/error feedback.
5. Extend the existing frontend tests, build, formatting and CI checks to include FE-1's new `typecheck` script. Update architecture/import checks to cover new `.ts/.tsx` files while preserving existing feature and shared-module boundaries.
6. Coordinate the frontend evidence with BE-10 and QA. Use real API/Worker flows for end-to-end acceptance and BE-7's mandatory real-model run for current scoring; distinguish these from fixture-based UI tests and historical US-13 evaluation.

**Acceptance criteria**

- List cards, details and collection-related views display consistent server scores, weights, contributions and ordering for the same data. Zero is displayed as zero; null/unavailable data is shown as unavailable rather than a fabricated zero or percentage.
- With fixed BE-7 fixtures and a real-model API response, current per-requirement scoring is labelled correctly. Structured coverage and interest diagnostics remain separate, and missing/negative evidence is not described as satisfied.
- Model failure, missing information, unconfirmed profiles, consent withdrawal and expired opportunities have clear recovery states. Team views expose only records returned through authorised projections.
- All changed critical flows work in English and Simplified Chinese and are checked in an existing RTL language. New UI strings use the existing dictionary/fallback mechanism; personal content is not translated or rewritten.
- Changed screens/dialogs remain usable at widths of 320, 768 and 1,280 pixels. Keyboard users can open/use/close dialogs, focus returns appropriately, controls have accessible labels, and feedback is announced without losing drafts.
- Execute frontend tests, build, formatting and the new typecheck gate. Report counts and any failures/skips; required checks cannot be skipped and counted as passed.
- Complete upload/review/import/confirmation/matching, stale-write recovery, polling pause/resume, account switching, privacy withdrawal and model fallback against the real backend. Link evidence to FE-1 through FE-5 and the corresponding BE tasks in the shared release report.

**Deliverables:** updated matching/recovery UI, necessary localisation/accessibility changes, frontend CI updates, viewport/keyboard evidence and the frontend section of the shared acceptance/release report.

## 4. Backend Development Requirements and Acceptance Criteria

### BE-1: Establish API Contracts, Error Semantics and a Regression Baseline

**Difficulty: 5/10.** Mainly aligns existing contracts, fixtures and regression evidence; the challenge is coverage and consistency rather than new algorithms.

**Objective:** provide an explicit, executable comparison of behaviour before and after subsequent refactoring.

**Development requirements**

1. Review profile read/write/confirmation, privacy, document list/extraction/apply, opportunity update/publication, recommendations and team matching endpoints. Compare OpenAPI, examples, implemented routes and existing consumers for each operation.
2. Document revision field names, omission and clearing semantics, status codes and error responses. Preserve the common structure: `error.code`, `error.message`, `error.fieldErrors` and `requestId`; conflicts also return `error.currentRevision`.
3. Execute relevant existing tests first. Record the commit, environment, test count, passed/failed/skipped counts and failure reasons. List existing defects separately; do not conceal failures by changing expected results.
4. Create a mapping from business rules to endpoints and tests. Add regression cases for missing critical scenarios and reuse existing coverage. Coordinate the fixtures and validation/error expectations with FE-1.

**Acceptance criteria**

- Successful responses and representative error responses validate against their respective schemas. Valid JSON syntax alone is insufficient.
- Coverage includes anonymous access `401`, an incorrect role `403`, an inaccessible resource `404`, a revision conflict `409` and field validation `422`. Preserve endpoint-specific contracts for other errors.
- The current revision in conflict examples agrees with the database, and field error paths identify the relevant request fields.
- Deliver a reproducible baseline report that identifies every failure and skip. Subsequent tasks introduce no unresolved regression failures.

**Deliverables:** contract review matrix, necessary contract/example updates, baseline report and additional tests. Prefer the existing `docs/api/` and `backend/tests/` locations.

### BE-2: Extract the Reviewed Document Import Application Service

**Difficulty: 7/10.** Extracts a multi-step import workflow while preserving transaction atomicity, provenance and revision semantics.

**Objective:** move the document import workflow out of HTTP routes while preserving atomic persistence of user-reviewed content.

**Development requirements**

1. Extract business operations such as `ApplyReviewedExtraction` from `documents/routes.py`. Coordinate ownership, extraction state, profile revision, selected sections, tag resolution, provenance and confirmation invalidation.
2. Place queries and writes in document or profile repositories, with serialisation in a separate module. Remove imports of profile route modules from document routes.
3. Keep request parsing and response conversion in the HTTP layer. Services receive explicit arguments and the same Session, allowing direct invocation in tests without an HTTP request context.
4. Preserve existing support for saving reviewed content. Describe and coordinate with the frontend any proposed new content restriction that would change the contract before implementing it.

**Acceptance criteria**

- Importing valid sections from an owned READY document with the correct revision succeeds. The revision increases exactly once, confirmation becomes `UNCONFIRMED`, and the response contains the canonical saved profile.
- `QUEUED/PROCESSING` returns `409 / EXTRACTION_NOT_READY`; `FAILED` returns `422 / EXTRACTION_FAILED`; another user's document returns `404 / NOT_FOUND`.
- Importing against a stale revision returns `409 / REVISION_CONFLICT` without changing the profile, tags or provenance records.
- Importing only skills preserves other content and provenance. Explicit empty values clear the relevant sections as permitted by the contract.
- A failure during tag resolution or saving rolls back all changes, creates no orphan personal tags and does not invoke profile confirmation.
- Business operations can be tested through direct calls. Existing HTTP and frontend review integration checks continue to pass.

**Deliverables:** import service, necessary data access/serialisation modules, direct-call tests and a regression report for the existing review workflow.

### BE-3: Organise Profile Save and Confirmation Services

**Difficulty: 6/10.** Refactors established save/confirmation rules with shared queries and serialisation, including no-op and tag behaviour.

**Objective:** centralise profile state transitions for reuse by document imports and owner profile operations.

**Development requirements**

1. Move profile queries, serialisation and save/confirmation business operations from `profile/routes.py` into appropriate modules. Keep HTTP adaptation in the routes.
2. Define inputs and results for `SaveProfile` and `ConfirmProfile`. Share the rule that profile changes invalidate confirmation while preserving the different revision semantics of ordinary saves and imports.
3. Preserve personal interest tag normalisation, deduplication, shared-tag resolution, ownership and combined-count limits.
4. Confirmation must apply only to the current revision explicitly submitted by the requester. Repeated confirmation must not overwrite the original confirmation timestamp.

**Acceptance criteria**

- A real content change to a confirmed profile increments the revision by one and invalidates confirmation. An identical ordinary save preserves the revision, confirmation timestamp and provenance.
- Repeated confirmation of the same current revision preserves the revision, `confirmedRevision` and original `confirmedAt`.
- Confirmation of a stale revision returns `409`. A blank name or absence of confirmable content returns `422`, with no persistent changes.
- When older clients omit optional companion fields, existing free text and personal tags remain intact. Explicit clearing follows the existing contract.
- Another user's personal tag ID cannot be associated or modified. Failed operations create no personal tags and do not change the shared vocabulary.
- Profile operations can be tested without an HTTP request context. Preserve the relevant behaviours covered by `test_us01.py`, `test_us03.py` and `test_us11.py`.

**Deliverables:** profile services, shared query/serialisation modules, state-transition rules and regression evidence.

### BE-4: Verify Concurrent Revision Control and Transaction Atomicity

**Difficulty: 8/10.** Requires controlled multi-connection concurrency and fault injection on SQLite and MySQL to prove valid state transitions and rollback.

**Objective:** demonstrate that real concurrent operations cannot lose updates and protect subsequent layering changes.

**Development requirements**

1. Review profile, privacy, import and opportunity writes. Establish the required write protection before reading the state used for revision comparison.
2. Retain the existing MySQL write lock and SQLite write transaction guarantees. Reproduce concurrency using two independent database connections/requests; sequential calls on one connection are insufficient.
3. Inject failures during writes to profile child tables, personal tags, provenance and confirmation state to verify rollback within the same transaction.
4. Distinguish repeated confirmation, ordinary no-op saves and repeated imports. Preserve the existing revision protocol so retries cannot silently repeat an import.

**Acceptance criteria**

- When two concurrent requests submit the same revision and both would change profile content, exactly one succeeds and the other returns `409`. The final database contains only the complete result of the successful request.
- The same rule applies when import and manual save compete for the same revision. A successful import produces exactly one revision increment.
- Concurrent confirmation and editing must produce a valid serial outcome: new content cannot retain confirmation of an old revision. If editing finishes first, confirmation of the old revision returns `409`.
- Retrying an already successful import with the same stale revision returns `409`, creates no additional tags and does not increment the revision again.
- A failure during any child-table write rolls back the revision, confirmation, tags, content and provenance together.
- Execute critical cases against both SQLite and real MySQL 8.4 and submit both sets of results. Repeat the cases for at least 10 rounds without relying on sleeps to produce a race; synchronisation barriers may control interleaving.

**Deliverables:** concurrency and fault-injection tests, transaction-boundary documentation and results from both databases. If finer locking is necessary, include measurements and a correctness comparison.

### BE-5: Unify Authorisation and Team-Visible Data Boundaries

**Difficulty: 8/10.** Authorisation must constrain every search, scoring and evidence input, including revocation and collection paths.

**Objective:** ensure authorisation governs the inputs to filtering, scoring, ranking and evidence generation as well as returned fields.

**Development requirements**

1. Reuse existing session, role and CSRF checks. Document an access matrix covering the owner, other talent users, the opportunity owner, other teams, anonymous users and invalid sessions.
2. Organise team query entry points around current confirmation, discovery consent, an active user and field visibility. Cover lists, details, matching and collection/shortlist paths.
3. Construct the team-visible data projection before search and scoring. Do not score hidden content and then merely remove it from the response.
4. Review `resumeDescription`, original documents, extraction results, origins, personal tags and semantic inputs. Keep owner data and team-visible projections distinct.

**Acceptance criteria**

- Anonymous access to private endpoints returns `401`; an incorrect role returns `403`. Unauthorised private resources return `404` under the existing contract without revealing their existence.
- After changing hidden content in two otherwise discoverable test profiles and reconfirming each, team filtering, scores, ranks and evidence remain unaffected by the hidden content.
- Revoking discovery consent or hiding a field takes effect on the next new request. Existing collections cannot bypass the checks.
- After a profile edit and before reconfirmation, teams cannot continue using the previously confirmed content. Owner recommendation/matching endpoints reject unconfirmed profiles according to the contract.
- Team responses and team model inputs contain no complete resume, original document path/ID or private provenance. Other accounts cannot read the owner's documents or use their personal tags.
- Verify logout, session expiry and account switching with independent clients. Hiding frontend buttons is insufficient evidence.

**Deliverables:** access matrix, necessary consolidation of data boundaries, API and scoring-input assertions, and a regression report.

### BE-6: Verify Worker Recovery and State Consistency

**Difficulty: 8/10.** Needs reproducible multi-process lease recovery, restart checks and rejection of delayed writes from stale Workers.

**Objective:** verify that the existing lease mechanism remains reliable across restarts, multiple processes and timeouts.

**Development requirements**

1. Preserve `QUEUED → PROCESSING → READY/FAILED`, lease tokens, expired-lease recovery and maximum-attempt rules.
2. Review the boundaries between claiming a job, parsing its file, validating the result and persisting the outcome. File parsing stays outside write transactions.
3. Compare coverage with `test_us09_worker.py` and add any missing cross-process stop/restart checks. Reuse scenarios already covered.
4. Distinguish lease expiry, file corruption, model/parser exceptions and result schema errors. Record the processing stage and outcome needed for diagnosis.

**Acceptance criteria**

- With two independent Workers running simultaneously, only one can claim a given lease for the same document.
- If a Worker stops after a document enters PROCESSING, another Worker can take over after lease expiry. A successful run leaves the document READY with exactly one valid extraction result.
- A delayed success or failure from the previous lease holder cannot overwrite a newer lease or a READY result.
- Reaching the maximum attempt count leaves the document FAILED. Missing/corrupt files produce an identifiable failure, and the user can still maintain their profile manually.
- An extraction result with a mismatched `documentId` or invalid schema cannot set the document to READY. Subsequent handling follows the lease recovery rules.
- If database registration fails after an uploaded file has been saved, the existing compensation mechanism removes that file. Failure logs contain no resume body text.

**Deliverables:** Worker behaviour documentation, reproducible recovery steps, regression tests and at least one record of an actual process-restart check.

### BE-7: Establish Per-Requirement Scoring and Model Fallback Behaviour

**Difficulty: 9/10.** Combines per-requirement scoring correctness, hard evidence constraints, real model resources and failure/cooldown recovery.

**Objective:** make the existing MiniLM per-requirement scoring explainable and reproducible, while keeping the API available when the model is unavailable.

**Development requirements**

1. Review the call boundaries in `requirement_scoring.py` and `semantic_runtime.py`. Clarify responsibility for structured assessment, semantic scoring, total scores and explanations.
2. Preserve REQUIRED=2 and PREFERRED=1 weights. Calculate the total recommendation score using the existing per-requirement rules; do not add overall interest similarity as an extra ranking bonus.
3. Preserve request-local text deduplication, batching, verified local model artifacts, failure cooldown and structured fallback. Record the versions of the model, preprocessing/scoring algorithm and thresholds.
4. Add mandatory checks using the actual application model and prepare the required resources under `data/semantic/model`. The historical US-13 experiment's model/report does not replace verification of current per-requirement scoring.
5. The real-model acceptance entry point must fail explicitly when required resources are missing. Existing `skipif` conditions must not allow skipped real-model checks to be reported as a semantic feature pass.

**Acceptance criteria**

- Every supported requirement type has an individual score. Weights, denominators, rounding and total scores agree with independently calculated fixed examples.
- High similarity cannot turn missing evidence, an explicit gap or an unmet qualification-level/output-type requirement into a satisfied requirement. Interest text cannot serve as skill or qualification evidence.
- Lists, details and collection-related matching use the same rules for the same data. Ranking uses the final scores of all eligible candidates.
- Missing/corrupt model files, load failures, inference exceptions and invalid vectors produce contract-compliant structured fallback and unavailable indicators, without NaN values or fabricated semantic evidence.
- The model is not reloaded on every request during the failure cooldown and can recover after the cooldown. Request handling does not download a model.
- Real-model HTTP cases covering Chinese synonymous expressions, different meanings and explicit negation execute successfully. Submit the model version and a report with no skipped critical checks.
- Preserve the current boundary that profile text/vectors are not retained across requests. Any future cache requires a separate design for authorisation and revision-based invalidation.

**Deliverables:** scoring rules, fixed examples, fallback tests, a real-model execution report and model preparation/verification instructions.

### BE-8: Optimise Queries, Filtering and Pagination

**Difficulty: 9/10.** Must improve data loading and SQL execution while preserving global semantic ranking, exact filtering, totals and stable pagination.

**Objective:** reduce unnecessary data loading and related-record queries while preserving query results and recommendation semantics.

**Development requirements**

1. Measure SQL query counts, candidate counts, P50/P95 latency and peak memory for opportunity lists, owner recommendations and team talent matching before selecting optimisations.
2. For ordinary opportunity lists, push suitable authorisation, availability, combined filtering, stable ordering, count and pagination operations into the database. Document equivalent handling for rules that cannot be pushed down directly.
3. Read related tags and structured records in batches to avoid repeating the same query for every candidate. Add indexes based on actual queries and execution plans.
4. Preserve the recommendation sequence: authorisation filtering → condition filtering → score all eligible candidates → stable sorting → pagination. Do not fetch one page or arbitrarily truncate candidates before scoring.
5. Use consistent opportunity availability rules and one reference time per operation. Preserve explicit reopen behaviour and compatibility when older clients omit optional fields.

**Acceptance criteria**

- With the same data, fixed time and model, the result set, order, total and rank are identical before and after optimisation. Score differences must remain within the existing rounding precision.
- Behaviour immediately before, exactly at and after a deadline follows existing rules. Moving the deadline into the future does not automatically reopen an expired opportunity.
- Use fixed datasets of 100 and 1,000 candidates containing mixed permissions, states and filter conditions. After warming up, collect at least 30 requests for each group and submit before/after measurements from the same environment.
- Ordinary opportunity lists no longer serialise every candidate before selecting a page. Related-record SQL query counts do not grow one query at a time with the number of returned records; report the actual query bound.
- Multiple pages contain no duplicates or omissions, ties have stable ordering, and filtering/pagination alone triggers no writes.
- If measurement shows an optimisation has no benefit or would change ranking, retain the correct implementation and report the findings. Performance gains cannot come from changing business results.

**Deliverables:** query improvements, necessary indexes, result-equivalence tests, fixed datasets and a before/after performance report.

### BE-9: Standardise Database Upgrades and Pre-Release Checks

**Difficulty: 8/10.** Covers fresh and existing databases, repeatable upgrades, MySQL DDL behaviour and verified recovery without data loss.

**Objective:** demonstrate that the updated code works for both fresh installations and upgrades containing existing data.

**Development requirements**

1. Document a single checklist for the existing `init-db`, `upgrade-opportunity-search`, `upgrade-resume-text` and Docker startup sequence. `create_all()` does not replace upgrades to existing table structures.
2. Provide explicit, repeatable upgrades for any indexes, fields or constraints introduced in this iteration. Modules without schema changes need compatibility verification records.
3. Prepare pre-upgrade test data containing accounts, confirmed profiles, privacy settings, documents, personal tags and published/expired opportunities.
4. Document compatible API/Worker versions, the upgrade window, recovery after failure and model resource checks. Reuse existing CLI commands, deployment configuration and readiness checks.
5. Document the actual commit behaviour of MySQL DDL separately. Do not claim that application transaction rollback can automatically undo all DDL operations.

**Acceptance criteria**

- A fresh MySQL 8.4 installation can be initialised and run the API/Worker. An existing-data copy can be upgraded in the documented order.
- Two consecutive upgrade executions succeed. The second does not duplicate, clear or rewrite business data.
- Account login, profile/privacy revisions, confirmation information, document references, personal tags and opportunity requirements are preserved across the upgrade. New fields receive values according to the contract.
- Chinese text, four-byte Unicode characters and resume text at the API's permitted length can be saved and read back completely after a restart.
- An injected upgrade failure prevents the service from reporting readiness and accepting incompatible requests. The documented procedure can restore a known working state.
- Complete at least one backup restoration or verified reverse-recovery exercise on an isolated test copy and record the post-recovery data checks.

**Deliverables:** upgrade checklist, necessary migrations, fresh-install and upgrade verification reports, and release/recovery instructions.

### BE-10: Complete Integration, Diagnostics and Delivery Acceptance

**Difficulty: 7/10.** Integrates CI, diagnostics and real API/Worker/model workflows, with substantial coordination and acceptance evidence.

**Objective:** give the team evidence that the iteration works and the diagnostics needed to investigate actual user failures.

**Development requirements**

1. Reuse existing backend, MySQL, frontend/backend integration and semantic evaluation CI jobs. Include new tests from this iteration and the mandatory real application-model checks from BE-7.
2. Record test counts, failures/skips, model version, commit and environment consistently. Historical experiment reports alone cannot establish acceptance of current per-requirement scoring.
3. Preserve the existing `requestId`, `X-Request-Id` and `/healthz`. Add any missing diagnostics for stages, durations, error types, revision conflicts and model fallback. Use Worker job correlation identifiers that contain no document body text.
4. Work with frontend developers and QA to verify complete workflows and failure recovery. Supply replayable data, steps and expected results. Every fix must have reproduction and retest records. Incorporate FE-5's frontend report and link each scenario to its FE and BE owners.
5. Logs must contain no passwords, cookies, CSRF tokens, complete profiles/resumes, model inputs or private storage paths.

**Acceptance criteria**

- Relevant existing regressions and all new checks pass. Required MySQL, real application-model and frontend/backend integration cases cannot be skipped and then counted as complete.
- Execute at least this workflow: upload → Worker extraction → user-selected partial import → unconfirmed profile → explicit confirmation → matching. Also check a profile changed by another request during review, stale import conflicts, consent withdrawal, model fallback and opportunity expiry/reopen.
- Conflicts do not overwrite newer database content. Verify frontend draft preservation through integration checks; the backend must not avoid conflicts by automatically retrying stale writes.
- After injecting a request failure, its response requestId can locate the corresponding diagnostics. A job correlation identifier can trace Worker claim, reclaim and result persistence. Inspect diagnostics to confirm that they contain no sensitive body text.
- Saved data remains readable after API/Worker restarts. Database unavailability fails readiness. When the model is unavailable but structured fallback remains usable, report fallback status without incorrectly treating the entire service as unavailable.
- Release notes cover API impact, database upgrades, model resources, known limitations and recovery procedures. Every task links to an MR/commit and acceptance evidence.

**Deliverables:** CI updates, integration and failure-recovery reports, necessary diagnostic improvements and consolidated release notes.

## 5. Recommended Implementation Sequence

1. **Establish safeguards and contracts:** coordinate FE-1 with BE-1, then complete BE-4 and BE-5. Start the upgrade checklist in BE-9 and the acceptance templates in FE-5/BE-10 early.
2. **Complete the review pilot:** perform BE-3 before BE-2 to move shared functionality out of profile routes. Develop FE-2 against the agreed repository fixtures, then integrate it with the real backend. FE-3 and BE-6 can progress under the agreed query/transaction boundaries.
3. **Align editors and matching:** complete FE-4 after the FE-3 query contract is stable. Complete BE-7 after BE-5, then integrate FE-5's scoring presentation. Keep scoring changes separate from the BE-8 performance changes to make regressions easier to locate.
4. **Complete overall acceptance:** BE-9 consolidates actual database changes; FE-5 and BE-10 execute and report the frontend/backend release checks together. Every required FE and BE criterion must pass before the joint release gate is complete.

Each MR should describe the specific problem, resulting behaviour, contract/database changes, checks executed and reasons for any checks not executed. Use existing tests to establish behaviour and add necessary business scenarios. Measure completion through working behaviour, not the number of files moved or layers introduced.

### Shared Integration Scenarios and Ownership

| Scenario | Frontend responsibility | Backend responsibility | Shared acceptance evidence |
|---|---|---|---|
| Contract and malformed responses | FE-1 validates critical data and provides controlled recovery | BE-1 supplies consistent schemas, examples and machine-readable errors | Agreed fixtures, response validation and invalid-response cases |
| Reviewed partial import | FE-2 binds the selected document, draft and reviewed revision | BE-2/BE-3 apply atomically and leave the profile unconfirmed; BE-4 protects concurrent writes | Real upload/review/import/confirm flow, including omitted and cleared sections |
| Slow extraction and refresh | FE-3 preserves same-context list data and manages pause/resume | BE-6 recovers leases and reports authoritative document states | Worker restart and slow-processing checks with UI status/polling evidence |
| Conflict or uncertain write | FE-2/FE-4 preserve input and reconcile without blind retries | BE-4 enforces revisions/atomicity; BE-1 returns the agreed error structure | Competing requests and a committed write followed by a lost/unreadable response |
| Session/consent change | FE-3/FE-4 clear old-account/protected state; FE-5 clears obsolete matching views | BE-5 enforces current permissions on every applicable request | Independent clients, late responses, revocation and no leaked scoring input |
| Per-requirement scoring/fallback | FE-5 displays server values and distinguishes unavailable/missing evidence | BE-7 owns score calculation, permitted inputs and real-model/fallback checks | Current scoring fixtures plus actual application-model HTTP results |
| Deadline and explicit reopen | FE-4 uses the explicit action and server result; FE-5 reflects availability | BE-8 preserves authoritative availability during query optimisation | Deadline boundary, deadline-only edit and explicit reopen cases |
| Delivery and recovery | FE-5 owns frontend checks and browser usability evidence | BE-9 owns upgrade/recovery evidence; BE-10 consolidates release verification | Linked FE/BE records and the unified release report |

## 6. Definition of Done and Acceptance Records

A completed task must have reviewable implementation, correct business behaviour, synchronised contracts, executed tests and reproducible failure recovery. Directory changes, test files without execution, or an informal manual observation alone are insufficient for acceptance.

Frontend checks include the existing test, build and formatting scripts plus the `typecheck` script introduced by FE-1 and made mandatory by FE-5. The typecheck script is a Sprint 3 deliverable, not a claim that it already exists in the baseline. API mocks are appropriate for isolated UI/race tests; final cross-layer acceptance requires the applicable real backend, database, Worker and model checks.

Submit one record per task containing:

| Record item | Required information |
|---|---|
| Task and implementation | FE-x or BE-x identifier, actual owner and MR/commit |
| Environment | Database version and Python version; model/algorithm versions where applicable |
| Execution | Commands or steps, dataset version, execution time and passed/failed/skipped counts |
| Evidence | Responses, database assertions, reports or log correlation identifiers; no sensitive source text |
| Risks and recovery | Known limitations, contract/upgrade impact and recovery procedure |
| Acceptance decision | Pass / Fail, with every unmet criterion listed explicitly |

Reuse the repository's existing `--run-mysql` and `--require-frontend` test options. MySQL tests clear test data: use a dedicated, isolated database whose name ends in `_test`, following `backend/tests/conftest.py` and the existing CI configuration.

Frontend records must also include Node.js, package-manager and browser versions where applicable, along with viewport/language settings for usability evidence. Record the commit and outcomes for frontend tests, build, formatting and typecheck separately.

## 7. Code and Test Reference Map

The following locations are planning references and development entry points. Their inclusion does not mean the associated tests have passed:

### Frontend Reference Map

| Area | Current entry points |
|---|---|
| Tooling and build | `frontend/package.json`, `frontend/vite.config.js`, `frontend/scripts/test.js` |
| HTTP and errors | `frontend/src/api/client.js`, `frontend/src/api/errors.js`, `frontend/tests/api.test.js` |
| Query/mutation/navigation state | `frontend/src/shared/hooks.js`, `frontend/src/shared/useMutation.js`, `frontend/src/layout/useWorkspaceNavigation.js` |
| Documents and review | `frontend/src/features/documents/ExtractionReview.jsx`, `frontend/src/features/documents/DocumentsPage.jsx`, `frontend/src/features/documents/ReviewRecovery.jsx` |
| Profile/privacy/opportunity editing | `frontend/src/features/profile/ProfilePage.jsx`, `frontend/src/features/privacy/PrivacyPage.jsx`, `frontend/src/features/opportunities/useOpportunityEditor.js` |
| Session isolation and composition | `frontend/src/features/auth/useAccountSession.js`, `frontend/src/App.jsx`, `frontend/src/app/workspace-config.jsx` |
| Matching display | `frontend/src/features/matching/Recommendations.jsx`, `frontend/src/features/matching/MatchDetails.jsx`, `frontend/src/features/matching/RequirementScore.jsx`, `frontend/src/features/matching/SemanticInterest.jsx`, `frontend/src/features/matching/TalentPage.jsx` |
| Accessibility/localisation | `frontend/src/shared/ui.jsx`, `frontend/src/shared/i18n.jsx`, `frontend/src/shared/locales/` |
| Main regression entry points | `frontend/tests/task-61-document-review.test.js`, `frontend/tests/task-22-documents.test.js`, `frontend/tests/task-41-profile-privacy.test.js`, `frontend/tests/task-47-opportunities.test.js`, `frontend/tests/task-49-account-language.test.js`, `frontend/tests/task-20-semantic.test.js`, `frontend/tests/task-53-talent-evidence.test.js` |
| Architecture and integration | `frontend/tests/architecture.test.js`, `frontend/tests/support/app-harness.js`, `backend/tests/test_frontend_integration.py`, `backend/tests/test_us09_frontend_integration.py` |

### Backend Reference Map

| Area | Current entry points |
|---|---|
| Contracts and errors | `docs/api/openapi.json`, `docs/api/examples/`, `backend/src/shared/validation.py`, `backend/src/app.py` |
| Profiles and imports | `backend/src/features/profile/routes.py`, `backend/src/features/documents/routes.py`, `backend/src/features/documents/review.py`, `backend/src/db/interests.py` |
| Concurrency and persistence | `backend/src/db/database.py`, `backend/src/db/models.py`, `backend/src/db/schema_upgrades.py`, `backend/src/db/opportunity_upgrade.py` |
| Authorisation and visibility | `backend/src/shared/security.py`, `backend/src/features/privacy/routes.py`, `backend/src/features/matching/team_repository.py`, `backend/src/features/matching/team_service.py` |
| Worker | `backend/src/features/documents/worker.py`, `backend/src/features/documents/storage.py`, `backend/tests/test_us09_worker.py` |
| Per-requirement scoring | `backend/src/features/matching/requirement_scoring.py`, `backend/src/features/matching/semantic_runtime.py`, `backend/src/features/matching/semantic_config.json` |
| Queries and opportunity lifecycle | `backend/src/features/opportunities/service.py`, `backend/src/features/opportunities/repository.py`, `backend/src/features/opportunities/availability.py`, `backend/src/features/matching/service.py` |
| Core behaviour tests | `backend/tests/test_us01.py`, `backend/tests/test_us03.py`, `backend/tests/test_us05.py`, `backend/tests/test_us11.py`, `backend/tests/test_us11_review_regressions.py`, `backend/tests/test_us14.py`, `backend/tests/test_us20.py` |
| Semantic / database / integration tests | `backend/tests/test_requirement_scoring.py`, `backend/tests/test_semantic_matching.py`, `backend/tests/test_mysql.py`, `backend/tests/test_frontend_integration.py`, `backend/tests/test_us09_frontend_integration.py` |
| Release and CI | `.gitlab-ci.yml`, `backend/docker/entrypoint.sh`, `backend/README.md`, `docs/mysql-migration.md` |

The historical Sprint 2 README contains earlier implementation states and proposals labelled "proposed". Confirm implementation decisions against this iteration's code baseline, coordinated contracts and actual execution results.
