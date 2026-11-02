# Requirement-level semantic scoring

Implemented on 2 November 2026. Recommendation lists, discovery, shortlists and
both match-detail endpoints now score each published requirement separately.
This replaces the former global 70% coverage / 30% interest blend.

## Scoring

Each requirement has `scoring.score` from 0 to 100, a `weight`, a `contribution`,
a scoring `method`, optional similarity and the permitted source records used.

```
weight(REQUIRED) = 2
weight(PREFERRED) = 1
recommendationScore = sum(requirement score * weight) / sum(weights)
contribution = requirement score * weight / sum(weights)
```

Individual scores and the final total are rounded HALF_UP to two decimals.
Displayed contributions may differ from their sum by a rounding cent. Missing
requirements remain in the denominator and contribute zero. No requirements
means a null total; an opportunity's general research area cannot add a bonus.
For example, scores 80 (required), 60 (preferred) and 0 (required) yield 44.

Confirmed complete structured matches score 100. An explicit confirmed skill gap
scores zero. Other requirements compare their individual criteria with permitted
records of the corresponding kind. Each skill/interest criterion uses its best
matching source; their scores are averaged. Semantic similarity below 0.45
contributes zero; otherwise its nonnegative cosine similarity is multiplied by
100. Existing structured partial credit provides a floor. Relevance is RELEVANT
at 0.75+, PARTIAL at 0.45+, otherwise UNRELATED. These thresholds are product
rules and have not been calibrated against a new labelled multilingual corpus.

Academic requirements choose the best single record after scoring its criteria;
criteria cannot be assembled from unrelated degrees or projects. Qualification,
organisation identity and output type require exact normalized equality. Project
and output descriptions can explain the title criterion. A similar subject does
not establish a different degree level or output type.

Skill denials and statements about wanting to learn do not supply positive
semantic skill evidence. Interests cannot supply skill or qualification credit.

## Inputs and evidence

- SKILL: confirmed positive skill titles, with denials considered separately.
- INTEREST: confirmed research interest text, shared labels and personal labels.
- EDUCATION: qualification and discipline from a permitted education record.
- RESEARCH_EXPERIENCE: title/description and organisation from a permitted record.
- RESEARCH_OUTPUT: title/description and type from a permitted output record.

Full resumes, original documents, unrelated profile fields and hidden records are
not model inputs. Active accounts, current confirmation, discovery consent,
visibility and filters are checked before constructing model inputs. Profile
changes require reconfirmation; visibility changes apply on the next request.
No texts or vectors are persisted or cached between requests.

`summary.score`, `algorithmVersion`, requirement `status` and `evidence` retain
their structured evidence meaning. The separately displayed requirement score
can therefore be high while the structured evidence badge remains UNKNOWN.
The interface explicitly distinguishes semantic relevance from confirmed support.
`recommendationScore` is the weighted requirement total used by cards and sorting;
`rankingAlgorithmVersion` is `requirement-semantic-v1`. `semanticRequirements`
reports the model status, total importance weight and model version.
`semanticInterest` remains an explanatory diagnostic with weight zero; it is not
added again to the total. The API contract is `0.1.4-draft`; see the synthetic
[detail example](api/examples/owner-match-requirement-semantic.json).

## Model and installation

The application uses the pinned public
[paraphrase-multilingual-MiniLM-L12-v2 model](https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2),
with its official CPU uint8 ONNX export, 384-dimensional vectors, masked mean
pooling and L2 normalization. Model identity, revision, SHA-256 checksums, token
limits and thresholds are in `backend/src/features/matching/semantic_config.json`.
The tokenizer uses its own `<pad>` token and ID. Each distinct text is inferred
separately because dynamic int8 batch activation ranges otherwise change scores
between list and detail requests. Request-level text deduplication and a shared
encoder lock remain in place.

Native environments can install/prepare from the repository root:

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
.\.venv\Scripts\python.exe -m backend.src.features.matching.prepare_semantic
```

Use `.venv/bin/python` on macOS/Linux. The default native model directory is now
`data/semantic/model`; frozen US-13 artifacts in `data/us13/model` are preserved.
`SEMANTIC_MODEL_DIR` can override the location. Docker continues to prepare its
model at build time in `/app/models/minilm`, outside the persistent data volume.
No startup or request downloads models. Restart native backends and rebuild
existing Docker images after updating. No database migration is needed.

`SEMANTIC_MATCHING_ENABLED` defaults to true. Disabling it preserves structured
matching and omits the additional scoring fields. `SEMANTIC_MATCHING_WEIGHT`
remains accepted/validated for configuration compatibility, but no longer blends
an extra global interest score into the requirement total.

Missing evidence uses structured scores. Missing/corrupt artifacts, dependency
failures or inference errors fall back to structured per-requirement scores for
the entire batch, preserving consistent ordering and HTTP availability. Failures
retry after 60 seconds. Private content and exception messages are not logged or
returned. Sorting happens before pagination and uses the weighted total, lower
unknown-evidence weight, then stable ID; null totals sort last.

## Verification

`backend/tests/test_requirement_scoring.py` covers every requirement kind,
importance weighting, missing-input denominators, multi-skill criteria, academic
record boundaries, fixed degree/type constraints, denials, privacy,
reconfirmation, real Chinese synonym inference, unrelated controls and
list/detail consistency. `backend/tests/test_semantic_matching.py` covers HTTP
recommendations, discovery, shortlists, all interest representations, atomic
fallback and recovery. Frontend tests cover scores, contributions, sources,
English/Chinese wording and model fallback. Legacy fixtures and the frozen US-13
experiment remain available for independent regression checks.

Executed verification on 2 November 2026: full backend suite with required real
frontend integration **743 passed, 14 skipped**; full frontend suite **262 passed**;
production build, formatting and all **49 indexed API examples** passed. The real
multilingual model ran in the Chinese HTTP regression and produced stable scores
across list/detail requests. Docker image execution was not part of this run.
