"""Conservative, source-based suggestions; nothing here confirms a profile."""

import hashlib
import re
import unicodedata

from ...shared.validation import validator
from .academic import extract_academic_records
from .skill_suggestions import free_skill_suggestions

PROJECT_HEADINGS = (
    "projects", "project experience", "selected projects", "academic projects",
    "personal projects", "research projects", "course projects",
    "portfolio", "technical portfolio", "project portfolio", "capstone projects",
    "competitions", "hackathons",
    "项目经历", "项目经验", "个人项目", "课程项目", "研究项目", "竞赛经历",
)

HEADINGS = {
    "education": ("education", "academic qualifications", "qualifications", "教育背景", "教育经历"),
    "courses": ("courses", "coursework", "relevant coursework", "academic transcript", "transcript", "相关课程", "课程"),
    "researchExperience": ("research experience", "research experiences", "科研经历", "研究经历"),
    "skills": ("skills", "technical skills", "programming skills", "专业技能", "技能"),
    "researchInterests": ("research interests", "research interest", "interests", "研究兴趣", "研究方向"),
    "researchOutputs": ("research outputs", "publications", "selected publications","科研成果", "研究成果",) + PROJECT_HEADINGS,
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

OTHER_HEADINGS |= {
    "additional information", "availability",
    "intern experience", "internship experience", "work history",
    "employment history", "leadership", "volunteering", "volunteer experience",
    "leadership and volunteering", "实习经历",
}

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

def _normalise_cv_headings(text):
    """Recover standalone headings split into individual letters by PDF export."""
    known = {name for names in HEADINGS.values() for name in names} | OTHER_HEADINGS
    by_letters = {re.sub(r"\s+", "", name.casefold()): name for name in known}
    output, extra_headings = [], set()

    for raw in text.splitlines():
        value = raw.strip().rstrip(":：").strip()
        value = value.replace("\u00a0", " ").replace("\u202f", " ")
        parts = value.split()
        if len(parts) < 4 or not all(re.fullmatch(r"[A-Za-z&/]", part) for part in parts):
            output.append(raw)
            continue

        heading = by_letters.get("".join(parts).casefold())
        if heading is None:
            groups = re.split(r" {2,}|\t+", value)
            heading = " ".join("".join(group.split()) for group in groups).upper()
            if not (
                _looks_like_project_heading(heading)
                or re.search(
                    r"\b(?:EDUCATION|EXPERIENCE|SKILLS|PUBLICATIONS?|CERTIFICATIONS?|"
                    r"AWARDS|VOLUNTEERING|LEADERSHIP|ACTIVITIES|INTERESTS|COURSES?|"
                    r"BACKGROUND|HISTORY|SUMMARY)$",
                    heading,
                )
            ):
                output.append(raw)
                continue
            extra_headings.add(heading.casefold())

        output.append(heading.upper() if value.isupper() else heading)

    return "\n".join(output), extra_headings

def _looks_like_project_heading(line):
    """Recognise short uppercase headings with common project-section words."""
    title = line.rstrip(":：").strip()
    return (
        title.isupper()
        and len(title.split()) <= 8
        and bool(re.fullmatch(r"[A-Z][A-Z &/–-]*", title))
        and bool(re.search(
            r"\b(?:PROJECTS?|COMPETITIONS?|HACKATHONS?|CAPSTONES?|PORTFOLIO|BUILDS)$",
            title,
        ))
    )

def _sections(text, extra_headings=()):
    aliases = {
        alias: section
        for section, names in HEADINGS.items()
        for alias in names
    }
    sections = {section: [] for section in HEADINGS}
    active = active_heading = None
    rows = text.splitlines()

    for index, raw in enumerate(rows):
        raw = re.sub(r"^\s*[\ue000-\uf8ff]\s+", "• ", raw)
        line = _clean(raw)
        heading, remainder = _heading(line, set(aliases) | OTHER_HEADINGS)

        if (
            heading is None
            and active_heading not in PROJECT_HEADINGS
            and raw.strip() == line
            and _looks_like_project_heading(line)
        ):
            heading = "projects"

        # These words can be section headings or ordinary skill names.
        if active == "skills" and heading in {"leadership", "volunteering"}:
            after_blank = index > 0 and not rows[index - 1].strip()
            standalone = raw.strip() == line and not remainder
            if not (
                standalone
                and (line.endswith((":", "：")) or (after_blank and line.isupper()))
            ):
                heading, remainder = None, ""

        # A bare portfolio label can be the name of an entry inside Projects.
        if (
            active_heading in PROJECT_HEADINGS
            and heading in {"portfolio", "technical portfolio", "project portfolio"}
            and not remainder
            and not line.endswith((":", "："))
        ):
            heading = None

        if active == "skills" and heading == "languages" and remainder:
            sections[active].append((line, line))
        elif heading in aliases:
            active = aliases[heading]
            active_heading = heading
            if active == "researchOutputs":
                sections[active].append(("", heading))
            if remainder:
                sections[active].append((remainder, line))
        elif (
            heading in OTHER_HEADINGS
            or line.casefold().rstrip(":：").strip() in extra_headings
        ):
            active = active_heading = None
        elif active:
            source = raw if active == "researchOutputs" else line
            sections[active].append((line, source))

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
    for index, (value, source) in enumerate(lines):
        if (
            not value and section == "researchOutputs" and block_keys
            and source not in HEADINGS["researchOutputs"]
        ):
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

    month = (
        r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|"
        r"Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|"
        r"Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?"
    )
    year = r"(?:19|20)\d{2}"
    date = (
        rf"(?:{month}\s+{year}|(?:0?[1-9]|1[0-2])[/.-]{year}|"
        rf"{year}(?:[./-](?:0?[1-9]|1[0-2])|年(?:\d{{1,2}}月)?)?)"
    )
    date_span = re.compile(
        rf"(?:{month}\s*[-–—]\s*{month}\s+{year}|"
        rf"{date}(?:\s*(?:[-–—~至]|\bto\b)\s*"
        rf"(?:{date}|present|current|ongoing|至今))?)(?:\s*\(expected\))?",
        re.I,
    )
    date_tail = re.compile(rf"(?<!\S)\(?{date_span.pattern}\)?$", re.I)
    separator = re.compile(r"\s*[|\t·]\s*| {2,}")
    role = re.compile(
        r"(?:(?:team|group|individual|personal|academic|research|course|capstone)\s+)?project"
        r"|(?:团队|个人|课程|研究)?项目",
        re.I,
    )
    metadata = re.compile(
        r"^(?:tech(?:nology)? stack|technologies|tools|stack|role|dates?|duration|"
        r"技术栈|技术|角色|时间)\s*[:：]",
        re.I,
    )
    bullet = re.compile(r"^\s*(?:[•●⚫▪◦]\s*|[-*]\s+|\d+[.)]\s+)")
    action = re.compile(
        r"^(?:built|developed|implemented|designed|created|tested|improved|"
        r"evaluated|led|worked|used|wrote|collaborated|maintained)\b"
        r"|^(?:负责|实现了|开发了|完成了)",
        re.I,
    )
    explicit = re.compile(
        r"^(?:title|type)\s*[:\t]|^(?:project|publication|other)\s*[:|\t]",
        re.I,
    )
    url_pattern = re.compile(
        r"https?://[^\s<>|]+|(?:[\w-]+\.)+[a-z]{2,}/[^\s<>|]+", re.I,
    )
    rows = list(lines)
    converted, issues = [], []

    def is_heading(index):
        value, source = rows[index]
        return not value and source in HEADINGS["researchOutputs"]

    def next_line(index):
        index += 1
        while index < len(rows) and not rows[index][0]:
            if is_heading(index):
                return None
            index += 1
        return index if index < len(rows) else None

    def link(value):
        value = re.sub(
            r"^(?:url|link|repo(?:sitory)?|github)\s*[:：]\s*", "",
            value, flags=re.I,
        ).rstrip(".,;，。；")
        if not url_pattern.fullmatch(value):
            return None
        scheme, mark, rest = value.partition("://")
        return scheme.lower() + mark + rest if mark else "https://" + value

    def has_date(cells):
        return any(
            date_span.fullmatch(metadata.sub("", cell).strip())
            for cell in cells
        )

    def title_like(value):
        return (
            0 < len(value) <= 300 and len(value.split()) <= 24
            and not action.match(value) and not explicit.match(value)
            and not metadata.match(value) and not role.fullmatch(value)
            and not link(value) and not date_span.fullmatch(value)
            and not re.match(r"^(?:description|url)\s*[:\t]", value, re.I)
            and not value.endswith((".", "!", "?", "。", "！", "？"))
        )

    def continues_previous_line(index):
        if index == 0 or not rows[index - 1][0]:
            return False

        previous, previous_raw = rows[index - 1]
        raw = rows[index][1]
        previous_indent = len(previous_raw) - len(previous_raw.lstrip())
        indent = len(raw) - len(raw.lstrip())
        unfinished = re.search(
            r"(?:[,/&]|\b(?:and|or|with|using|for|to|of))\s*$",
            previous,
            re.I,
        )
        return bool(
            unfinished or (bullet.match(previous_raw) and indent > previous_indent)
        )
    
    def project_start(index, in_projects):
        value, raw = rows[index]
        value = re.sub(r"^\d+[.)]\s+", "", value)
        cells = separator.split(value)

        if in_projects and not explicit.match(value) and not link(value):
            if len(cells) > 1 and title_like(cells[0]) and has_date(cells[1:]):
                return cells[0], index, True

            dated = date_tail.search(value)
            if dated:
                prefix = value[:dated.start()].rstrip(" |·–—-(")
                title = separator.split(prefix, maxsplit=1)[0].strip()
                if title_like(title):
                    return title, index, True

        if len(cells) != 1 or not title_like(value):
            return None

        after = next_line(index)
        if after is None:
            return None
        following, original = rows[after]
        following_cells = separator.split(following)
        dated = has_date(following_cells)

        if role.fullmatch(following_cells[0]) and has_date(following_cells[1:]):
            return value, after, True
        if in_projects and (
            dated or metadata.match(following)
            or (not bullet.match(raw)
                and not continues_previous_line(index)
                and (link(following) or bullet.match(original))
                )
        ):
            return value, after, dated
        return None

    index = 0
    in_projects = False
    allow_legacy = False
    while index < len(rows):
        if is_heading(index):
            heading = rows[index][1]
            in_projects = heading in PROJECT_HEADINGS
            allow_legacy = heading not in {"publications", "selected publications"}
            converted.append(rows[index])
            index += 1
            continue

        entry = project_start(index, in_projects) if allow_legacy else None
        if entry is None:
            converted.append(rows[index])
            index += 1
            continue

        title, cue_index, dated_title = entry
        end = cue_index + 1
        seen_description = bool(
            cue_index > index
            and (bullet.match(rows[cue_index][1]) or action.match(rows[cue_index][0]))
        )
        while end < len(rows):
            value, raw = rows[end]
            if is_heading(end) or explicit.match(value):
                break

            next_entry = project_start(end, in_projects)
            if next_entry and (next_entry[2] or seen_description or not dated_title):
                break

            if re.match(r"^url\s*[:\t]", value, re.I):
                after = next_line(end)
                if after is not None and explicit.match(rows[after][0]):
                    break

            if bullet.match(raw) or action.match(value):
                seen_description = True
            end += 1

        source = " ".join(value for value, _ in rows[index:end] if value)
        links = set()
        for offset, (value, raw) in enumerate(rows[index:end]):
            if offset and (bullet.match(raw) or action.match(value)):
                break
            links.update(url for cell in separator.split(value) if (url := link(cell)))

        converted.extend([
            ("", ""),
            ("Title: " + title, title),
            ("Type: PROJECT", title),
            ("Description: " + source[:5000], source),
        ])
        if len(links) == 1:
            url = links.pop()
            if validator("ResearchOutput").is_valid({
                "id": "candidate", "title": title, "type": "PROJECT",
                "description": "", "url": url,
            }):
                converted.append(("URL: " + url, url))
        converted.append(("", ""))

        if len(source) > 5000:
            issues.append("Project description was shortened to 5000 characters.")
        issues.append("Review the inferred project title and description against the source.")
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
    text, extra_headings = _normalise_cv_headings(text)
    sections = _sections(text, extra_headings)
    academic, academic_issues = extract_academic_records(
        text,
        OTHER_HEADINGS | extra_headings | {
            alias
            for section, aliases in HEADINGS.items()
            if section not in ("education", "courses")
            for alias in aliases
        },
    )
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
