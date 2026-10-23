"""Academic Statement layouts reported by a user, with synthetic student data."""

import pytest

from backend.src.features.documents.suggestions import build_extraction_result
from backend.src.shared.validation import validator
from backend.tests.conftest import headers
from backend.tests.test_us09_extraction import TAGS, text_docx, text_pdf, upload, process


STATEMENT = """Academic Statement
The University of New South Wales Name: Example Student
Student ID: 1234567
Academic Career 1 of 2: Undergraduate
Print Date: 23/10/2026
Beginning of Undergraduate Record
Term 1 2024
Program: 3778 Computer Science
Plan: COMPA13778 Computer Science Major
Session: Teaching Period One
Course Title Attempted Passed Mark Grade
COMP 1511 Programming Fundamentals 6.00 6.00 72 CR
MATH 1141 Higher Mathematics 1A 6.00 6.00 73 CR
Term WAM: 72.500 Term Totals 12.00 12.00
Good Standing
Term 2 2025
Program: 3778 Computer Science
Plan: COMPA13778 Computer Science Major
Academic Statement
The University of New South Wales Name: Example Student
Student ID: 1234567
Session: Teaching Period Two
Course Title Attempted Passed Mark Grade
COMP 3121 Algorithm Design and Analysis 6.00 0.00 50 UF
PHYS 1110 Everyday Physics 6.00 6.00 SY
Term WAM: 52.000 Term Totals 12.00 6.00
Academic Risk Level 1
Term 2 2026
Program: 3778 Computer Science
Plan: COMPA13778 Computer Science Major
Course Title Attempted Passed Mark Grade
COMP 3121 Algorithm Design and Analysis 6.00 6.00 71 CR
Good Standing
Term 3 2026
Program: 3778 Computer Science
Plan: COMPA13778 Computer Science Major
Course Title Attempted Passed Mark Grade
COMP 3900 Computer Science Project 6.00
COMP 9444 Neural Networks, Deep Learning 6.00
Term Totals 12.00 0.00
3778 Computer Science Totals
WAM: 73.136 Units: 156.00 132.00
Continuing to Postgraduate Record...
Academic Statement
The University of New South Wales Name: Example Student
Student ID: 1234567
...Continuing from Undergraduate Record
Academic Career 2 of 2: Postgraduate
Print Date: 23/10/2026
End of Academic Statement
"""


def extract(source=STATEMENT):
    result = build_extraction_result("doc_statement", source, TAGS)
    validator("Extraction").validate(result)
    return result


def test_statement_extracts_one_actual_programme_and_clean_course_titles():
    result = extract()
    sections = result["suggestedSections"]
    assert set(sections) == {"education", "courses", "resumeDescription"}
    education, = sections["education"]
    assert education["institution"] == "The University of New South Wales"
    assert education["qualification"] == "Computer Science"
    assert education["discipline"] == "Computer Science Major"
    assert education["startYear"] == 2024
    assert education["endYear"] is None
    assert "Example Student" not in str(sections["education"])
    courses = {item["code"]: item for item in sections["courses"]}
    assert len(courses) == 6
    assert courses["COMP1511"]["name"] == "Programming Fundamentals"
    assert courses["MATH1141"]["name"] == "Higher Mathematics 1A"
    assert courses["PHYS1110"]["name"] == "Everyday Physics"
    assert courses["COMP9444"]["name"] == "Neural Networks, Deep Learning"
    assert courses["COMP3900"]["name"] == "Computer Science Project"
    assert "6.00 6.00 72 CR" in courses["COMP1511"]["description"]
    assert "Term 3 2026" in courses["COMP3900"]["description"]
    assert any(item["field"] == "education" and "first recorded term" in item["reason"]
               for item in result["uncertainFields"])
    assert not any(item["field"] in ("education", "courses") and item["status"] == "NOT_RECOGNISED"
                   for item in result["uncertainFields"])
    assert result == extract()


def test_repeated_courses_keep_both_attempts_and_repeated_headers_do_not_create_records():
    sections = extract()["suggestedSections"]
    course, = [item for item in sections["courses"] if item["code"] == "COMP3121"]
    assert "Term 2 2025\nCOMP 3121 Algorithm Design and Analysis 6.00 0.00 50 UF" in course["description"]
    assert "Term 2 2026\nCOMP 3121 Algorithm Design and Analysis 6.00 6.00 71 CR" in course["description"]
    assert "WAM" not in course["description"]
    assert "Example Student" not in str(sections["courses"])
    assert len(sections["education"]) == 1  # Postgraduate header has no actual programme.


def test_academic_transcript_heading_does_not_turn_student_metadata_into_a_course():
    result = extract("""Academic Transcript
University of Example
Name: Example Student
Code: 1234567
Program: 3778 Computer Science
Course Title Attempted Passed Mark Grade
COMP 1511 Programming Fundamentals 6.00 6.00 85 HD
""")
    course, = result["suggestedSections"]["courses"]
    assert course["name"] == "Programming Fundamentals"
    assert course["code"] == "COMP1511"
    assert "Example Student" not in str(result["suggestedSections"]["courses"])


def test_university_in_a_programme_or_course_title_is_not_an_institution_header():
    result = extract("""Academic Statement
University of Example
Term 1 2026
Program: 1000 University Studies
Plan: University Policy
HIST 1000 The University in Society 6.00 6.00 80 DN
""")
    education, = result["suggestedSections"]["education"]
    assert education["institution"] == "University of Example"
    assert education["qualification"] == "University Studies"
    assert education["discipline"] == "University Policy"
    course, = result["suggestedSections"]["courses"]
    assert course["name"] == "The University in Society"


@pytest.mark.parametrize("format", ["pdf", "docx"])
@pytest.mark.parametrize("kind", ["CV", "TRANSCRIPT"])
def test_real_statement_upload_worker_review_apply_and_reload(app, signed, tmp_path, format, kind):
    client, csrf = signed
    app.config["DOCUMENT_STORAGE_DIR"] = str(tmp_path / "documents")
    before = client.get("/api/v1/me/profile").json
    content = text_pdf(STATEMENT) if format == "pdf" else text_docx(STATEMENT)
    document_id = upload(client, csrf, content, "academic-statement." + format, kind)
    process(app)
    response = client.get(f"/api/v1/me/documents/{document_id}/extraction")
    assert response.status_code == 200, response.json
    validator("Extraction").validate(response.json)
    sections = response.json["suggestedSections"]
    assert len(sections["education"]) == 1
    assert len(sections["courses"]) == 6
    assert client.get("/api/v1/me/profile").json == before
    accepted = {key: sections[key] for key in ("education", "courses")}
    applied = client.post(f"/api/v1/me/documents/{document_id}/apply", headers=headers(csrf),
                          json={"expectedProfileRevision": before["revision"], "sections": accepted})
    assert applied.status_code == 200, applied.json
    validator("Profile").validate(applied.json)
    reloaded = client.get("/api/v1/me/profile").json
    assert reloaded == applied.json
    assert all(reloaded["content"][key] == value for key, value in accepted.items())
    assert reloaded["content"]["resumeDescription"] == ""
    assert reloaded["confirmation"]["status"] == "UNCONFIRMED"


@pytest.mark.parametrize("rows,expected", [
    ("COMP 1511 Programming\nFundamentals 6.00 6.00 85 HD", "Programming Fundamentals"),
    ("COMP 1511\nProgramming Fundamentals\n6.00 6.00 85 HD", "Programming Fundamentals"),
    ("COMP1511\tProgramming Fundamentals\t6.00\t6.00\t85\tHD", "Programming Fundamentals"),
    ("COMP1511 Programming Fundamentals", "Programming Fundamentals"),
])
def test_table_rows_wrapped_titles_and_result_columns(rows, expected):
    result = extract("Academic Statement\nCourse Title Attempted Passed Mark Grade\n" + rows)
    course, = result["suggestedSections"]["courses"]
    assert course["code"] == "COMP1511"
    assert course["name"] == expected


def test_transcript_does_not_promote_course_topics_to_claims_or_parse_unrelated_sections():
    result = extract(STATEMENT + "\nWork experience\nCOMP 9999 Future Plans 6.00\nPython\n"
                     "Research interests\nMachine learning\n")
    sections = result["suggestedSections"]
    assert "skills" not in sections
    assert "researchExperience" not in sections
    assert "researchOutputs" not in sections
    assert sections["researchInterests"] == ["interest_ml"]
    assert "COMP9999" not in {item["code"] for item in sections["courses"]}
    assert "courses" not in extract("Work experience\nCOMP 1511 Programming Fundamentals 6.00")["suggestedSections"]


def test_multiple_programmes_remain_distinct_and_header_only_careers_are_ignored():
    result = extract("""Academic Statement
University of Example
Academic Career 1 of 2: Undergraduate
Term 1 2020
Program: 1000 Bachelor of Science
Plan: Physics Major
PHYS 1001 Mechanics 6.00 6.00 70 CR
Academic Career 2 of 2: Postgraduate
Term 1 2026
Program: 9000 Master of Research
Plan: Computer Science
COMP 9001 Research Methods 6.00
""")
    education = result["suggestedSections"]["education"]
    assert [(item["qualification"], item["startYear"]) for item in education] == [
        ("Bachelor of Science", 2020), ("Master of Research", 2026)]
    assert all(item["endYear"] is None for item in education)


def test_transcript_limits_are_reported_and_missing_institution_is_not_invented():
    result = extract("Academic Statement\nProgram: 3778 Computer Science\n" + "\n".join(
        f"COMP {1000 + i} Subject {i} 6.00 6.00 80 DN" for i in range(101)))
    assert "education" not in result["suggestedSections"]
    assert len(result["suggestedSections"]["courses"]) == 100
    assert any(item["field"] == "courses" and "100" in item["reason"] for item in result["uncertainFields"])
    assert any(item["field"] == "education" and "institution" in item["reason"] for item in result["uncertainFields"])
