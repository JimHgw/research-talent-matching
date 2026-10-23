"""Read academic records without treating subjects as skills or research claims."""

import hashlib
import re
import unicodedata

from ...shared.validation import validator


TRANSCRIPT = re.compile(r"^(?:(?:official|unofficial)\s+)?(?:academic statement|(?:academic\s+)?transcript(?: of records)?)\s*:?$", re.I)
TABLE = re.compile(r"^(?:course|subject)\s+(?:code\b|title\b|name\b)", re.I)
TERM = re.compile(r"^(?:(?:summer|winter)\s+term|term\s+\d+|semester\s+\d+|(?:fall|spring|summer|winter)(?:\s+semester)?)\s+(\d{4})\b", re.I)
CAREER = re.compile(r"^Academic Career(?:\s+\d+\s+of\s+\d+)?\s*:\s*(.+)$", re.I)
PROGRAM = re.compile(r"^program(?:me)?(?:\s+(?:name|title))?\s*:\s*(?:(\d{3,8})\s+)?(.+)$", re.I)
PLAN = re.compile(r"^(?:plan|major)\s*:\s*(?:[A-Z]{2,}\d{3,}\s+)?(.+)$", re.I)
COURSE = re.compile(r"^([A-Z]{2,8})\s*(\d{3,5})\b(?:\s*[-–—:]\s*|\s+)?(.*)$")
# A decimal credit value distinguishes the results columns from digits in titles.
RESULTS = re.compile(r"(?:^|\s)\d{1,3}\.\d{2}(?:\s+(?:\d{1,3}(?:\.\d+)?|[A-Z]{1,5}|[-–—]))*\s*$")
METADATA = re.compile(r"^(?:academic\b|the university\b|university\b|student\b|name\s*:|print date\s*:|beginning\b|continuing\b|\.{3}|end of\b|session\s*:|term (?:wam|totals)\b|wam\s*:|good standing\b|academic risk\b|\d+\s+.+\s+totals\b|page\s+\d+\b)", re.I)


def _line(value):
    return " ".join(unicodedata.normalize("NFKC", value).split()).strip()


def _id(section, value):
    return "doc_" + hashlib.sha256((section + value).encode()).hexdigest()[:24]


def _institution(value):
    # Repeated page headers often put the student's name on the same line.
    value = re.split(r"\b(?:name|student (?:id|number)|print date)\s*:", value, maxsplit=1, flags=re.I)[0].strip()
    labelled = re.match(r"^(?:institution|university)\s*:\s*(.+)$", value, re.I)
    if labelled:
        return labelled[1].strip()
    if ":" in value:
        return None
    if re.match(r"^(?:the\s+)?(?:university\b|.+\b(?:university|college|institute of technology)\b)", value, re.I):
        return value
    return None


def _boundary(value, stop_headings):
    heading = value.split(":", 1)[0].strip().casefold()
    return (heading in stop_headings or TRANSCRIPT.match(value) or TABLE.match(value)
            or TERM.match(value) or CAREER.match(value) or PROGRAM.match(value)
            or PLAN.match(value) or METADATA.match(value) or COURSE.match(value))


def _course(lines, index, stop_headings):
    match = COURSE.match(lines[index])
    code, name = match[1] + match[2], match[3].strip()
    source = [lines[index]]
    consumed = 1
    # PDF reading order may put the title and/or result columns on following lines.
    # Only join continuations when a results suffix makes the boundary explicit.
    if not RESULTS.search(name):
        pending = []
        for following in lines[index + 1:index + 4]:
            if not following or _boundary(following, stop_headings):
                break
            pending.append(following)
            combined = " ".join([name, *pending]).strip()
            if RESULTS.search(combined):
                name = combined
                source.extend(pending)
                consumed += len(pending)
                break
    title = RESULTS.sub("", name).strip(" |\t")
    if not title:
        return None, consumed
    return {"id": _id("academic-course", code), "code": code,
            "name": title, "description": "\n".join(source)}, consumed


def extract_academic_records(text, stop_headings):
    """Return only explicit programmes/course rows from transcript context.

    Upload kind is deliberately irrelevant: an Academic Statement uploaded as a CV
    still has academic-record content. A page mentioning another academic career
    without a programme does not create a second qualification.
    """
    lines = [_line(line) for line in text.splitlines()]
    sections, issues = {}, {"education": [], "courses": []}
    if not any(TRANSCRIPT.match(line) or TABLE.match(line) for line in lines):
        return sections, issues

    institution, career, term, year = "", "", "", None
    active, current = False, None
    programmes, courses = {}, {}
    index = 0
    while index < len(lines):
        value = lines[index]
        index += 1
        if TRANSCRIPT.match(value) or TABLE.match(value):
            active = True
            continue
        heading = re.split(r":", value, maxsplit=1)[0].casefold()
        if heading in stop_headings:
            active, current = False, None
        if not active or not value:
            continue
        match = CAREER.match(value)
        if match:
            if career.casefold() != match[1].casefold():
                current, term, year = None, "", None
            career = match[1]
            continue
        match = TERM.match(value)
        if match:
            term = value
            year = int(match[1]) if 1900 <= int(match[1]) <= 2200 else None
            continue
        match = PROGRAM.match(value)
        if match:
            if match[2].isdigit():
                current = None
                issues["education"].append("A programme code without its title needs manual review.")
                continue
            key = (institution.casefold(), career.casefold(), (match[1] or match[2]).casefold())
            if key not in programmes:
                programmes[key] = {"institution": institution, "qualification": match[2],
                                   "discipline": "", "years": set()}
            current = programmes[key]
            if year is not None:
                current["years"].add(year)
            continue
        match = PLAN.match(value)
        if match and current is not None:
            # Keep the explicitly named plan; do not derive a degree from a code.
            current["discipline"] = match[1]
            continue
        school = None if COURSE.match(value) else _institution(value)
        if school:
            if institution and school != institution:
                current, term, year = None, "", None
            institution = school
            continue
        if not COURSE.match(value):
            continue
        item, consumed = _course(lines, index - 1, stop_headings)
        index += consumed - 1
        if item is None or not validator("Course").is_valid(item):
            issues["courses"].append("A course row needs manual review in the original document.")
            continue
        if current is not None and year is not None:
            current["years"].add(year)
        if term:
            item["description"] = term + "\n" + item["description"]
        existing = courses.get(item["code"])
        if existing:
            # One profile course, with all attempts retained rather than an arbitrary grade.
            if item["description"] not in existing["attempts"]:
                existing["attempts"].append(item["description"])
            if existing["name"] != item["name"]:
                issues["courses"].append("A repeated course code has different titles; review its recorded attempts.")
        elif len(courses) < 100:
            courses[item["code"]] = {**item, "attempts": [item["description"]]}
        else:
            issues["courses"].append("More than 100 records; remaining records need manual review.")

    for code, item in courses.items():
        description = "\n\n".join(item.pop("attempts"))
        item["description"] = description[:5000]
        if len(description) > 5000:
            issues["courses"].append(f"Recorded attempts for {code} were shortened to 5000 characters; consult the original file.")
    if courses:
        sections["courses"] = list(courses.values())

    education = []
    for key, programme in programmes.items():
        years = programme.pop("years")
        item = {**programme, "id": _id("academic-education", "|".join(key)),
                "startYear": min(years) if years else None, "endYear": None}
        if not validator("Education").is_valid(item):
            issues["education"].append("Programme details are incomplete; review the institution and programme in the original file.")
            continue
        if len(education) >= 100:
            issues["education"].append("More than 100 records; remaining records need manual review.")
            break
        education.append(item)
    if education:
        sections["education"] = education
        issues["education"].append("Review the programme label as the qualification: no degree title or graduation year was inferred. The start year is the first recorded term, which may not be the enrolment year.")
    return sections, issues
