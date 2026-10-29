# US-13 / BE-46: executed semantic interest comparison

Historical benchmark record. On 27 October 2026, [application semantic interest
ranking](../semantic-matching.md) was added as a separate integration. The original
experiment's outputs and OMIT decision below are retained unchanged as evidence
of its limitations; they do not describe the current application's feature state.

Implemented and executed on **23 October 2026**. The experiment is complete;
**omit semantic integration from application recommendations** for this delivery.
The current interest baseline remains available without a model or embedding
packages. The separate free-text opportunity skill extension is documented in
[free-text skills](../free-text-skills.md#opportunity-skill-requirements).

## Delivered evidence

- [Semantic implementation](../../backend/src/features/matching/semantic.py): real
  MiniLM ONNX inference, masked mean pooling, L2 normalisation and cosine similarity.
- [Runnable comparison](../../backend/src/features/matching/evaluate_semantic.py):
  executes the unchanged interest baseline and the semantic method, selects
  thresholds using tuning data only, measures costs and records errors/fallback.
- [Frozen model/configuration](us13/config.json), [inputs and relevance labels](us13/dataset.json),
  [actual per-pair outputs and metrics](us13/results.json).
- [Optional dependencies](../../backend/requirements-semantic.txt),
  [regression tests](../../backend/tests/test_us13.py), and a dedicated CI job
  `semantic_evaluation` which downloads the pinned artifacts, runs inference and
  retains its fresh report even on failure.

The report records SHA-256 hashes for the dataset, configuration and all three
implementation files, plus installed package versions and the execution platform.
These text hashes normalise CRLF to LF before hashing, as recorded by
`textChecksumNormalization`, so Windows and Linux checkouts verify the same saved
evidence. Model artifact hashes still verify the exact downloaded bytes.
Model files remain in ignored `data/us13/model/`; no weights, personal data,
credentials, vectors or database changes are needed in source control.

## Reproduction

Run from the repository root, using the existing development environment.

Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-semantic.txt
.\.venv\Scripts\python.exe -m backend.src.features.matching.evaluate_semantic --download-model --output data/us13/latest.json
.\.venv\Scripts\python.exe -m pytest backend/tests/test_us13.py -q
```

macOS/Linux:

```sh
.venv/bin/python -m pip install -r backend/requirements-semantic.txt
.venv/bin/python -m backend.src.features.matching.evaluate_semantic --download-model --output data/us13/latest.json
.venv/bin/python -m pytest backend/tests/test_us13.py -q
```

Install the normal `backend/requirements-dev.txt` first on a fresh checkout.
`--download-model` is the only operation that uses the network. It downloads two
public files from the recorded Hugging Face commit and verifies their hashes.
Subsequent runs can omit that flag and execute entirely offline. To intentionally
replace the checked-in evidence, specify `--output docs/testing/us13/results.json`.
Normal runs write to ignored `data/` and do not change the saved benchmark.

A missing/corrupt model, missing dependency, inference failure or invalid vector
produces an **INCOMPLETE** report and a nonzero exit status. The report still
contains actual baseline results and explicitly labelled fallback results; these
are never reported as successful semantic inference. Missing permitted evidence
is UNKNOWN rather than a model failure. No application endpoint imports a model,
downloads weights or requires these optional packages.

## Data, labels and permissions

The versioned corpus contains **84 explicitly labelled pairs**:

- Tuning: 6 synthetic profiles × 3 opportunities = 18 pairs, covering marine
  conservation, solar energy and computational music.
- Final: 11 eligible synthetic profiles × 6 opportunities = 66 pairs, covering
  language, vision, graphs, medical imaging, climate and archival history.
- Three additional profiles test revoked discovery, stale confirmation and an
  unconfirmed profile. They enter neither method's candidate pool.

Profile and opportunity IDs and research topics are disjoint across splits.
Labels were authored as domain judgements **before executing either matcher**,
independently of tag overlap and similarity outputs. They are synthetic,
author-assigned labels, **not independently human-reviewed annotations**. No
claim of external expert or multi-annotator agreement is made. The label guide
and per-profile annotation notes are in the dataset; labels remain fixed during
threshold selection and final evaluation. A larger independently annotated
corpus is required before deployment.

Both methods receive the same current confirmed, opted-in, active talent pool
and published active synthetic opportunities. The experiment applies the
`researchInterests` visibility group before constructing either method's input,
before encoding/caching text and before constructing reports. A hidden-interest
profile stays in the unfiltered candidate pool with empty interest input and
UNKNOWN outcomes. Revoked/stale/unconfirmed profiles are excluded entirely.
Synthetic private sentinel strings are tested to stay out of model inputs and
reports. For application data, the corresponding trusted boundary is
`discoverable_profiles` followed by `visible_profiles` in `team_repository.py`;
`interest_input` accepts only those already-permitted fields. This CLI reads the
explicit dataset file and never reads a running application's database.

The frozen synthetic shared catalogue is used only in this experiment. It does
not create tags in the application. Text-only, shared-only, personal-only,
combined and missing/hidden examples all remain in the same cross-product pool.
Equivalent wording with no common ID, and a different shared ID for language
research, are evaluated without an exact-ID prefilter.

## Methods and score meaning

Semantic method: `minilm-interest-onnx-v1`, model
`sentence-transformers/all-MiniLM-L6-v2`, revision
`1110a243fdf4706b3f48f1d95db1a4f5529b4d41`, CPU ONNX Runtime, one inference thread,
384 dimensions, batches of at most 16 texts and truncation at 256 tokens. Inputs
use NFKC and collapsed whitespace. Interest text is primary; distinct shared and
personal labels supply context. Labels repeated across fields or already present
in text, including punctuation boundaries, are omitted. The resulting profile is
encoded once, without summing label scores or taking the maximum across duplicate
labels. Opportunity input uses research-area text plus distinct INTEREST labels;
skills, resumes, qualifications, provenance and unrelated descriptions are excluded.

The model is frozen; there is no training, random sampling or random seed.
A grid of partial/relevant thresholds is scored only on tuning labels, maximising
four-label macro F1, then accuracy, then preferring higher thresholds on ties.
Selected thresholds are **partial ≥ 0.45**, **relevant ≥ 0.75**. Lower similarities
are UNRELATED; absent permitted text is UNKNOWN. Cosine is stored separately
from the application's percentage score. Relevance labels do not establish
skills, credentials or an application MATCHED/GAP status.

Baseline: the existing `engine.evaluate_opportunity` implementation,
`tag-coverage-v1`, receives only permitted shared IDs. Each corpus opportunity has
one required INTEREST criterion, so its actual MATCHED/PARTIAL/UNKNOWN result can
be mapped to RELEVANT/PARTIAL/UNKNOWN for comparison. Required/preferred weights
remain 2/1, partial value 0.5, ROUND_HALF_UP to two decimals, UNKNOWN score zero,
and no-criteria score null. The baseline deliberately cannot consume text-only
or personal-only interests. Unmatched shared IDs remain UNKNOWN even when the
domain label is UNRELATED; the report does not silently reinterpret missing
baseline evidence as an explicit negative claim. All raw summaries are preserved.
The separate application `skill-title-interest-tags-v2` extension is not used
in this interest benchmark.

Retrieval counts RELEVANT/PARTIAL as positive for both methods. Macro F1 averages
all four labels, including zero when a label has no predicted positives. NDCG@3
ranks each identical opportunity-specific pool by descending method score, with
missing scores last and talent ID as the deterministic tie-breaker. Gains are
3 for RELEVANT, 1 for PARTIAL, 0 otherwise. Per-mode metrics, all predictions,
incorrect pairs, unknown counts and the three eligibility exclusions are saved.

## Measured final results

| Measure | Structured baseline | Semantic |
|---|---:|---:|
| Four-label accuracy | 0.2121 | 0.8788 |
| Macro F1 (four labels) | 0.1789 | 0.6968 |
| Retrieval precision | 1.0000 | 1.0000 |
| Retrieval recall | 0.1429 | 0.5714 |
| Retrieval F1 | 0.2500 | 0.7273 |
| NDCG@3 | 0.4326 | 0.9710 |

Baseline incorrect pairs: **52 / 66**; semantic incorrect pairs:
**8 / 66**. The baseline has 64 UNKNOWN predictions versus 12 for the
semantic method. Much of the gain is broader permitted-input coverage, rather
than a claim that embeddings outperform tags when both have the same full text.
The report separately breaks results down by input representation.

The semantic method has no false-positive retrievals on this small final pool,
but misses all six author-labelled PARTIAL cases. Two fully relevant shared-only
interests are also downgraded to PARTIAL. These are actual incorrect outputs:

| Talent | Opportunity | Label | Prediction | Cosine |
|---|---|---|---|---:|
| eval_vision | eval_cv | RELEVANT | PARTIAL | 0.6571 |
| eval_vision | eval_health | PARTIAL | UNRELATED | 0.3408 |
| eval_medical | eval_cv | PARTIAL | UNRELATED | 0.2987 |
| eval_broad_ml | eval_nlp | PARTIAL | UNRELATED | 0.2525 |
| eval_broad_ml | eval_cv | PARTIAL | UNRELATED | 0.2953 |
| eval_broad_ml | eval_gnn | PARTIAL | UNRELATED | 0.2534 |
| eval_broad_ml | eval_health | PARTIAL | UNRELATED | 0.4232 |
| eval_language_alias | eval_nlp | RELEVANT | PARTIAL | 0.4604 |

## Measured practical costs

The saved run used Python 3.12.14 on Windows x86-64, CPU only. One process encoded
**23 unique permitted texts**, with **zero truncations and zero inference errors**.

| Measurement | Saved run |
|---|---:|
| Model + tokenizer artifact size | 90,871,461 bytes (86.66 MiB) |
| Local model load including imports and checksum verification | 351.91 ms |
| Batched encoding of 23 unique texts | 72.22 ms |
| Baseline evaluation, 84 pairs total | 0.305 ms |
| Full comparison including threshold selection, excluding model load | 89.32 ms |
| Comparison process CPU time | 93.75 ms |
| Whole-process peak resident memory | 313.24 MiB |
| Paid API calls / external inference requests | 0 / 0 |

These are one-run local measurements, not production latency percentiles or
incremental model-only memory. Inputs were deduplicated and encoded once per
run; all 84 pair outputs reuse that run's vectors. Encoding and model loading
are recorded separately to avoid presenting cached cosine cost as end-to-end
semantic latency. The model was already downloaded for this saved run; first-run
download time depends on the network. The implementation uses no vector database
and sends no profile text to a hosted inference service.

## Adoption and fallback decision

**OMIT application semantic integration.** Paraphrase coverage and ranking improve,
but the partial-relevance failures, 11-profile final corpus and zero independent
human reviewers do not support changing production scores or thresholds.
The pre-recorded exploratory adoption gates require at least 50 final profiles,
two independent human reviewers, retrieval precision ≥ 0.9 and macro-F1 gain ≥ 0.1.
These gates are engineering safeguards, not a statistical power calculation.
The size/review gates fail; the partial-relevance errors give additional evidence
against adoption. Thresholds and labels were not changed after inspecting final
errors. Broader languages, negation, compound interests, adversarial inputs,
long-text truncation and real research data remain unevaluated.

Keep this runnable experiment, model configuration and actual outputs for later
improvement. The application continues its structured interest algorithm, with
the separately delivered free-text skill path where applicable. Missing model
files/packages have no effect on existing endpoints. Tests exercise both the
experiment's incomplete/error reports and actual HTTP recommendations with all
optional semantic imports disabled. No semantic explanation is added to US-18,
and similarity never creates a confirmed qualification or skill claim.

## Verification record

- Cross-platform checksum correction: **12 US-13 tests passed**, including LF
  and CRLF CLI inputs and source files, corrupt-model rejection and real-model
  reproduction. Regenerated saved evidence has identical per-pair outputs,
  thresholds, metrics and adoption decision; the costs above reflect that rerun.
- Full backend suite including real frontend HTTP workflows: **521 passed,
  6 skipped** (optional isolated Docker/MySQL cases).
- Frontend suite: **193 passed**; formatting and production build passed.
- Final focused US-13/opportunity-skill rerun: **21 passed**, including the
  real model, empty skill vocabulary and additive legacy-schema upgrade.
- Focused tests also cover real pinned-model reruns, saved-input/implementation
  hashes, missing/corrupt artifacts, eligibility/visibility, deduplication,
  fallback, arbitrary opportunity skill names with an empty SKILL vocabulary,
  atomic validation/conflicts, legacy storage upgrade and private skill evidence.

The real-model regression requires the optional model/dependencies locally; CI's
separate semantic job installs/downloads them and runs it explicitly. Unit
failure-path tests do not substitute mocked scores for the saved real evaluation.

## Primary method references

- [Model card and pooling example](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2)
- [Sentence Transformers ONNX guidance](https://sbert.net/docs/sentence_transformer/usage/efficiency.html#onnx)
- [Pinned model export](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2/blob/1110a243fdf4706b3f48f1d95db1a4f5529b4d41/onnx/model.onnx)
