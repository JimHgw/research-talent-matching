# US-06 Sprint 1 Matching Evaluation

## 1. Purpose

This evaluation assesses the Sprint 1 tag-based matching algorithm using
synthetic and de-identified test data with manually labelled expected results.

The evaluation focuses on whether the current matching implementation produces
the expected requirement statuses and summary results for representative normal
and edge cases.

The evaluated algorithm version is:

`tag-coverage-v1`

---

## 2. Evaluation Dataset

The evaluation dataset is implemented in:

`backend/tests/test_us06.py`

All profiles and opportunities used in the evaluation are synthetic and contain
no real personal information.

The labelled dataset contains the following representative scenarios:

| Scenario | Purpose |
|---|---|
| Perfect match | All required and preferred tags are supported |
| Partial multi-tag match | Only part of a multi-tag requirement is supported |
| Explicit negative gap | A required skill has a confirmed `DOES_NOT_HAVE` claim |
| Missing information | No evidence exists for requested requirements |
| Unmatched tags | Profile tags are unrelated to opportunity requirements |
| Incomplete profile | Only part of the relevant profile information is available |
| No matching criteria | Opportunity contains no requirements |

Each case contains manually specified expected requirement statuses and expected
summary values.

---

## 3. Evaluation Measures

Three reproducible measures are used.

### 3.1 Requirement-status accuracy

The percentage of individual opportunity requirements for which the algorithm
produces the manually labelled expected status.

Possible statuses are:

- `MATCHED`
- `PARTIAL`
- `GAP`
- `UNKNOWN`

### 3.2 Summary exact-match accuracy

The percentage of labelled evaluation cases where the generated summary matches
all manually specified expected summary values.

The checked summary fields include:

- `score`
- `unknownWeightPercent`
- `requiredGapCount`
- `evaluationStatus`

### 3.3 Incorrect labelled case count

The evaluation records the IDs of any cases where either the requirement
statuses or expected summary values differ from the manual labels.

---

## 4. Results

The current labelled Sprint 1 evaluation dataset passes successfully.

| Measure | Result |
|---|---:|
| Requirement-status accuracy | 100% |
| Summary exact-match accuracy | 100% |
| Incorrect labelled cases | 0 |

All evaluation cases also confirmed the expected algorithm version:

`tag-coverage-v1`

The evaluation is executed automatically as part of the backend pytest suite and
therefore runs in the GitLab CI pipeline.

---

## 5. Behaviour Confirmed by Testing

The evaluation confirmed the following Sprint 1 matching behaviour.

### MATCHED

A requirement is `MATCHED` when all requested tag IDs have confirmed positive
support in the profile.

### PARTIAL

A requirement is `PARTIAL` when at least one requested tag has confirmed
positive support but not all requested tags are supported.

### GAP

A skill requirement becomes `GAP` when at least one requested skill has an
explicit confirmed `DOES_NOT_HAVE` claim.

An explicit negative claim takes priority over positive evidence for other tags
within the same requirement.

### UNKNOWN

A requirement is `UNKNOWN` when there is insufficient confirmed evidence for
the requested tags.

Missing information is therefore distinguished from an explicit negative claim.

### Insufficient criteria

When an opportunity contains no requirements, the result uses:

`INSUFFICIENT_CRITERIA`

and no numerical matching score is produced.

---

## 6. Identified Limitations

Although all manually labelled Sprint 1 cases passed, the evaluation identified
several limitations of the current matching approach.

### 6.1 Exact tag-ID matching

The algorithm currently relies on exact tag IDs.

Two semantically similar skills will not match unless they use the same tag ID.

For example, conceptually related terms such as:

- `Machine Learning`
- `ML`
- `Statistical Learning`

are not automatically treated as equivalent unless they are represented by the
same confirmed tag.

Semantic matching using embeddings or another similarity method is outside the
current Sprint 1 algorithm.

### 6.2 Fixed PARTIAL value

Every `PARTIAL` requirement contributes a fixed value of `0.5`.

This means a requirement containing three requested tags receives the same
partial value whether one tag or two tags are supported.

The current scoring therefore does not represent the proportion of supported
tags within a partially matched requirement.

### 6.3 Fixed importance weights

Sprint 1 uses fixed weights:

- `REQUIRED = 2`
- `PREFERRED = 1`

These values are not configurable per opportunity and do not express finer
differences in requirement importance.

### 6.4 UNKNOWN and GAP both contribute zero score

Both `UNKNOWN` and `GAP` currently contribute zero to the numerical score.

They remain distinguishable in the explanation and in
`unknownWeightPercent` / `requiredGapCount`, but the main score itself does not
capture the qualitative difference between missing information and an explicit
negative claim.

### 6.5 Small synthetic evaluation dataset

The current evaluation uses a deliberately small synthetic dataset intended to
verify Sprint 1 behaviour.

A 100% result on this dataset demonstrates consistency with the manually defined
Sprint 1 rules, but does not demonstrate matching quality on large-scale,
real-world university research data.

Future evaluation should use a larger synthetic or appropriately de-identified
dataset with more varied profiles and opportunities.

### 6.6 No semantic or contextual interpretation

The algorithm evaluates confirmed tags rather than interpreting broader profile
context.

It does not currently infer relevant skills from:

- free-text research descriptions,
- CV content that has not been converted into confirmed tags,
- related disciplines,
- synonyms,
- contextual similarity.

This is a planned area for later iterations.

---

## 7. Incorrect Matches

No incorrect matches were found in the current manually labelled Sprint 1
evaluation dataset.

This result should be interpreted as successful verification of the implemented
Sprint 1 matching rules rather than proof of general real-world matching
accuracy.

Any future case where the actual result differs from a manually labelled
expected result should be recorded here and added as a regression test.

---

## 8. Reproducibility

The evaluation can be reproduced by running the backend test suite.

From the `backend` directory:

```bash
python -m pytest
```
