"""Representative files and conservative extraction boundaries, not fixture-only matches."""

from io import BytesIO

import pytest
from docx import Document as DocxDocument
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject

from backend.src.features.documents.suggestions import build_extraction_result
from backend.src.shared.validation import validator
from backend.tests.conftest import headers


CV_TEXT = """Education
UNSW | Bachelor of Science | Computer Science | 2022-2025
Courses
COMP1511 - Programming Fundamentals
COMP2521 - Data Structures
Research experience
Research Assistant | UNSW | Evaluated graph algorithms.
Technical skills
Python, SQL
Research interests
Machine learning
Research outputs
PROJECT | Graph benchmark | https://example.test/graph
"""
TAGS = [
    {"id": "skill_python", "label": "Python", "kind": "SKILL"},
    {"id": "skill_sql", "label": "SQL", "kind": "SKILL"},
    {"id": "interest_ml", "label": "Machine learning", "kind": "INTEREST"},
]
SECTIONS = {"education", "courses", "researchExperience", "skills", "researchInterests", "researchOutputs", "researchInterestText", "resumeDescription"}


def text_pdf(text):
    """A real PDF with a text layer; no external fixture generator is required."""
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject({NameObject("/Type"): NameObject("/Font"),
                             NameObject("/Subtype"): NameObject("/Type1"),
                             NameObject("/BaseFont"): NameObject("/Helvetica")})
    page[NameObject("/Resources")] = DictionaryObject({
        NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})})
    commands = ["BT /F1 10 Tf 40 750 Td 14 TL"]
    for line in text.splitlines():
        escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        commands.append(f"({escaped}) Tj T*")
    commands.append("ET")
    stream = DecodedStreamObject()
    stream.set_data("\n".join(commands).encode("latin-1"))
    page[NameObject("/Contents")] = writer._add_object(stream)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def text_docx(text):
    document = DocxDocument()
    for line in text.splitlines():
        document.add_paragraph(line)
    output = BytesIO()
    document.save(output)
    return output.getvalue()


def upload(client, csrf, content, filename, kind="CV"):
    response = client.post("/api/v1/me/documents", headers=headers(csrf),
                           data={"kind": kind, "file": (BytesIO(content), filename)})
    assert response.status_code == 202, response.json
    return response.json["id"]


def process(app):
    result = app.test_cli_runner().invoke(args=["process-documents", "--once"])
    assert result.exit_code == 0, result.output


@pytest.mark.parametrize("format", ["pdf", "docx"])
def test_real_cv_extracts_and_imports_all_six_sections(app, signed, tmp_path, format):
    client, csrf = signed
    app.config["DOCUMENT_STORAGE_DIR"] = str(tmp_path / "documents")
    before = client.get("/api/v1/me/profile").json
    file = text_pdf(CV_TEXT) if format == "pdf" else text_docx(CV_TEXT)
    document_id = upload(client, csrf, file, "cv." + format)
    process(app)
    extraction = client.get(f"/api/v1/me/documents/{document_id}/extraction").json
    validator("Extraction").validate(extraction)
    sections = extraction["suggestedSections"]
    assert set(sections) == SECTIONS
    assert len(sections["courses"]) == 2
    assert sections["education"][0]["startYear"] == 2022
    assert sections["education"][0]["endYear"] == 2025
    assert sections["researchExperience"][0]["organisation"] == "UNSW"
    assert sections["researchOutputs"][0]["type"] == "PROJECT"
    assert extraction["uncertainFields"] == []
    assert client.get("/api/v1/me/profile").json == before
    response = client.post(f"/api/v1/me/documents/{document_id}/apply",
                           json={"expectedProfileRevision": before["revision"], "sections": sections},
                           headers=headers(csrf))
    assert response.status_code == 200, response.json
    imported = response.json
    for field in SECTIONS:
        assert imported["content"][field] == sections[field]
        assert {"field": field, "sourceType": "USER_REVIEWED_DOCUMENT",
                "documentId": document_id} in imported["origins"]
    assert imported["confirmation"]["status"] == "UNCONFIRMED"
    assert imported["revision"] == before["revision"] + 1


def test_real_word_tables_and_transcript_course_rows(app, signed, tmp_path):
    client, csrf = signed
    app.config["DOCUMENT_STORAGE_DIR"] = str(tmp_path / "documents")
    document = DocxDocument()
    table = document.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text = "Skills"
    table.rows[0].cells[1].text = "Python, COBOL"
    document.add_paragraph("Academic transcript")
    table = document.add_table(rows=1, cols=3)
    for cell, value in zip(table.rows[0].cells, ("Course Code", "Course Name", "Mark")):
        cell.text = value
    for values in (("COMP1511", "Programming Fundamentals", "85"),
                   ("COMP2521", "Data Structures", "90")):
        for cell, value in zip(table.add_row().cells, values):
            cell.text = value
    content = BytesIO()
    document.save(content)
    document_id = upload(client, csrf, content.getvalue(), "transcript.docx", "TRANSCRIPT")
    process(app)
    result = client.get(f"/api/v1/me/documents/{document_id}/extraction").json
    validator("Extraction").validate(result)
    assert [item["code"] for item in result["suggestedSections"]["courses"]] == ["COMP1511", "COMP2521"]
    assert [item["title"] for item in result["suggestedSections"]["skills"]] == ["Python", "COBOL"]


def test_labelled_blocks_and_multiple_entries_preserve_missing_details():
    source = """Education:
Institution: UNSW
Qualification: Master of IT
Start year: 2024
End year: present

Institution: University of Sydney
Degree: Bachelor of Science
Major: Physics
Start year: 2019
End year: 2022
Courses:
Name: Research Ethics
Research experience:
Title: Research Assistant
Description: Analysed survey data.
Research outputs:
Title: Survey report
Description: Reported the findings.
"""
    result = build_extraction_result("doc_cv", source, TAGS)
    validator("Extraction").validate(result)
    sections = result["suggestedSections"]
    assert len(sections["education"]) == 2
    assert sections["education"][0]["endYear"] is None
    assert sections["education"][0]["discipline"] == ""
    assert sections["courses"][0]["code"] is None
    assert sections["researchExperience"][0]["organisation"] == ""
    assert sections["researchOutputs"][0]["type"] == "OTHER"
    assert all(item["status"] == "UNKNOWN" for item in result["uncertainFields"]
               if item["field"] in sections)
    assert result == build_extraction_result("doc_cv", source, TAGS)


@pytest.mark.parametrize("text,field,known,unknown", [
    ("Skills: Python, COBOL", "skills", "skill_python", "COBOL"),
    ("Interests: Machine learning; Astrobiology", "researchInterests", "interest_ml", "Astrobiology"),
])
def test_partial_tags_keep_known_items_and_warn_about_unknown_items(text, field, known, unknown):
    result = build_extraction_result("doc_partial", text, TAGS)
    items = result["suggestedSections"][field]
    if field == "skills":
        assert [item["title"] for item in items] == ["Python", "COBOL"]
    else:
        assert items[0] == known
        assert any(item["field"] == field and item["status"] == "UNKNOWN" and unknown in item["reason"]
                   for item in result["uncertainFields"])


@pytest.mark.parametrize("text", [
    "", "Unstructured text with Python mentioned in passing.",
    "Education\nBachelor of Science\n2022-2025",
    "Education\nUNSW | Bachelor of Science | Computing | 2025-2022",
    "Education\nUNSW | Bachelor of Science | Computing | 1800-2022",
    "Research outputs\nPUBLICATION | Paper | javascript:alert(1)",
    "Skills: No Python, Python",
])
def test_unreliable_text_is_not_invented_or_promoted(text):
    result = build_extraction_result("doc_unknown", text, TAGS)
    validator("Extraction").validate(result)
    assert set(result["suggestedSections"]) <= {"resumeDescription"}
    assert len(result["uncertainFields"]) == 6


def test_bullets_stop_at_unrelated_headings_and_deduplicate():
    result = build_extraction_result("doc_bullets", "Technical skills\n- Python\n• Python\nWork experience\nSQL", TAGS)
    assert [item["title"] for item in result["suggestedSections"]["skills"]] == ["Python"]


def test_truncated_tags_and_evidence_are_flagged():
    tags = [{"id": f"skill_{i}", "label": f"Skill {i}", "kind": "SKILL"} for i in range(101)]
    result = build_extraction_result("doc_limit", "Skills: " + ", ".join(tag["label"] for tag in tags), tags)
    assert len(result["suggestedSections"]["skills"]) == 100
    assert any("100" in item["reason"] for item in result["uncertainFields"] if item["field"] == "skills")
    result = build_extraction_result("doc_long", "Skills: Python," + "x" * 2100, TAGS)
    assert len(result["suggestedSections"]["skills"][0]["evidenceText"]) == 2000
    assert any("shortened" in item["reason"] for item in result["uncertainFields"] if item["field"] == "skills")


def test_repeated_label_and_word_label_cells_start_complete_records():
    result = build_extraction_result("doc_labels", """Education
Institution\tUNSW
Degree\tMaster of IT
University: University of Sydney
Qualification: Bachelor of Science
Courses
Name: Ethics | Research
Description: Discussed survey | interview methods.
Research outputs
PROJECT | Graphs: a benchmark | https://example.test/graphs
""", TAGS)
    validator("Extraction").validate(result)
    assert [item["institution"] for item in result["suggestedSections"]["education"]] == ["UNSW", "University of Sydney"]
    assert result["suggestedSections"]["courses"][0]["description"] == "Discussed survey | interview methods."
    assert result["suggestedSections"]["researchOutputs"][0]["title"] == "Graphs: a benchmark"


def test_oversized_year_and_mixed_records_do_not_fail_reliable_sections():
    result = build_extraction_result("doc_mixed", "Education\nInstitution: UNSW\nDegree: Bachelor of Science\n"
                                     + "Start year: " + "2" * 5000 + "\nSkills: Python", TAGS)
    validator("Extraction").validate(result)
    assert "education" not in result["suggestedSections"]
    assert result["suggestedSections"]["skills"][0]["title"] == "Python"


def test_structured_item_limit_is_reported_without_losing_first_records():
    result = build_extraction_result("doc_courses", "Courses\n" + "\n".join(
        f"COMP{i:04d} - Course {i}" for i in range(101)), TAGS)
    validator("Extraction").validate(result)
    assert len(result["suggestedSections"]["courses"]) == 100
    assert any(item["field"] == "courses" and item["status"] == "UNKNOWN" and "100" in item["reason"]
               for item in result["uncertainFields"])


@pytest.mark.parametrize("source", [
    "Education\nUNSW | Bachelor of Science | Computing | 2022-2025 | Awarded distinction",
    "Education\nInstitution: UNSW\nDegree: Bachelor of Science\nDescription: Awarded distinction",
])
def test_additional_education_details_are_explicitly_flagged(source):
    result = build_extraction_result("doc_extra", source, TAGS)
    validator("Extraction").validate(result)
    assert result["suggestedSections"]["education"][0]["institution"] == "UNSW"
    assert any(item["field"] == "education" and item["status"] == "UNKNOWN"
               and "Additional" in item["reason"] for item in result["uncertainFields"])


@pytest.mark.parametrize("format", ["pdf", "docx"])
def test_real_document_without_text_offers_manual_entry(app, signed, tmp_path, format):
    client, csrf = signed
    app.config["DOCUMENT_STORAGE_DIR"] = str(tmp_path / "documents")
    content = text_pdf("") if format == "pdf" else text_docx("")
    document_id = upload(client, csrf, content, "empty." + format)
    process(app)
    response = client.get(f"/api/v1/me/documents/{document_id}/extraction")
    assert response.status_code == 200, response.json
    assert response.json["suggestedSections"] == {}
    assert len(response.json["uncertainFields"]) == 6
    assert any("manually" in warning for warning in response.json["warnings"])
