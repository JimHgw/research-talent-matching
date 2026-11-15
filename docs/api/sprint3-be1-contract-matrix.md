# BE-1 Contract Review Matrix

Base reference: 3a15eff07d0f23ccbde4b8119049c75ab55b5d11, plus the local
BE-1 documentation, fixture and regression-test changes.

The tested changes were uncommitted. Final MR/commit and responsible-owner
details must be recorded during review/handoff.

OpenAPI, indexed fixtures, implemented routes and existing frontend consumers
were compared for the operations below. Existing coverage is reused, and
missing schema/error/database-revision checks were added in
backend/tests/test_sprint3_be1.py.

Execution evidence and limitations are recorded in sprint3-be1-baseline.md.

Paths below are relative to /api/v1. Test references are relative to
backend/tests/. Schema names refer to docs/api/openapi.json.

## 1. Endpoint and consumer matrix

| Operation | Request | Successful response | Current frontend consumer |
| --- | --- | --- | --- |
| GET /me/profile | No body | 200 Profile | client.profile; profile editor; review repository |
| PUT /me/profile | ProfileWrite | 200 Profile | client.saveProfile; useProfileEditor |
| POST /me/profile/confirmation | RevisionRequest | 200 Profile | client.confirm; useProfileEditor |
| GET /me/privacy | No body | 200 Privacy | client.privacy; usePrivacyEditor |
| PUT /me/privacy | PrivacyWrite | 200 Privacy | client.savePrivacy; usePrivacyEditor |
| GET /me/documents | Pagination query | 200 DocumentPage | client.documents; documents page/ViewModel |
| POST /me/documents | Multipart file and kind | 202 Document | client.upload; documents page |
| GET /me/documents/{documentId} | Path ID | 200 Document | client.document; document status flow |
| GET /me/documents/{documentId}/file | Path ID | 200 file bytes | client.download |
| GET /me/documents/{documentId}/extraction | Path ID | 200 Extraction | client.extraction; review repository/UseCase |
| POST /me/documents/{documentId}/apply | ApplyExtractionRequest | 200 Profile | client.apply; applyReviewedExtraction |
| PUT /opportunities/{opportunityId} | OpportunityWrite | 200 Opportunity | client.saveOpportunity; useOpportunityEditor |
| POST /opportunities/{opportunityId}/publish | RevisionRequest | 200 Opportunity | client.publish; useOpportunityEditor |
| GET /me/recommendations | Pagination and opportunity filters | 200 RecommendationPage | client.recommendations; Recommendations; requireMatchPage |
| GET /me/opportunity-matches/{opportunityId} | Path ID | 200 OwnerMatch | client.match; MatchDetails; requireMatchDetail |
| GET /opportunities/{opportunityId}/talent-matches | Path ID, pagination and talent filters | 200 TalentMatchPage | client.talents; TalentPage; requireMatchPage |
| GET /opportunities/{opportunityId}/talent-matches/{talentId} | Path IDs | 200 TeamMatch | client.talentMatch; MatchDetails; requireMatchDetail |

Profile, privacy and document operations require TALENT.

Opportunity writes and team matching require RESEARCH_TEAM and applicable
resource ownership.

Writes retain existing session, Origin and X-CSRF-Token checks.

## 2. Revision, omission and clearing semantics

| Area | Contract and observed implementation |
| --- | --- |
| Initial profile | Account provisioning creates revision 0, empty content and UNCONFIRMED state; reading it returns 200. |
| Profile save | expectedRevision is required and checked before mutation, including no-op requests. Eight legacy content fields are required: displayName, disciplineGroup, education, courses, researchExperience, skills, researchInterests and researchOutputs. |
| Profile clearing | Explicit [] clears a list; explicit "" clears an allowed text field. disciplineGroup accepts null. Required fields cannot simply be omitted. |
| Profile companion fields | Omitted researchInterestText, customInterestTags and resumeDescription preserve stored values. Explicit empty strings/lists clear the corresponding allowed values. |
| Personal descriptions | Existing personal-tag description omission/clearing and shared-label normalisation rules are preserved. Responses provide canonical stored selections. |
| Actual profile change | Increment revision once, set UNCONFIRMED and clear confirmedRevision/confirmedAt. Only changed components acquire MANUAL provenance. |
| No-op profile save | Preserve revision, confirmation, timestamps and unchanged provenance. |
| Confirmation | Submit expectedRevision for the saved, reviewed profile. Confirmation does not increment revision; repeated confirmation preserves the first confirmedAt. Require nonblank displayName and confirmable content. |
| Privacy | Uses its own expectedRevision/revision, independently of the profile. discoverable and visibleFields are required. Actual changes increment only the privacy revision; reordered identical visibleFields are a no-op. [] clears visibility. Privacy changes preserve profile confirmation. |
| Document extraction | READY means extraction is complete. Reading suggestions does not import or confirm a profile. Original files and extraction data remain owner-only. |
| Apply | Requires expectedProfileRevision and a nonempty sections object. Replace only supplied sections; omitted sections and their provenance remain unchanged, subject to existing shared-label normalisation rules. [] and allowed empty strings clear supplied components. |
| Successful apply | Always increment the profile revision once, even for identical imported values; clear confirmation and assign USER_REVIEWED_DOCUMENT provenance to imported components. Confirmation remains a separate action. |
| Opportunity save | Uses its own expectedRevision. Actual content changes increment revision; no-op saves preserve it. Saving preserves publication status. |
| Optional opportunity fields | Omitted opportunityType, deadlineAt and sourceUrl preserve stored values. Explicit null clears them. Unset optional fields are omitted on reads. |
| Publication | A valid current draft with at least one supported requirement becomes PUBLISHED and increments revision. Repeating publication at the current revision is a no-op; stale revisions still conflict. |
| Expiry/reopen | For PUBLISHED opportunities, reaching the deadline makes availability EXPIRED; drafts remain DRAFT. Editing or clearing an expired opportunity's deadline does not reopen it automatically. Explicit reopen requires an owned PUBLISHED opportunity, the current revision and a future or null deadline. Reopening an expired opportunity increments its revision even if content is unchanged. |

Current skill records use id, title and evidenceText. They do not use the
old tagId/claim write shape.

## 3. Error semantics and status-specific coverage

All JSON errors preserve error.code, error.message, error.fieldErrors and
requestId.

The application error handler provides X-Request-Id. The added BE-1 HTTP
tests reuse the response helper that validates Error and checks that the
response requestId matches this header. Existing tests retain their own
schema, code and state assertions.

| Situation | Status / code | Existing or added coverage |
| --- | --- | --- |
| Anonymous access | 401 / UNAUTHENTICATED | test_us01.py::test_private_reads_require_login; test_us02.py::test_authentication_required; test_us03.py::test_confirm_requires_login; test_us09.py::test_document_list_requires_login; test_us04.py::test_matching_requires_login_and_talent_role |
| Incorrect role | 403 / FORBIDDEN | test_us01.py::test_team_has_tags_but_no_talent_access; test_us03.py::test_confirm_rejects_team_account; test_us09.py::test_document_list_rejects_research_team; test_us05.py::test_authorization_and_unavailable_ids |
| Invalid write security | 403 / CSRF_INVALID | test_us01.py::test_bad_json_media_type_and_csrf_never_write; test_us02.py::test_all_mutations_require_csrf; test_us03.py::test_confirm_rejects_invalid_csrf |
| Inaccessible resources | 404 / NOT_FOUND | test_us02.py::test_drafts_and_owner_permissions; test_us09.py::test_document_read_endpoints_reject_unauthorized_access; test_us04.py::test_draft_and_missing_detail_are_not_found; test_us05.py::test_authorization_and_unavailable_ids |
| Stale versions | 409 / REVISION_CONFLICT, with error.currentRevision matching the database | test_sprint3_be1.py::test_profile_conflict_reports_database_revision; test_sprint3_be1.py::test_privacy_conflict_uses_its_own_database_revision; test_sprint3_be1.py::test_apply_conflict_matches_database_and_preserves_confirmation; test_sprint3_be1.py::test_opportunity_conflict_reports_database_revision |
| Invalid request fields | 422 / VALIDATION_ERROR | test_us01.py::test_validation_errors_use_contract_field_paths; test_sprint3_be1.py::test_skill_validation_error_matches_current_example; test_us02.py::test_ordered_replacement_ids_and_failed_updates; test_us20.py::test_invalid_deadline_create_and_edit_are_clear_and_atomic |
| Extraction pending | 409 / EXTRACTION_NOT_READY | test_us09.py::test_extraction_rejects_unavailable_results; test_sprint3_be1.py::test_apply_preserves_extraction_state_errors |
| Extraction failed | 422 / EXTRACTION_FAILED | The same extraction/apply state cases preserve the endpoint-specific code. |
| Unconfirmed owner profile | 409 / PROFILE_UNCONFIRMED | test_us04.py::test_profile_edit_requires_reconfirmation |
| Malformed JSON / wrong JSON media type | 400 / BAD_REQUEST; 415 / UNSUPPORTED_MEDIA_TYPE | test_us01.py::test_bad_json_media_type_and_csrf_never_write |
| Expired matching resource | 409 / OPPORTUNITY_EXPIRED | test_us20.py::test_deadline_before_at_after_and_no_deadline |

error.currentRevision is required by the version-conflict rule. It is not
a blanket requirement for every 409 response. Extraction and eligibility
errors retain their existing metadata.

FAILED document fixtures must populate the stored error to satisfy the
existing database constraint.

Profile confirmation currently reports content.displayName or content when
the saved profile lacks confirmable information. These paths identify the
saved profile being confirmed; the confirmation request itself contains only
expectedRevision. This existing endpoint-specific convention is preserved.

Other endpoint-specific errors retain their existing contracts and coverage.

## 4. Business rules and reused regression coverage

| Rule | Tests |
| --- | --- |
| No-op save, reconfirmation and provenance | test_us01.py::test_noop_preserves_confirmation_and_change_resets_it; test_us01.py::test_document_origins_preserved_until_section_changes; test_us03.py::test_confirm_profile_and_repeat |
| Profile explicit clearing and legacy omission | test_us01.py::test_clear_sections_and_reorder_skills; test_us11.py::test_normalised_duplicate_shared_resolution_noop_and_legacy_omission |
| Personal-tag descriptions and owner isolation | test_personal_interest_descriptions.py::test_legacy_label_only_entries_and_description_omission_remain_compatible; test_us11.py::test_stale_invalid_and_cross_owner_saves_create_no_personal_rows |
| Privacy defaults, no-ops and independent revision | test_us05.py::test_privacy_defaults_noops_conflicts_and_confirmation; test_sprint3_be1.py::test_privacy_conflict_uses_its_own_database_revision |
| Document list isolation, stable order and pagination | test_us09.py::test_document_list_only_returns_owned_documents; test_us09.py::test_document_list_pagination_and_order |
| Reviewed partial apply, clearing and unchanged origins | test_us09.py::test_apply_replaces_skills_and_resets_confirmation; test_us11.py::test_partial_review_accepts_rejects_and_clears_each_component_independently; test_us11.py::test_failed_or_stale_import_creates_no_tags_and_preserves_component_provenance |
| Real upload, Worker, import and confirmation | test_us11.py::test_real_upload_worker_review_import_reload_and_confirmation; test_us09_frontend_integration.py |
| Opportunity lifecycle, no-ops and publication | test_us02.py::test_lifecycle_noops_and_persistence; test_us02.py::test_stale_revision_is_rejected_even_for_noop_or_republish |
| Free-text skill requirements | test_opportunity_free_text_skills.py::test_arbitrary_skill_names_persist_publish_and_match_both_directions |
| Deadline, explicit reopen and optional-field compatibility | test_us20.py::test_deadline_edit_requires_explicit_reopening; test_us20.py::test_reopening_applies_new_deadline_in_one_save; test_us14.py::test_deadline_edits_preserve_expiry_and_legacy_optional_fields |
| Complete-pool filtering, stable ranking and pagination | test_us04.py::test_ranking_pagination_and_draft_exclusion; test_us05.py::test_ranking_global_pages_and_total_after_permission_filtering; test_us14.py::test_opportunity_filters_compose_before_total_and_recommendation_ranking; test_sprint3_be8.py |
| Team-visible projection and immediate revocation | test_us05.py::test_visible_content_four_statuses_and_no_owner_metadata; test_us05.py::test_hidden_claims_never_influence_scores_or_explanations; test_us05.py::test_revocation_profile_edits_and_opportunity_edits_are_immediate |
| Per-requirement scores, weights and evidence constraints | test_requirement_scoring.py; test_sprint3_be7.py |
| Real application MiniLM and fallback | test_semantic_matching.py; test_requirement_scoring.py::test_real_chinese_synonyms_and_distinct_meanings_through_http; test_sprint3_be7.py::test_http_failure_cooldown_recovers_using_current_profile |

## 5. Matching and frontend boundary expectations

Owner recommendations require the current profile revision to be confirmed.

Team matching additionally requires an owned published active opportunity,
discovery consent, an active talent account and current confirmation.

The team projection is constructed before filtering/scoring. Hidden content,
private resume text and document origins must not influence team results.

Matching uses recommendationScore when the property is present, including
when its value is null; otherwise it uses score.

The selected score sorts descending with null last, followed by
unknownWeightPercent ascending with null last, then the relevant object ID
ascending. Ranking occurs over the complete eligible filtered pool before
pagination.

Current requirement scoring preserves REQUIRED=2 and PREFERRED=1, the
existing weighted-total/rounding rules and separate structured coverage.
semanticInterest is diagnostic and has no additional current ranking weight.

Model failure preserves the documented structured fallback and availability
metadata. Legacy hybrid fixtures remain available for compatibility
validation.

Reviewed backend sources include:

- features/profile/routes.py
- features/privacy/routes.py
- features/documents/routes.py and review.py
- features/opportunities/routes.py and service.py
- features/matching/routes.py, service.py, team_service.py and team_repository.py
- shared/validation.py and shared/security.py
- The application error handler in app.py

These paths are relative to backend/src/.

Reviewed frontend sources include:

- api/client.js
- api/review-contract.ts
- api/review-repository.ts
- api/error-contract.ts
- api/match-contract.ts
- features/profile/profile-state.js and useProfileEditor.js
- features/privacy/usePrivacyEditor.js
- features/opportunities/useOpportunityEditor.js
- features/documents/extraction-review-use-cases.ts
- features/matching/Recommendations.jsx, TalentPage.jsx and MatchDetails.jsx

These paths are relative to frontend/src/.

The feature callers submit saved/reviewed revisions. Review and matching
boundaries retain their existing runtime validation.

All 49 entries in docs/api/examples/index.json have executable schema
coverage through test_indexed_example_matches_schema.

The current skill-title validation fixture is additionally compared with a
real HTTP 422 error. Added conflict checks compare currentRevision directly
with stored rows and verify that rejected requests preserve current state.

FE-1 source/fixture compatibility was reviewed. Separate agreement with the
FE-1 owner on fixtures and validation/error expectations must be recorded
before closing the shared acceptance item.

Backend integration tests do not stand in for separate FE-1 typecheck/build
or malformed-response unit checks.

## 6. Findings and resolutions

| ID | Finding | Resolution and evidence | Status |
| --- | --- | --- | --- |
| BE1-C01 | Profile PUT prose said every content key was required, contradicting optional companion fields. | Corrected the OpenAPI description to match ProfileContentWrite, route preservation and reused omission tests. | Resolved locally |
| BE1-C02 | The validation fixture referenced obsolete content.skills[0].tagId. | Updated the fixture to the current empty-title error and added a real HTTP/schema/field-path assertion. | Resolved locally |
| BE1-C03 | Shared and endpoint ranking prose still specified score alone. | Updated OpenAPI recommendation/team-list descriptions and Markdown sorting rules to match ranking_key; existing ranking/model regressions passed. | Resolved locally |
| BE1-C04 | Publication prose implied all requirements depended on shared tags. | Updated OpenAPI and Markdown descriptions for supported free-text/academic requirements and initial deadline validation; reused lifecycle, skill and deadline coverage. | Resolved locally |
| BE1-T01 | Initial added FAILED-state test omitted the stored document error. | Corrected the test fixture to satisfy the existing CHECK constraint; retained the 422/EXTRACTION_FAILED expectation. Full regression passed. | Resolved locally |

No production route/service behaviour, database schema or dependency change
was introduced. Existing test expectations were not weakened to hide failures.

## 7. Verification and remaining handoff

- Pre-change baseline: 887 passed, 21 skipped, 18 warnings; 908 total.
- Final full regression: 946 passed, 21 skipped, 18 warnings; 967 total.
- All original 908 test identities/outcomes and skip reasons were preserved.
- All 59 added cases passed.
- No unresolved local regression was observed.
- --require-frontend and --require-application-model were enabled for the final run.
- Docker/MySQL and historical US-13 model skip groups remain unverified and are recorded in the baseline report.
- Record final MR/commit, responsible owner and FE-1 agreement before marking Done.
