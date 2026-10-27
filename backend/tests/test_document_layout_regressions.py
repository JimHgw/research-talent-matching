from io import BytesIO

import pytest
from docx import Document as DocxDocument
from docx.oxml import OxmlElement
from lxml import etree

from backend.src.features.documents.suggestions import build_extraction_result
from backend.src.features.documents.text import extract_docx_text
from backend.src.shared.validation import validator


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