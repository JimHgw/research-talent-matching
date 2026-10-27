"""Skill titles and source evidence, independent of any discipline vocabulary."""

import re

from ...db.skills import normalise_title, skill_id

SKILL_CATEGORIES = {
    "languages",
    "programming languages",
    "backend & data",
    "web development",
    "tools & systems",
    "core concepts",
    "frameworks",
    "databases",
    "tools",
    "methods",
}

def free_skill_suggestions(lines):
    found, issues, conflicts = {}, [], set()

    def add(title, evidence):
        title = title.strip(" \t•●⚫▪◦*-")
        if not title:
            return
        if re.search(r"\b(?:want to learn|plan to learn|interested in learning|wish to learn)\b", title + " " + evidence, re.I):
            issues.append(f"Learning intention needs manual review: {title[:100]}")
            return
        if len(title) > 350:
            issues.append("A skill title exceeds 350 characters; consult the original description and enter a shorter title.")
            return
        key = normalise_title(title)
        negative = re.match(r"^(?:no|not|without|lack(?:ing)?(?: of)?|does not have)\s+(.+)$", key)
        base = negative[1] if negative else key
        existing = found.get(base)
        if existing and existing["negative"] != bool(negative):
            conflicts.add(base)
            issues.append(f"Conflicting skill statements need manual review: {title[:100]}")
            return
        if existing:
            if evidence not in existing["sources"]:
                existing["sources"].append(evidence)
            return
        if len(found) >= 100:
            issues.append("More than 100 items; remaining items need manual review.")
            return
        found[base] = {"id": skill_id("extracted:" + key), "title": title,
                       "negative": bool(negative), "sources": [evidence]}

    pending = None
    for value, source in lines:
        labelled = re.match(r"^(?:title|skill(?: title)?|技能名称|技能标题)\s*[:：]\s*(.+)$", value, re.I)
        if labelled:
            if pending:
                add(*pending)
            pending = [labelled[1], ""]
            continue
        if pending is not None:
            evidence = re.sub(r"^(?:supporting evidence|evidence|description|佐证|证据)\s*[:：]\s*", "", value, flags=re.I)
            if value:
                pending[1] += ("\n" if pending[1] else "") + evidence
            else:
                add(*pending)
                pending = None
            continue
        category = re.match(r"^([^:：]+)[:：]\s*(.+)$", value)

        if (
            category
            and normalise_title(category[1]) in SKILL_CATEGORIES
        ):
            for title in re.split(r"[,;\t|、，；]", category[2]):
                add(title, source)
            continue
        # Sentences with commas remain a single free-text statement. Explicit
        # short lists can contain arbitrary tools, methods or business skills.
        values = [value] if re.search(r"[.!?。！？]", value) else re.split(r"[,;\t|、，；]", value)
        for candidate in values:
            if ":" in candidate or "：" in candidate:
                title, evidence = re.split(r"[:：]", candidate, maxsplit=1)
                add(title, evidence.strip())
            else:
                add(candidate, source)
    if pending:
        add(*pending)

    items = []
    for key, item in found.items():
        if key in conflicts:
            continue
        evidence = "\n".join(item.pop("sources"))
        item.pop("negative")
        item["evidenceText"] = evidence[:2000]
        if len(evidence) > 2000:
            issues.append("Supporting evidence was shortened to 2000 characters; consult the original file.")
        items.append(item)
    return items, issues
