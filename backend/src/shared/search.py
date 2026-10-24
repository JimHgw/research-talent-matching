"""Strict search inputs and engine-independent Unicode text comparisons."""

import re
from datetime import datetime, timezone

from flask import request
from sqlalchemy import select

from ..db.models import Tag
from ..db.skills import matching_skills, normalise_title, skill_claims
from .universities import university_code
from .validation import invalid

OPPORTUNITY_TYPES = ("PHD", "MASTERS", "RESEARCH_ASSISTANT", "POSTDOC", "OTHER")
ATTRIBUTES = ("university", "disciplineGroup", "discipline", "researchArea", "opportunityType")
SEARCH_FIELDS = ("title", "university", "discipline", "researchArea", "description")
ATTRIBUTE_LIMITS = {"university": 200, "disciplineGroup": 16, "discipline": 200,
                    "researchArea": 300, "opportunityType": 32}


def parse_datetime(value, field):
    # RFC3339 requires a time and explicit offset; fromisoformat alone is more permissive.
    if not isinstance(value, str) or not re.fullmatch(
            r"\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:[Zz]|[+-](?:[01]\d|2[0-3]):[0-5]\d)", value):
        invalid(field, "Use an RFC3339 date-time with an explicit UTC offset.")
    try:
        result = datetime.fromisoformat(value.upper().replace("Z", "+00:00"))
        return result.astimezone(timezone.utc).replace(tzinfo=None)
    except (ValueError, OverflowError):
        invalid(field, "Use a valid RFC3339 date-time.")


def search_parameters(db, *, talent=False, scope=False):
    multi = ("skillTagId", "interestTagId") if talent else ATTRIBUTES
    singles = ("q", "skill", "university") if talent else ("q", "deadlineFrom", "deadlineTo")
    allowed = {*multi, *singles, "page", "pageSize"}
    if scope:
        allowed.add("scope")
    result = {}
    for key in request.args:
        if key not in allowed:
            invalid(key, "Unsupported search parameter.")
        values = request.args.getlist(key)
        if key in ("scope", "page", "pageSize"):
            continue  # Their existing strict validators handle these values.
        if key in singles and len(values) != 1:
            invalid(key, "Supply this parameter only once.")
        limit = 200 if key in ("q", "skill") else ATTRIBUTE_LIMITS.get(key, 64)
        if key.startswith("deadline"):
            result[key] = parse_datetime(values[0], key)
            continue
        if any(not normalise_title(value) or len(value) > limit for value in values):
            invalid(key, f"Use non-blank text of at most {limit} characters.")
        if key == "disciplineGroup" and any(v not in ("STEM", "BUSINESS") for v in values):
            invalid(key, "Choose STEM or BUSINESS.")
        if key == "opportunityType" and any(v not in OPPORTUNITY_TYPES for v in values):
            invalid(key, "Choose a supported opportunity type.")
        if talent and key == "university":
            code = university_code(values[0])
            if code is None:
                invalid(key, "Choose a Group of Eight university.")
            result[key] = code
        elif key in ("skillTagId", "interestTagId"):
            kind = "SKILL" if key == "skillTagId" else "INTEREST"
            known = set(db.scalars(select(Tag.id).where(Tag.kind == kind, Tag.id.in_(values))))
            if set(values) - known:
                invalid(key, f"Select existing shared {kind} tags.")
            result[key] = set(values)
        else:
            result[key] = [normalise_title(value) for value in values] if key in multi else normalise_title(values[0])
    if ("deadlineFrom" in result and "deadlineTo" in result
            and result["deadlineFrom"] >= result["deadlineTo"]):
        invalid("deadlineTo", "The upper deadline bound must be later than the lower bound.")
    return result


def opportunity_matches(opportunity, filters):
    content = opportunity["content"]
    if "q" in filters and not any(filters["q"] in normalise_title(content[field]) for field in SEARCH_FIELDS):
        return False
    for field in ATTRIBUTES:
        if field in filters and normalise_title(content.get(field) or "") not in filters[field]:
            return False
    if "deadlineFrom" in filters or "deadlineTo" in filters:
        deadline = content.get("deadlineAt")
        if deadline is None:
            return False
        deadline = parse_datetime(deadline, "content.deadlineAt")
        if "deadlineFrom" in filters and deadline < filters["deadlineFrom"]:
            return False
        if "deadlineTo" in filters and deadline >= filters["deadlineTo"]:
            return False
    return True


def _searchable_text(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from _searchable_text(item)
    elif isinstance(value, dict):
        for key, item in value.items():
            if key != "id":
                yield from _searchable_text(item)


def talent_matches_filters(talent, filters, labels):
    # This function receives ONLY the current permitted projection, never the profile.
    fields = talent["fields"]
    if "skill" in filters:
        claims = skill_claims(fields.get("skills", [])).values()
        if not any(claim["claim"] == "HAS" and any(filters["skill"] in normalise_title(claim[key])
                   for key in ("title", "evidenceText")) for claim in claims):
            return False
    if "university" in filters and not any(
            university_code(row["institution"]) == filters["university"] for row in fields.get("education", [])):
        return False
    if "skillTagId" in filters:
        skills = matching_skills(fields.get("skills", []), labels)
        if not any(skills.get(tag, {}).get("claim") == "HAS" for tag in filters["skillTagId"]):
            return False
    if "interestTagId" in filters and not filters["interestTagId"].intersection(fields.get("researchInterests", [])):
        return False
    if "q" in filters:
        strings = [text for key, value in fields.items() if key != "researchInterests"
                   for text in _searchable_text(value)]
        strings.extend(labels[tag] for tag in fields.get("researchInterests", []) if tag in labels)
        if not any(filters["q"] in normalise_title(text) for text in strings):
            return False
    return True
