"""Free-text skill storage and a read adapter for existing tag-backed data."""

from copy import deepcopy
import hashlib
import re
import unicodedata

from sqlalchemy import select

from .models import ProfileSkill, ProfileSkillDetails, Tag
from ..shared.validation import invalid


def normalise_title(value):
    return " ".join(unicodedata.normalize("NFKC", value).split()).casefold()


def skill_id(value):
    return "skill_" + hashlib.sha256(value.encode()).hexdigest()[:24]


def legacy_skill(tag_id, claim, evidence, label):
    return {"id": skill_id("legacy:" + tag_id),
            "title": ("No " if claim == "DOES_NOT_HAVE" else "") + label,
            "evidenceText": evidence}


def read_skills_many(db, talent_ids):
    """Callers pass only owners whose skills they may read."""
    if not talent_ids:
        return {}
    rows = {row.talent_id: deepcopy(row.skills) for row in db.scalars(
        select(ProfileSkillDetails).where(ProfileSkillDetails.talent_id.in_(talent_ids)))}
    missing = set(talent_ids) - rows.keys()
    for talent_id in missing:
        rows[talent_id] = []
    if missing:
        for row, label in db.execute(select(ProfileSkill, Tag.label).join(Tag).where(
                ProfileSkill.talent_id.in_(missing)).order_by(ProfileSkill.talent_id, ProfileSkill.position)):
            rows[row.talent_id].append(legacy_skill(row.tag_id, row.claim, row.evidence_text, label))
    return rows


def replace_skills(db, talent_id, skills):
    row = db.get(ProfileSkillDetails, talent_id)
    if row is None:
        row = ProfileSkillDetails(talent_id=talent_id)
        db.add(row)
    row.skills = deepcopy(skills)


def check_skills(skills, field):
    ids = [item["id"] for item in skills]
    if len(set(ids)) != len(ids):
        invalid(field, "Each skill record ID must be unique.")
    for index, item in enumerate(skills):
        if not any(not char.isspace() and not unicodedata.category(char).startswith("C")
                   for char in item["title"]):
            invalid(f"{field}[{index}].title", "Enter a visible skill title.")


def upgrade_extraction_skills(db, result):
    """Old READY results stay reviewable without changing their stored JSON."""
    result = deepcopy(result)
    skills = result.get("suggestedSections", {}).get("skills", [])
    labels = dict(db.execute(select(Tag.id, Tag.label).where(Tag.id.in_(
        [item["tagId"] for item in skills if "tagId" in item]))).all())
    if "skills" in result.get("suggestedSections", {}):
        result["suggestedSections"]["skills"] = [
            legacy_skill(item["tagId"], item["claim"], item["evidenceText"], labels.get(item["tagId"], item["tagId"]))
            if "tagId" in item else item for item in skills]
    return result


def matching_skills(skills, labels):
    """Resolve exact titles against existing opportunity criteria, without storing tags.

    Unrelated prose, course names and substrings never establish a match. Explicit
    legacy negatives remain negatives after migration to the two text fields.
    """
    by_title = {}
    for item in skills:
        title = normalise_title(item["title"])
        negative = re.match(r"^(?:no|not|without|lack(?:ing)?(?: of)?|does not have)\s+(.+)$", title)
        name = negative[1] if negative else title
        evidence = normalise_title(item["evidenceText"])
        prefix = re.split(r"(?<!\w)" + re.escape(name) + r"(?!\w)", evidence, maxsplit=1)[0]
        evidence_negative = (prefix != evidence and re.search(
            r"\b(?:no|not|without|lack|lacking)\b(?!\s+only\b)[^.;]*$", prefix))
        if re.search(r"\b(?:want to learn|plan to learn|interested in learning|wish to learn)\b", title + " " + evidence):
            continue
        value = {**item, "label": item["title"],
                 "claim": "DOES_NOT_HAVE" if negative or evidence_negative else "HAS"}
        if name not in by_title or value["claim"] == "DOES_NOT_HAVE":
            by_title[name] = value
    return {tag_id: {**by_title[normalise_title(label)], "label": label} for tag_id, label in labels.items()
            if normalise_title(label) in by_title}
