"""CV layouts that previously lost skills, merged projects or invented outputs."""

from io import BytesIO

import pytest

from backend.src.features.documents.suggestions import build_extraction_result
from backend.src.features.documents.text import extract_docx_text, extract_pdf_text
from backend.src.shared.validation import validator
from backend.tests.conftest import headers
from backend.tests.test_us09_extraction import process, text_docx, text_pdf, upload


PROJECT = "Projects\nGraph benchmark\nTeam Project | 2024 - 2025\n"

CASES = {
    "wrapped-conjunction": (
        PROJECT + "- Built an API with Python and\nFlask\n- Deployed to AWS\n",
        "researchOutputs", ["Graph benchmark"], "Python and Flask",
    ),
    "leadership-skill": (
        "Skills\nPython\nLeadership\nCommunication\nTeamwork\n",
        "skills", ["Python", "Leadership", "Communication", "Teamwork"], "",
    ),
    "spaced-unknown-skill": (
        "Skills\nH T M L\nPython\nJavaScript\n",
        "skills", ["H T M L", "Python", "JavaScript"], "",
    ),
    "portfolio-title": (
        "Projects\nPortfolio\nTeam Project | 2024 - 2025\nBuilt a personal website.\n",
        "researchOutputs", ["Portfolio"], "Built a personal website.",
    ),
    "publication-then-project": (
        "Publications\nPUBLICATION | Paper A | https://example.test/paper\n"
        "OPEN SOURCE PROJECTS\nGraph benchmark\nTeam Project | 2024 - 2025\nBuilt a tool.\n",
        "researchOutputs", ["Paper A", "Graph benchmark"], "",
    ),
    "wrapped-noun": (
        PROJECT + "- Built a dashboard to monitor model\nperformance\n- Deployed to AWS\n",
        "researchOutputs", ["Graph benchmark"], "model performance",
    ),
    "portfolio-in-outputs": (
        "Research outputs\nPortfolio\nTeam Project | 2024 - 2025\nBuilt a personal website.\n",
        "researchOutputs", ["Portfolio"], "Built a personal website.",
    ),
    "dated-description": (
        PROJECT + "- Launched first version | 2024\n- Deployed to AWS\n",
        "researchOutputs", ["Graph benchmark"], "Launched first version | 2024",
    ),
    "spaced-heading-with-colon": (
        "Skills\nPython\nL E A D E R S H I P:\nClub President | Example Club\nOrganised events.\n",
        "skills", ["Python"], "",
    ),
    "numbered-projects": (
        "Projects\n1. API service | 2024 - 2025\n- Built the API.\n\n"
        "2. Data explorer | 2025 - 2026\n- Built a dashboard.\n",
        "researchOutputs", ["API service", "Data explorer"], "",
    ),
    "bulleted-projects": (
        "Projects\nAPI service | 2024 - 2025\n- Built the API.\n\n"
        "- Data explorer | 2025 - 2026\n- Built a dashboard.\n",
        "researchOutputs", ["API service", "Data explorer"], "",
    ),
    "adjacent-undated-projects": (
        "Projects\nAPI service\n- Built the API\nData explorer\n- Built a dashboard\n",
        "researchOutputs", ["API service", "Data explorer"], "",
    ),
    "spaced-portfolio-title": (
        "Projects\nP O R T F O L I O\nTeam Project | 2024 - 2025\nBuilt a personal website.\n",
        "researchOutputs", ["PORTFOLIO"], "Built a personal website.",
    ),
    "spaced-leadership-skill": (
        "Skills\nPython\nL E A D E R S H I P\nCommunication\nTeamwork\n",
        "skills", ["Python", "LEADERSHIP", "Communication", "Teamwork"], "",
    ),
    "wrapped-proper-name": (
        PROJECT + "- Built a dashboard on Amazon\nWeb Services\n- Deployed the application.\n",
        "researchOutputs", ["Graph benchmark"], "Amazon Web Services",
    ),
    "numbered-achievement": (
        PROJECT + "1. Achieved 95% accuracy | 2024\n2. Reduced model latency.\n",
        "researchOutputs", ["Graph benchmark"], "Achieved 95% accuracy | 2024",
    ),
    "achievement-after-completed-description": (
        PROJECT + "Built a model.\n1. Achieved 95% accuracy | 2024\n2. Reduced model latency.\n",
        "researchOutputs", ["Graph benchmark"], "Achieved 95% accuracy | 2024",
    ),
    "reduced-order-modelling": (
        "Projects\nReduced order modelling | 2024 - 2025\nEvaluated approximation methods.\n",
        "researchOutputs", ["Reduced order modelling"], "Evaluated approximation methods.",
    ),
    "inline-numbered-project-heading": (
        "Projects: 1. API service | 2024 - 2025\nBuilt the API.\n",
        "researchOutputs", ["API service"], "Built the API.",
    ),
    "inline-numbered-project-sequence": (
        "Projects: 1. API service | 2024 - 2025\n- Built the API.\n"
        "2. Data explorer | 2025 - 2026\n- Built a dashboard.\n",
        "researchOutputs", ["API service", "Data explorer"], "",
    ),
    "mixed-project-dates": (
        "Projects\nAPI service | 2024 - 2025\n- Built the API\n"
        "Data Explorer\n- Built a dashboard\n",
        "researchOutputs", ["API service", "Data Explorer"], "",
    ),
    "undated-wrapped-proper-name": (
        "Projects\nGraph benchmark\n- Built a dashboard on Amazon\n"
        "Web Services\n- Deployed the application.\n",
        "researchOutputs", ["Graph benchmark"], "Amazon Web Services",
    ),
    "indented-numbered-achievements": (
        "Projects\n1. Graph benchmark | 2024 - 2025\n  1. Built a model.\n"
        "  2. Achieved 95% accuracy | 2024\n  3. Reduced model latency.\n",
        "researchOutputs", ["Graph benchmark"], "Achieved 95% accuracy | 2024",
    ),
}


def checked_sections(result, case):
    validator("Extraction").validate(result)
    _, field, titles, preserved = CASES[case]
    rows = result["suggestedSections"].get(field, [])
    assert [row["title"] for row in rows] == titles
    if field == "researchOutputs":
        assert all(row["type"] == ("PUBLICATION" if row["title"] == "Paper A" else "PROJECT") for row in rows)
        if len(rows) > 1:
            assert rows[1]["title"] not in rows[0]["description"]
    if preserved:
        assert preserved in rows[0]["description"]
    return field, rows


@pytest.mark.parametrize("case", CASES)
@pytest.mark.parametrize("format", ["text", "docx", "pdf"])
def test_cv_boundaries_survive_document_text_extraction(case, format, tmp_path):
    source = CASES[case][0]
    if format == "docx":
        source = extract_docx_text(BytesIO(text_docx(source)))
    elif format == "pdf":
        path = tmp_path / "resume.pdf"
        path.write_bytes(text_pdf(source))
        source = extract_pdf_text(path)
    checked_sections(build_extraction_result("doc_boundaries", source, []), case)


@pytest.mark.parametrize("marker", ["- ", "* ", "\u2022 ", "\u2013 ", "\u2014 ", "2. ", "2) "])
def test_dated_project_after_a_blank_line_accepts_list_markers(marker):
    source = "Projects\nAPI service | 2024 - 2025\nBuilt the API.\n\n"
    source += marker + "Data explorer | 2025 - 2026\nBuilt a dashboard.\n"
    result = build_extraction_result("doc_markers", source, [])
    validator("Extraction").validate(result)
    rows = result["suggestedSections"]["researchOutputs"]
    assert [row["title"] for row in rows] == ["API service", "Data explorer"]


def test_consecutive_numbered_projects_do_not_require_empty_paragraphs():
    source = CASES["numbered-projects"][0].replace("\n\n", "\n")
    checked_sections(build_extraction_result("doc_numbered", source, []), "numbered-projects")


def test_large_word_layout_gap_keeps_the_project_and_its_description():
    source = PROJECT + "\n" * 6000 + "Built a tool."
    extracted = extract_docx_text(BytesIO(text_docx(source)))
    result = build_extraction_result("doc_gap", extracted, [])
    validator("Extraction").validate(result)
    row, = result["suggestedSections"]["researchOutputs"]
    assert row["title"] == "Graph benchmark"
    assert "Built a tool." in row["description"]


@pytest.mark.parametrize("case", [
    "bulleted-projects", "spaced-leadership-skill", "wrapped-proper-name", "numbered-achievement",
])
@pytest.mark.parametrize("format", ["docx", "pdf"])
def test_reviewed_import_persists_the_correct_boundaries(app, signed, tmp_path, case, format):
    client, csrf = signed
    app.config["DOCUMENT_STORAGE_DIR"] = str(tmp_path / "documents")
    before = client.get("/api/v1/me/profile").json
    source = CASES[case][0]
    content = text_docx(source) if format == "docx" else text_pdf(source)
    document_id = upload(client, csrf, content, "resume." + format)
    process(app)
    extraction = client.get(f"/api/v1/me/documents/{document_id}/extraction").json
    field, rows = checked_sections(extraction, case)
    assert client.get("/api/v1/me/profile").json == before
    applied = client.post(
        f"/api/v1/me/documents/{document_id}/apply", headers=headers(csrf),
        json={"expectedProfileRevision": before["revision"], "sections": {field: rows}},
    )
    assert applied.status_code == 200, applied.json
    validator("Profile").validate(applied.json)
    saved = client.get("/api/v1/me/profile").json
    assert saved["content"][field] == rows
    assert saved["confirmation"]["status"] == "UNCONFIRMED"
