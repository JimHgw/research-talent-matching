# Semantic interest ranking in the application

Implemented on 27 October 2026. Application recommendations, team discovery,
shortlisted candidates and both matching-detail endpoints now run the existing
local MiniLM interest encoder. This application integration supersedes the
historical US-13 decision to omit integration; the frozen experiment and its
recorded metrics remain unchanged.

## Inputs and privacy

The talent input combines the current confirmed `researchInterestText`, shared
interest labels and selected personal interest labels. Text is primary and
duplicate labels add no weight. Text-only and personal-only profiles participate
without an exact shared-tag gate. The opportunity input combines `researchArea`
and INTEREST requirement labels. Skills, education, full resumes and original
documents are not model inputs.

Owner recommendations use the owner's current confirmed interests. Team lists,
details and shortlists first check active accounts, current confirmation,
discovery consent and the existing `researchInterests` visibility group, which
also controls interest text and personal labels. Hidden interests never enter
inference. Profile changes require reconfirmation; privacy changes apply on the
next request. Text and vectors are deduplicated within each request and never
cached across requests or persisted. Only the encoder is shared across requests,
with a lock protecting initialization and tokenization/inference.

Filters run before model input construction. Eligible matches are evaluated and
sorted before pagination, so ranks and counts describe the whole filtered pool.

## Scores and response fields

The existing `summary.score`, `algorithmVersion`, requirement statuses and
supporting evidence keep their structured coverage meaning. Semantic similarity
does not create a skill, qualification or MATCHED/GAP result.

When semantic matching is enabled, every matching summary also includes:

| Field | Meaning |
|---|---|
| `recommendationScore` | Score used for sorting and displayed on recommendation/talent cards |
| `rankingAlgorithmVersion` | `hybrid-interest-v1` |
| `semanticInterest.status` | `AVAILABLE`, `MISSING_EVIDENCE` or `UNAVAILABLE` |
| `semanticInterest.similarity` | Raw cosine similarity from -1 to 1; null when unavailable |
| `semanticInterest.score` | `max(0, similarity) × 100`, rounded to two decimals |
| `semanticInterest.relevance` | `RELEVANT` at 0.75+, `PARTIAL` at 0.45+, otherwise `UNRELATED`; `UNKNOWN` when no result |
| `semanticInterest.weight` | Actual semantic weight used for this result; zero on fallback |
| `semanticInterest.modelVersion` | `minilm-interest-onnx-v1` |

Default ranking is **70% structured coverage + 30% semantic percentage**.
For example, 50 coverage and cosine 0.8 produce 59 recommendation points. The
blend uses the unrounded semantic percentage and rounds the final result to two
decimals with HALF_UP. If structured coverage is null, the semantic percentage
alone supplies the recommendation score. A configured weight of zero preserves
structured ranking, including a null score when there are no criteria.

Missing interest text on either side uses `MISSING_EVIDENCE`. Missing/corrupt
model artifacts, missing packages or inference errors use `UNAVAILABLE`. Both
fall back to the structured score and return null semantic similarity/score,
UNKNOWN relevance and semantic weight zero. A failed batch falls back as a whole
to avoid inconsistent partial rankings. Loader failures are retried after a
60-second cooldown, allowing a repaired installation to recover without a
process restart. Exception messages and input content are not exposed or logged.

Sorting uses descending recommendation score, ascending unknown-evidence weight,
then stable opportunity/talent ID. Null scores sort last. When the feature is
disabled, the three new summary fields are omitted and structured ranking is used.

The UI shows recommendation score, interest similarity/relevance and fallback
state on cards. Details additionally show structured coverage, blend weights and
the existing per-requirement evidence. All shipped interface languages include
the new system messages; source profile text remains verbatim.

The additive contract is version `0.1.3-draft`. See [OpenAPI](api/openapi.json),
[recommendation example](api/examples/recommendations-semantic.json) and
[detail example](api/examples/owner-match-semantic.json). These examples are
synthetic interface fixtures, not benchmark measurements.

## Installation and configuration

Normal backend requirements now include `requirements-semantic.txt`. Both native
setup programs install these packages and prepare the pinned public model. The
Docker image downloads and verifies its model during build, stores it outside the
persistent data volume at `/app/models/minilm`, and runs inference without network
access. No request or application startup downloads anything.

Existing native environments can prepare their model from the repository root:

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
.\.venv\Scripts\python.exe -m backend.src.features.matching.prepare_semantic
```

On macOS/Linux, substitute `.venv/bin/python`. The preparation command reuses
matching files, downloads missing/corrupt artifacts, verifies SHA-256 checksums
and executes a real encoding. It accepts `--model-dir` for a custom location.
It neither reads the application database nor rewrites historical benchmark data.

| Setting | Default | Meaning |
|---|---|---|
| `SEMANTIC_MATCHING_ENABLED` | `true` | Enable application semantic ranking; accepts true/false |
| `SEMANTIC_MATCHING_WEIGHT` | `0.3` | Semantic share of hybrid ranking, from 0 to 1 |
| `SEMANTIC_MODEL_DIR` | `data/us13/model` (native); `/app/models/minilm` (Docker) | Local verified model directory; relative paths resolve from repository root |

Restart an existing backend after updating source or configuration. Rebuild
existing Docker images. No database migration or new endpoint is required.

The fixed model/revision/checksums, tokenizer limits, batch size and relevance
thresholds live in `backend/src/features/matching/semantic_config.json`, which is
packaged with the application. They match the original experiment's model and
selected thresholds. Ranking weights are a product rule rather than a newly
measured quality claim. The original small synthetic corpus, partial-relevance
errors and untested languages remain limitations of the model.

## Verification

`backend/tests/test_semantic_matching.py` covers actual owner/team HTTP endpoints,
ranking before pagination, request batching, all interest representations,
visibility/consent changes, reconfirmation, fallback and a real pinned MiniLM run.
Deterministic encoder doubles isolate plumbing and failure paths; the separately
marked real-model test does not replace inference with a double. CI downloads the
model and runs both the historical US-13 suite and application integration tests.

`frontend/tests/task-20-semantic.test.js` covers card/detail scores, English/Chinese
messages, team matching and missing-input/model fallback. Existing baseline
fixtures explicitly disable semantic matching to retain independent structured
coverage checks.

Executed verification on 27 October 2026: full backend suite with required real
frontend integration **694 passed, 14 skipped**; full frontend suite **260 passed**;
frontend production-build assertions, formatting and all **48 indexed API examples**
passed. The real Linux Docker image built successfully, and its non-root user
executed the bundled model in a read-only temporary container with networking
disabled. Existing application containers and databases were not changed.
