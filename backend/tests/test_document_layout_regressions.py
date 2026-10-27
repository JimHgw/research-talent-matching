from io import BytesIO

import pytest
from docx import Document as DocxDocument
from docx.oxml import OxmlElement
from lxml import etree

from backend.src.features.documents.suggestions import build_extraction_result
from backend.src.features.documents.text import extract_docx_text
from backend.src.shared.validation import validator
from backend.tests.conftest import headers
from backend.tests.test_us09_extraction import process, text_docx, upload


SOURCE = """Technical Skills
⚫ Languages: Python, JavaScript
⚫ Backend & Data: SQL, Flask
Work Experience       Example Organisation
Computer Science Intern
Projects
Survey benchmark
Team Project | 2024.08 – 2024.12
Built a survey prototype.
Data explorer
Team Project | 2025.05 – 2025.06
Built an exploration tool.
Additional information
Enjoys basketball.
Education:
Example University——Bachelor of Computer
Science
01.2024 – 12.2026 (Expected)
Relevant Coursework: Object-Oriented Design, Data Structures &
Algorithms
"""

PROJECT_SOURCE = """Projects
Data explorer
Team Project | 2024.08 - 2024.12
Built an exploration tool.
"""

PUBLICATIONS_SOURCE = """Research outputs
Title: Paper A
Type: PUBLICATION
Description: First paper.

URL: https://example.test/paper-b
Title: Paper B
Type: PUBLICATION
Description: Second paper.
"""


def hyphenated_skill_docx():
    document = DocxDocument()
    document.add_paragraph("Skills")
    run = document.add_paragraph().add_run("scikit")
    run._r.append(OxmlElement("w:noBreakHyphen"))
    run.add_text("learn")
    content = BytesIO()
    document.save(content)
    return content.getvalue()


def test_cv_layout_keeps_records_grounded_and_work_out_of_skills():
    result = build_extraction_result("doc_layout", SOURCE, [])
    validator("Extraction").validate(result)
    sections = result["suggestedSections"]

    assert [row["title"] for row in sections["skills"]] == [
        "Python", "JavaScript", "SQL", "Flask",
    ]

    education, = sections["education"]
    assert education["institution"] == "Example University"
    assert education["qualification"] == "Bachelor of Computer Science"
    assert (education["startYear"], education["endYear"]) == (2024, 2026)

    assert [row["name"] for row in sections["courses"]] == [
        "Object-Oriented Design", "Data Structures & Algorithms",
    ]
    assert all(row["code"] is None for row in sections["courses"])

    assert [row["title"] for row in sections["researchOutputs"]] == [
        "Survey benchmark", "Data explorer",
    ]
    assert all(
        row["type"] == "PROJECT"
        for row in sections["researchOutputs"]
    )
    assert "Enjoys basketball" not in str(sections["researchOutputs"])
    assert "researchExperience" not in sections

    assert any(
        item["field"] == "education"
        and "expected date" in item["reason"]
        for item in result["uncertainFields"]
    )
    assert result["reviewRequired"] is True


@pytest.mark.parametrize("heading", [
    "Work experience",
    "Work experience: Example Organisation",
    "Work experience       Example Organisation",
    "Work experience\tExample Organisation",
])
def test_work_heading_ends_skills_even_when_combined_with_content(heading):
    result = build_extraction_result(
        "doc_boundary",
        "Skills\nPython\n" + heading + "\nComputer Science Intern",
        [],
    )

    assert [
        row["title"]
        for row in result["suggestedSections"]["skills"]
    ] == ["Python"]
    assert "researchExperience" not in result["suggestedSections"]


def test_word_textbox_is_read_once_and_table_columns_are_preserved():
    document = DocxDocument()
    paragraph = document.add_paragraph()
    markup = (
        "{http://schemas.openxmlformats.org/"
        "markup-compatibility/2006}"
    )
    alternate = etree.Element(markup + "AlternateContent")

    for kind in ("Choice", "Fallback"):
        branch = etree.SubElement(alternate, markup + kind)
        box = OxmlElement("w:txbxContent")
        inner = OxmlElement("w:p")
        run = OxmlElement("w:r")
        text = OxmlElement("w:t")
        text.text = "Education: Example University"

        run.append(text)
        inner.append(run)
        box.append(inner)
        branch.append(box)

    paragraph._p.append(alternate)

    table = document.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "COMP1511"
    table.cell(0, 1).text = "Programming Fundamentals"

    content = BytesIO()
    document.save(content)
    content.seek(0)

    extracted = extract_docx_text(content)

    assert extracted.count("Education: Example University") == 1
    assert "COMP1511\tProgramming Fundamentals" in extracted


@pytest.mark.parametrize("following", [
    "Publication: Graph paper",
    "PUBLICATION | Graph paper",
    "PUBLICATION\tGraph paper",
])
@pytest.mark.parametrize("separator", ["", "\n"])
def test_project_preserves_following_publication(following, separator):
    result = build_extraction_result(
        "doc_outputs", PROJECT_SOURCE + separator + following, [],
    )
    validator("Extraction").validate(result)
    outputs = result["suggestedSections"]["researchOutputs"]
    assert [(row["title"], row["type"]) for row in outputs] == [
        ("Data explorer", "PROJECT"), ("Graph paper", "PUBLICATION"),
    ]
    assert "Graph paper" not in outputs[0]["description"]


def test_blank_lines_keep_publication_urls_with_their_record():
    result = build_extraction_result("doc_publications", PUBLICATIONS_SOURCE, [])
    validator("Extraction").validate(result)
    outputs = result["suggestedSections"]["researchOutputs"]
    assert [(row["title"], row["url"]) for row in outputs] == [
        ("Paper A", None), ("Paper B", "https://example.test/paper-b"),
    ]
    assert [row["description"] for row in outputs] == ["First paper.", "Second paper."]


def test_project_date_spacing_and_description_paragraphs_are_preserved():
    source = PROJECT_SOURCE.replace("Data explorer\n", "Data explorer\n\n")
    source += "\nEvaluated the results.\n\nSecond project\n\nProject | 2025 - current\nBuilt a tool."
    result = build_extraction_result("doc_projects", source, [])
    validator("Extraction").validate(result)
    outputs = result["suggestedSections"]["researchOutputs"]
    assert [row["title"] for row in outputs] == ["Data explorer", "Second project"]
    assert "Evaluated the results." in outputs[0]["description"]
    assert "Second project" not in outputs[0]["description"]


def test_word_nonbreaking_hyphen_preserves_skill_name():
    extracted = extract_docx_text(BytesIO(hyphenated_skill_docx()))
    assert extracted == "Skills\nscikit-learn"
    result = build_extraction_result("doc_skill", extracted, [])
    validator("Extraction").validate(result)
    assert [row["title"] for row in result["suggestedSections"]["skills"]] == ["scikit-learn"]


@pytest.mark.parametrize("case,field,expected", [
    ("mixed_outputs", "researchOutputs", [
        {"title": "Data explorer", "type": "PROJECT", "url": None},
        {"title": "Graph paper", "type": "PUBLICATION", "url": None},
    ]),
    ("publication_links", "researchOutputs", [
        {"title": "Paper A", "type": "PUBLICATION", "url": None},
        {"title": "Paper B", "type": "PUBLICATION", "url": "https://example.test/paper-b"},
    ]),
    ("skill_hyphen", "skills", [{"title": "scikit-learn"}]),
], ids=["mixed-outputs", "publication-links", "skill-hyphen"])
def test_layout_fixes_survive_reviewed_import(app, signed, tmp_path, case, field, expected):
    client, csrf = signed
    app.config["DOCUMENT_STORAGE_DIR"] = str(tmp_path / "documents")
    before = client.get("/api/v1/me/profile").json
    if case == "skill_hyphen":
        content = hyphenated_skill_docx()
    else:
        source = PROJECT_SOURCE + "\nPublication: Graph paper" if case == "mixed_outputs" else PUBLICATIONS_SOURCE
        content = text_docx(source)
    document_id = upload(client, csrf, content, "review.docx")
    process(app)
    extraction = client.get(f"/api/v1/me/documents/{document_id}/extraction").json
    validator("Extraction").validate(extraction)
    rows = extraction["suggestedSections"][field]
    keys = expected[0].keys()
    assert [{key: row[key] for key in keys} for row in rows] == expected
    assert client.get("/api/v1/me/profile").json == before

    response = client.post(
        f"/api/v1/me/documents/{document_id}/apply", headers=headers(csrf),
        json={"expectedProfileRevision": before["revision"], "sections": {field: rows}},
    )
    assert response.status_code == 200, response.json
    validator("Profile").validate(response.json)
    saved = client.get("/api/v1/me/profile").json
    assert saved == response.json
    assert saved["content"][field] == rows
    assert saved["confirmation"]["status"] == "UNCONFIRMED"
