"""Conservative, source-based suggestions; nothing here confirms a profile."""

import hashlib
import re
import unicodedata

from ...shared.validation import validator
from .academic import extract_academic_records
from .skill_suggestions import free_skill_suggestions


HEADINGS = {
    "education": ("education", "academic qualifications", "qualifications", "教育背景", "教育经历"),
    "courses": ("courses", "coursework", "relevant coursework", "academic transcript", "transcript", "相关课程", "课程"),
    "researchExperience": ("research experience", "research experiences", "科研经历", "研究经历"),
    "skills": ("skills", "technical skills", "programming skills", "专业技能", "技能"),
    "researchInterests": ("research interests", "research interest", "interests", "研究兴趣", "研究方向"),
    "researchOutputs": ("research outputs", "publications", "projects", "research projects", "科研成果", "研究成果"),
}
SCHEMAS = {
    "education": "Education", "courses": "Course",
    "researchExperience": "ResearchExperience", "researchOutputs": "ResearchOutput",
}
DEGREE = re.compile(r"\b(bachelor|master|doctor|ph\.?d|bsc|msc|beng|meng|diploma|certificate)\b", re.I)
YEAR_RANGE = re.compile(
    r"\b(?:(?:0?[1-9]|1[0-2])[./])?(\d{4})\s*[-–—]\s*"
    r"(?:(?:0?[1-9]|1[0-2])[./])?(\d{4}|present|current)\b",
    re.I,
)
COURSE = re.compile(r"^([A-Z]{2,8}\s?\d{3,5})\s*(?:[-–—:]\s*|\s+)(.+)$")
KEYS = {
    "institution": "institution", "university": "institution",
    "qualification": "qualification", "degree": "qualification",
    "discipline": "discipline", "major": "discipline",
    "start year": "startYear", "end year": "endYear",
    "name": "name", "course name": "name", "course": "name", "code": "code", "course code": "code",
    "title": "title", "organisation": "organisation", "organization": "organisation",
    "description": "description", "type": "type", "url": "url",
}
OTHER_HEADINGS = {"work experience", "employment", "professional experience", "awards",
                  "contact", "personal information", "references", "languages", "certifications",
                  "工作经历", "联系方式", "个人信息", "获奖经历", "自我评价"}

OTHER_HEADINGS |= {"additional information", "availability"}
def new_extraction_result(document_id):
    return {"documentId": document_id, "status": "READY", "suggestedSections": {},
            "uncertainFields": [], "warnings": ["Review all suggestions before saving."],
            "reviewRequired": True}


def _clean(value):
    return re.sub(r"^[\s•●⚫▪◦*\-]+", "", value).strip()

def _heading(line, names):
    for name in sorted(names, key=len, reverse=True):
        if line.casefold().rstrip(":：").strip() == name:
            return name, ""

        match = re.match(
            re.escape(name) + r"(?:\s*[:：]\s*|\t+| {2,})(.*)$",
            line,
            re.I,
        )
        if match:
            return name, match[1].strip()

    return None, ""

def _sections(text):
    aliases = {
        alias: section
        for section, names in HEADINGS.items()
        for alias in names
    }
    sections = {section: [] for section in HEADINGS}
    active = None

    for raw in text.splitlines():
        line = _clean(raw)
        heading, remainder = _heading(
            line, set(aliases) | OTHER_HEADINGS
        )

        if active == "skills" and heading == "languages" and remainder:
            sections[active].append((line, line))
        elif heading in aliases:
            active = aliases[heading]
            if remainder:
                sections[active].append((remainder, line))
        elif heading in OTHER_HEADINGS:
            active = None
        elif active:
            sections[active].append((line, line))

    return sections


def _fold(value):
    return " ".join(unicodedata.normalize("NFKC", value).split()).casefold()


def _tag_mentions(value, tags, kind):
    folded = _fold(value)
    for tag in tags:
        if tag["kind"] != kind:
            continue
        label = _fold(tag["label"])
        for match in re.finditer(r"(?<!\w)" + re.escape(label) + r"(?!\w)", folded):
            yield match.start(), tag, folded[:match.start()]


def _tags(lines, tags, kind):
    found, issues = {}, []
    for values, source in lines:
        for name in re.split(r"[,;\t|、，；]|\b(?:but|however)\b", values, flags=re.I):
            name = _clean(name)
            if not name:
                continue
            mentions = sorted(_tag_mentions(name, tags, kind), key=lambda item: item[0])
            if not mentions:
                issues.append(f"Unrecognised item: {name[:100]}")
            for _, tag, before in mentions:
                if re.search(r"\b(?:want to learn|plan to learn|interested in learning|wish to learn)\b", _fold(name)):
                    issues.append(f"Learning intention needs manual review: {name[:100]}")
                    continue
                negative = bool(re.search(r"\b(?:no|not|without|lack|lacking)\b(?!\s+only\b)[^.;]*$", before))
                if kind == "INTEREST" and negative:
                    issues.append(f"Negative interest statement needs manual review: {name[:100]}")
                    continue
                existing = found.get(tag["id"])
                if existing:
                    continue
                if len(found) >= 100:
                    issues.append("More than 100 items; remaining items need manual review.")
                    continue
                found[tag["id"]] = tag["id"]
    return list(found.values()), issues


def _interest_details(lines, tags, shared_count):
    """Preserve source text; propose only short explicit labels, never invent them."""
    text = "\n".join(value for value, _ in lines).strip()
    personal, issues, seen = [], [], set()
    for value, _ in lines:
        for candidate in re.split(r"[,;\t|、，；]|\s+and\s+", value, flags=re.I):
            candidate = _clean(candidate)
            folded = _fold(candidate)
            if not candidate or folded in seen or list(_tag_mentions(candidate, tags, "INTEREST")):
                continue
            # Paragraphs remain free text. Only explicit, short list labels become proposals.
            if (len(candidate) > 100 or len(candidate.split()) > 12 or re.search(r"[.!?。！？:：]", candidate)
                    or re.match(r"(?:i\b|my\b|we\b|interested\b|not\b|no\b|focus\b)", folded)):
                continue
            if len(personal) + shared_count >= 100:
                issues.append("More than 100 interest tags; remaining labels are retained in the description.")
                continue
            seen.add(folded)
            personal.append({"label": candidate})
    if len(text) > 5000:
        text = text[:5000]
        issues.append("Interest description was shortened to 5000 characters; consult the original file.")
    return text, personal, issues


def find_skill_suggestions(text, tags):
    return free_skill_suggestions(_sections(text)["skills"])[0]


def find_interest_suggestions(text, tags):
    return _tags(_sections(text)["researchInterests"], tags, "INTEREST")[0]


def _output_fields_continue(block_keys, lines, start):
    """Complementary labelled paragraphs can be one output with layout gaps."""
    following_keys = set()
    for index in range(start, len(lines)):
        value = lines[index][0]
        if not value:
            if following_keys:
                break
            continue
        parts = re.split(r"[:\t]", value, maxsplit=1)
        key = KEYS.get(parts[0].strip().casefold())
        if (len(parts) != 2 or key not in ("title", "type", "description", "url")
                or key in following_keys):
            return False
        following_keys.add(key)
    return bool(following_keys) and block_keys.isdisjoint(following_keys)


def _records(section, lines):
    """Keep labelled blocks together; output layout gaps need not start a record."""
    block = []
    block_keys = set()
    for index, (value, _) in enumerate(lines):
        if not value and section == "researchOutputs" and block_keys:
            # Inspect the next paragraph once per run of blank lines. A repeated
            # field marks a new record, including URL-first paragraphs with a title.
            if index and not lines[index - 1][0]:
                continue
            if _output_fields_continue(block_keys, lines, index + 1):
                continue
        key = KEYS.get(re.split(r"[:\t]", value, maxsplit=1)[0].strip().casefold())
        repeated = key is not None and key in block_keys
        delimited = key is None and ("|" in value or "\t" in value
                     or (section == "courses" and COURSE.match(value))
                     or (section == "researchOutputs" and re.match(r"^(Publication|Project|Other)\s*:", value, re.I)))
        if not value or repeated or delimited:
            if block:
                yield block
                block = []
            block_keys = set()
        if delimited:
            yield [value]
        elif value:
            block.append(value)
            if key is not None:
                block_keys.add(key)
    if block:
        yield block


def _labelled(rows):
    fields = {}
    unknown = []
    for row in rows:
        parts = re.split(r"[:\t]", row, maxsplit=1)
        mapped = KEYS.get(parts[0].strip().casefold())
        if len(parts) == 2 and mapped:
            fields[mapped] = parts[1].strip()
        else:
            unknown.append(row)
    return fields, unknown


def _years(value):
    match = YEAR_RANGE.search(value)
    if not match:
        return None, None
    start, end = match.groups()
    return int(start), int(end) if end.isdigit() else None


def _education(rows, fields):
    result = {"institution": "", "qualification": "", "discipline": "",
              "startYear": None, "endYear": None}
    if fields:
        result.update({key: fields[key] for key in result if key in fields})
        for key in ("startYear", "endYear"):
            if key in fields:
                value = fields[key]
                if not re.fullmatch(r"\d{4}", value) and value.casefold() not in ("present", "current", "unknown", ""):
                    return None
                result[key] = int(value) if value.isdigit() else None
    else:
        joined = " ".join(rows)
        compact = re.fullmatch(
            r"(.+?)\s*(?:—{2,}|–{2,})\s*(.+)", joined
        )

        if (
            compact
            and not DEGREE.search(compact[1])
            and len(DEGREE.findall(compact[2])) == 1
        ):
            dates = YEAR_RANGE.search(compact[2])
            qualification = (
                compact[2][:dates.start()] if dates else compact[2]
            )
            cells = [
                compact[1].strip(),
                qualification.strip(" ,()"),
            ]
            if dates:
                cells.append(dates[0])
        else:
            cells = [
                part.strip()
                for row in rows
                for part in re.split(r"[|\t]", row)
                if part.strip()
            ]
        degree_index = next((i for i, cell in enumerate(cells) if DEGREE.search(cell)), None)
        if degree_index is None or len(cells) < 2 or sum(bool(DEGREE.search(cell)) for cell in cells) > 1:
            return None
        if re.search(r"\b\d{4}\b", " ".join(cells)) and not YEAR_RANGE.search(" ".join(cells)):
            return None
        institution_index = 1 if degree_index == 0 else 0
        if YEAR_RANGE.search(cells[institution_index]) or DEGREE.search(cells[institution_index]):
            return None
        result["institution"] = cells[institution_index]
        result["qualification"] = YEAR_RANGE.sub("", cells[degree_index]).strip(" ,()")
        remaining = [cell for i, cell in enumerate(cells) if i not in (degree_index, institution_index)]
        result["discipline"] = next((cell for cell in remaining if not YEAR_RANGE.search(cell)), "")
        result["startYear"], result["endYear"] = _years(" ".join(cells))
    if result["startYear"] is not None and result["endYear"] is not None and result["endYear"] < result["startYear"]:
        return None
    return result


def _course(rows, fields):
    if fields:
        return {"name": fields.get("name", ""), "code": fields.get("code") or None,
                "description": fields.get("description", "\n".join(rows))}
    cells = [part.strip() for part in re.split(r"[|\t]", rows[0])]
    if len(cells) >= 2 and re.fullmatch(r"[A-Z]{2,8}\s?\d{3,5}", cells[0]):
        return {"name": cells[1], "code": cells[0], "description": "\n".join(rows)}
    match = COURSE.match(rows[0])
    if match:
        return {"name": match[2], "code": match[1], "description": "\n".join(rows)}
    return None


def _experience(rows, fields):
    if fields:
        return {"title": fields.get("title", ""), "organisation": fields.get("organisation", ""),
                "description": fields.get("description", "\n".join(rows))}
    cells = [part.strip() for part in re.split(r"[|\t]", rows[0])]
    if len(cells) >= 2:
        return {"title": cells[0], "organisation": cells[1], "description": "\n".join(rows)}
    return None


def _output(rows, fields):
    if not fields:
        cells = [part.strip() for part in re.split(r"[|\t]", rows[0])]
        if len(cells) == 1:
            cells = [part.strip() for part in rows[0].split(":", 1)]
        if len(cells) < 2 or cells[0].upper() not in ("PUBLICATION", "PROJECT", "OTHER"):
            return None
        fields = {"type": cells[0], "title": cells[1],
                  "url": cells[2] if len(cells) > 2 and cells[2] else None}
    return {"title": fields.get("title", ""), "type": fields.get("type", "OTHER").upper(),
            "url": fields.get("url") or None, "description": fields.get("description", "\n".join(rows))}


PARSERS = {"education": _education, "courses": _course,
           "researchExperience": _experience, "researchOutputs": _output}

def _cv_lines(section, lines):
    values = [value for value, _ in lines if value]

    if section == "courses" and values:
        source = " ".join(values)
        labelled = any(
            re.split(r"[:\t]", value, maxsplit=1)[0]
            .strip().casefold() in KEYS
            for value in values
        )

        if (
            not labelled
            and not any(
                COURSE.match(value) or "|" in value or "\t" in value
                for value in values
            )
            and re.search(r"[,;、，；]", source)
            and not re.search(r"[:：]", source)
        ):
            names = [
                name.strip()
                for name in re.split(r"[,;、，；]", source)
                if name.strip()
            ]

            if names and all(len(name) <= 200 for name in names):
                converted = []

                for name in names:
                    converted.extend([
                        ("Name: " + name, source),
                        ("Description: " + source[:5000], source),
                        ("", ""),
                    ])

                issues = [
                    "Review course boundaries split from the source list."
                ]
                if len(source) > 5000:
                    issues.append(
                        "Course source description was shortened to "
                        "5000 characters; consult the original file."
                    )

                return converted, issues

    if section != "researchOutputs":
        return lines, []

    date = r"\d{4}(?:[./]\d{1,2})?"
    marker = re.compile(
        rf"^(?:team\s+)?project\s*\|\s*{date}\s*[-–—]\s*"
        rf"(?:{date}|present|current)"
        rf"(?:\s*\(expected\))?$",
        re.I,
    )

    # Retain gaps so _records can distinguish layout spacing from a new output.
    rows = list(lines)
    converted, issues = [], []
    index = 0

    def project_date_index(title_index):
        if not rows[title_index][0]:
            return None
        date_index = title_index + 1
        while date_index < len(rows) and not rows[date_index][0]:
            date_index += 1
        if date_index < len(rows) and marker.fullmatch(rows[date_index][0]):
            return date_index
        return None

    while index < len(rows):
        date_index = project_date_index(index)
        if date_index is None:
            converted.append(rows[index])
            index += 1
            continue

        title = rows[index][0]
        end = date_index + 1

        while end < len(rows):
            if project_date_index(end) is not None:
                break

            key = (
                re.split(r"[:\t]", rows[end][0], maxsplit=1)[0]
                .strip().casefold()
            )
            if key in ("title", "type") or re.match(
                r"^(PUBLICATION|PROJECT|OTHER)\s*[:|\t]",
                rows[end][0],
                re.I,
            ):
                break

            end += 1

        source = " ".join(value for value, _ in rows[index:end] if value)
        converted.extend([
            ("", ""),
            ("Title: " + title, title),
            ("Type: PROJECT", rows[date_index][0]),
            ("Description: " + source[:5000], source),
            ("", ""),
        ])

        if len(source) > 5000:
            issues.append(
                "Project description was shortened to "
                "5000 characters; consult the original file."
            )

        issues.append(
            "Review the project record against the source "
            "title, dates and description."
        )
        index = end

    return converted, issues

def _structured(section, lines):
    lines, layout_issues = _cv_lines(section, lines)
    found, issues, seen = [], list(layout_issues), set()
    for rows in _records(section, lines):
        # Skip transcript column labels, while retaining the actual course rows.
        if section == "courses" and re.match(r"^(course )?code[\t|]", rows[0], re.I):
            continue
        fields, unknown = _labelled(rows)
        item = PARSERS[section](rows, fields)
        source = "\n".join(rows)
        if item is not None:
            item["id"] = "doc_" + hashlib.sha256((section + source).encode()).hexdigest()[:24]
        if item is None or not validator(SCHEMAS[section]).is_valid(item):
            issues.append(f"Could not reliably parse: {source[:100]}")
            continue
        if item["id"] in seen:
            continue
        seen.add(item["id"])
        if len(found) >= 100:
            issues.append("More than 100 records; remaining records need manual review.")
            continue
        found.append(item)
        if fields and unknown:
            issues.append(f"Additional text needs review: {'; '.join(unknown)[:100]}")
        unused = [key for key in fields if key not in item]
        if unused:
            issues.append("Additional details need review: " + ", ".join(unused))
        if section == "education" and re.search(
            r"\bexpected\b", source, re.I
        ):
            issues.append(
                "The source gives an expected date; "
                "qualification completion has not been verified."
            )
        if section == "education" and not fields:
            cells = [part for row in rows for part in re.split(r"[|\t]", row) if part.strip()]
            if len(cells) > 4:
                issues.append("Additional education details need manual review in the original file.")
        missing = [key for key, value in item.items() if key != "id" and value in (None, "")]
        if missing:
            issues.append("Missing details: " + ", ".join(missing))
        if section == "researchOutputs" and fields and "type" not in fields:
            issues.append("Output type is unknown; review the suggested OTHER classification.")
    return found, issues


def build_extraction_result(document_id, text, tags):
    result = new_extraction_result(document_id)
    # One owner-only free-text description also retains content outside known headings.
    description = "\n".join(" ".join(line.split()) for line in text.splitlines() if line.strip())
    if description:
        result["suggestedSections"]["resumeDescription"] = description[:20000]
        if len(description) > 20000:
            result["uncertainFields"].append({"field": "resumeDescription", "status": "UNKNOWN",
                                               "reason": "Resume description was shortened to 20000 characters; consult the original file."})
    sections = _sections(text)
    academic, academic_issues = extract_academic_records(text, OTHER_HEADINGS | {
        alias for section, aliases in HEADINGS.items() if section not in ("education", "courses")
        for alias in aliases})
    for section, lines in sections.items():
        if section == "skills":
            items, issues = free_skill_suggestions(lines)
        elif section == "researchInterests":
            items, issues = _tags(lines, tags, "INTEREST")
        else:
            items, issues = _structured(section, lines)
        if section in academic:
            # Transcript rows need their result columns separated from course names.
            # Prefer those records over the same rows parsed as generic CV text.
            records = academic[section]

            def identity(item):
                if section == "courses" and item.get("code"):
                    return _fold(item["code"]).replace(" ", "")
                return (_fold(item.get("institution", "")), _fold(item.get("qualification", "")))

            existing = {identity(item) for item in records}
            # Transcript metadata such as "Name: ..." is not a labelled course.
            if section == "courses":
                items = [item for item in items if re.fullmatch(r"[A-Z]{2,8}\s?\d{3,5}", item.get("code") or "")]
                issues = []
            items = records + [item for item in items if identity(item) not in existing]
            if len(items) > 100:
                issues.append("More than 100 records; remaining records need manual review.")
                items = items[:100]
        issues.extend(academic_issues.get(section, []))
        if items:
            result["suggestedSections"][section] = items
        if issues or not items:
            reasons = list(dict.fromkeys(issues))
            reason = "; ".join(reasons[:5]) if reasons else "No reliable information was recognised for this section."
            if len(reasons) > 5:
                reason += "; More items need manual review."
            result["uncertainFields"].append({
                "field": section, "status": "UNKNOWN" if items else "NOT_RECOGNISED", "reason": reason,
            })
    interest_text, personal, issues = _interest_details(
        sections["researchInterests"], tags, len(result["suggestedSections"].get("researchInterests", [])))
    if interest_text:
        result["suggestedSections"]["researchInterestText"] = interest_text
    if personal:
        result["suggestedSections"]["customInterestTags"] = personal
    if issues:
        result["uncertainFields"].append({"field": "researchInterestText", "status": "UNKNOWN",
                                           "reason": "; ".join(dict.fromkeys(issues))})
    if not text.strip():
        result["warnings"].append("No readable text was found. Enter information manually.")
    return result
