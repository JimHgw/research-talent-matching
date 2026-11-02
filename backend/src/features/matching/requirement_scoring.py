"""Score each requirement against current, audience-permitted records only."""

from decimal import Decimal, ROUND_HALF_UP

from ...db.skills import normalise_title, skill_claims
from .academic_evidence import ACADEMIC_FIELDS
from .engine import VALUES, WEIGHTS
from .semantic import cosine, relevance

VERSION = "requirement-semantic-v1"
# Similar text cannot establish a degree level, organisation identity or output type.
EXACT_FIELDS = {"qualification", "organisation", "type"}


def rounded(value):
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def source(field, record_id, text, *, negative=False):
    return {"field": field, "recordId": record_id, "text": text, "negative": negative}


def cell(target, candidates, *, exact_only=False):
    return {"target": target, "candidates": [s for s in candidates if s["text"].strip()],
            "exactOnly": exact_only}


def targets(requirement, profile):
    if "skillTitles" in requirement:
        return requirement["skillTitles"]
    labels = profile.get("tagLabels", {})
    ids = requirement.get("tagIds", [])
    if requirement["kind"] == "INTEREST" and len(ids) <= 1:
        return [requirement["label"]]
    if ids and all(key in labels for key in ids):
        return list(dict.fromkeys(labels[key] for key in ids))
    return [requirement["label"]]


def plan_requirement(result, profile):
    """A plan is alternatives of records; every record contains required criteria.

    Skills/interests may be supported by separate records. Academic criteria must
    be satisfied by one record, so unrelated degrees/projects cannot be combined.
    """
    req = result["requirement"]
    if result["status"] in ("MATCHED", "GAP"):
        return []
    kind = req["kind"]
    if kind == "SKILL":
        claims = skill_claims(profile.get("skillRecords", []))
        candidates = [source("skills", record["id"], title,
                             negative=record["claim"] == "DOES_NOT_HAVE")
                      for title, record in claims.items()]
        return [[cell(text, candidates) for text in targets(req, profile)]]
    if kind == "INTEREST":
        candidates = [source("researchInterestText", None, profile.get("researchInterestText", ""))]
        candidates += [source("researchInterests", key, label)
                       for key, label in profile.get("researchInterests", {}).items()]
        candidates += [source("customInterestTags", tag["id"], tag["label"])
                       for tag in profile.get("customInterestTags", [])]
        return [[cell(text, candidates) for text in targets(req, profile)]]
    if kind in ACADEMIC_FIELDS:
        criteria = req.get("criteria")
        if not criteria:
            return []
        field = ACADEMIC_FIELDS[kind]
        alternatives = []
        for record in profile.get(field, []):
            cells = []
            for key, expected in criteria.items():
                candidates = [source(field, record["id"], str(record.get(key) or ""))]
                # A project's/output's description can explain its title.
                if key == "title":
                    candidates.append(source(field, record["id"], record.get("description", "")))
                cells.append(cell(expected, candidates, exact_only=key in EXACT_FIELDS))
            alternatives.append(cells)
        return alternatives
    return []


def model_texts(plan):
    for alternative in plan:
        for item in alternative:
            if item["exactOnly"]:
                continue
            for candidate in item["candidates"]:
                if normalise_title(item["target"]) != normalise_title(candidate["text"]):
                    yield item["target"]
                    yield candidate["text"]


def score_cell(item, vectors, thresholds):
    best = 0.0
    best_match = None
    best_similarity = None
    semantic = False
    denied = False
    for candidate in item["candidates"]:
        exact = normalise_title(item["target"]) == normalise_title(candidate["text"])
        similarity = 1.0 if exact else None
        if not exact and not item["exactOnly"] and vectors is not None:
            similarity = cosine(vectors[item["target"]], vectors[candidate["text"]])
        if similarity is None:
            continue
        if candidate["negative"]:
            if exact or similarity >= thresholds["relevant"]:
                denied = True
            continue
        value = (max(0, similarity) * 100
                 if exact or similarity >= thresholds["partial"] else 0.0)
        if best_match is None or value > best:
            best = value
            best_similarity = similarity
            semantic = not exact
            best_match = {key: candidate[key] for key in ("field", "recordId", "text")}
            best_match.update(criterion=item["target"], similarity=similarity)
    if denied:
        return 0.0, None, None, False, True
    return best, best_match if best else None, best_similarity, semantic, False


def score_requirement(result, plan, vectors, thresholds, *, failed=False):
    baseline = float(VALUES[result["status"]] * 100)
    score, matches, similarity = baseline, [], None
    if result["status"] == "GAP":
        method = "EXPLICIT_GAP"
    elif result["status"] == "MATCHED":
        method = "EXACT"
    elif not plan or not any(c["candidates"] for row in plan for c in row):
        method = "MISSING_EVIDENCE"
    elif failed and list(model_texts(plan)):
        method = "UNAVAILABLE"
    else:
        method = "STRUCTURED"
        for alternative in plan:
            values = [score_cell(item, vectors, thresholds) for item in alternative]
            value = sum(item[0] for item in values) / len(values) if values else 0
            if value >= score:
                score = value
                matches = [item[1] for item in values if item[1] is not None]
                similarities = [item[2] for item in values if item[2] is not None]
                similarity = min(similarities) if similarities else None
                method = ("EXPLICIT_GAP" if any(item[4] for item in values) and not value
                          else "SEMANTIC" if any(item[3] for item in values)
                          else "EXACT" if value == 100 else "STRUCTURED")
    return {"score": rounded(score), "weight": WEIGHTS[result["requirement"]["importance"]],
            "method": method, "similarity": similarity,
            "relevance": relevance(similarity, thresholds), "matches": matches}


def enrich_requirements(results, plans, vectors, thresholds, *, failed=False):
    total_weight = sum(WEIGHTS[row["requirement"]["importance"]] for row in results)
    for result, plan in zip(results, plans, strict=True):
        scoring = score_requirement(result, plan, vectors, thresholds, failed=failed)
        scoring["contribution"] = rounded(scoring["score"] * scoring["weight"] / total_weight)
        result["scoring"] = scoring
    total = (rounded(sum(row["scoring"]["score"] * row["scoring"]["weight"]
                         for row in results) / total_weight) if total_weight else None)
    return total, total_weight
