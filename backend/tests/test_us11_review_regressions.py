"""Reproductions from the MR !40 review, including real API and MySQL coverage."""

from copy import deepcopy

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.dialects.mysql import dialect
from sqlalchemy.schema import CreateTable

from backend.src.db.models import ProfileSkill, ProfileTextDetails
from backend.src.db.schema_upgrades import upgrade_resume_text
from backend.src.db.skills import matching_skills
from backend.tests.conftest import headers
from backend.tests.test_us04 import make_opportunity, research_team
from backend.tests.test_us09_extraction import process, text_docx, upload
from backend.tests.test_us11 import apply, checked, profile, save


@pytest.mark.parametrize("evidence", [
    "No R experience, but I have used Python for data analysis.",
    "No experience with R; Python was used in my project.",
    "I do not know R and have used Python for data analysis.",
    "No R experience. Used Python for data analysis.",
    "不会 R，但使用过 Python。",
    "没有R经验，使用过Python处理数据。",
])
def test_a_denial_of_r_does_not_negate_python(evidence):
    skills = [{"id": title, "title": title, "evidenceText": evidence} for title in ("Python", "R")]
    result = matching_skills(skills, {"python": "Python", "r": "R"})
    assert result["python"]["claim"] == "HAS"
    assert result["r"]["claim"] == "DOES_NOT_HAVE"


@pytest.mark.parametrize("evidence,expected", [
    ("I do not have experience with Python.", "DOES_NOT_HAVE"),
    ("I am not proficient in Python.", "DOES_NOT_HAVE"),
    ("I have no prior experience using Python.", "DOES_NOT_HAVE"),
    ("没有使用过Python。", "DOES_NOT_HAVE"),
    ("Python不会，但是会R。", "DOES_NOT_HAVE"),
    ("I used not only Python but also R.", "HAS"),
    ("No R experience but worked with Python.", "HAS"),
])
def test_only_a_target_specific_negative_becomes_a_gap(evidence, expected):
    result = matching_skills([{"id": "python_record", "title": "Python", "evidenceText": evidence}], {"p": "Python"})
    assert result["p"]["claim"] == expected


@pytest.mark.parametrize("legacy", [True, False])
@pytest.mark.parametrize("evidence", ["No R experience, but used Python in my project.", "不会 R，但使用过 Python。"])
def test_confirmed_python_stays_matched_through_owner_and_team_http(app, signed, research_team, legacy, evidence):
    client, csrf = signed
    before = profile(client)
    content = deepcopy(before["content"])
    content["displayName"] = "Review regression talent"
    if legacy:
        with app.extensions["database"].transaction(write=True) as db:
            db.add(ProfileSkill(talent_id=before["talentId"], tag_id="skill_python", claim="HAS",
                                evidence_text=evidence, position=0))
        content = profile(client)["content"]
        content["displayName"] = "Review regression talent"
    else:
        content["skills"] = [{"id": "free_python", "title": "Python", "evidenceText": evidence}]
    saved = checked(save(signed, content, before["revision"]))
    checked(client.post("/api/v1/me/profile/confirmation", headers=headers(csrf), json={"expectedRevision": saved["revision"]}))
    opportunity = make_opportunity(research_team, [{"id": "python", "label": "Python", "kind": "SKILL",
                     "importance": "REQUIRED", "tagIds": ["skill_python"]}])
    own = checked(client.get(f"/api/v1/me/opportunity-matches/{opportunity['id']}"), schema="OwnerMatch")
    assert own["requirements"][0]["status"] == "MATCHED"
    assert own["summary"]["score"] == 100
    checked(client.put("/api/v1/me/privacy", headers=headers(csrf), json={"expectedRevision": 0,
                  "discoverable": True, "visibleFields": ["skills"]}))
    team, _ = research_team
    shared = checked(team.get(f"/api/v1/opportunities/{opportunity['id']}/talent-matches/{saved['talentId']}"), schema="TeamMatch")
    assert shared["requirements"][0]["status"] == "MATCHED"
    assert shared["summary"]["score"] == 100


@pytest.mark.parametrize("length", [17000, 20000])
@pytest.mark.parametrize("reviewed", [False, True])
def test_four_byte_resume_text_within_api_limit_saves_and_reloads(app, signed, tmp_path, length, reviewed):
    client, csrf = signed
    before = profile(client)
    resume = "\U0001f9ea" * length
    assert len(resume.encode("utf-8")) > 65535
    if reviewed:
        app.config["DOCUMENT_STORAGE_DIR"] = str(tmp_path / "documents")
        doc = upload(client, csrf, text_docx("Skills: Python"), "resume.docx")
        process(app)
        saved = checked(apply(signed, doc, {"resumeDescription": resume}, before["revision"]), schema="Profile")
    else:
        content = deepcopy(before["content"])
        content["resumeDescription"] = resume
        saved = checked(save(signed, content, before["revision"]), schema="Profile")
    assert saved["content"]["resumeDescription"] == resume
    assert profile(client)["content"]["resumeDescription"] == resume
    content = deepcopy(saved["content"])
    content["resumeDescription"] = "\U0001f9ea" * 20001
    checked(save(signed, content, saved["revision"]), 422)
    assert profile(client) == saved


def test_mysql_ddl_can_store_the_full_unicode_resume_limit():
    ddl = str(CreateTable(ProfileTextDetails.__table__).compile(dialect=dialect()))
    assert "resume_description MEDIUMTEXT NOT NULL" in ddl


def test_existing_mysql_text_column_upgrade_preserves_profile_and_is_repeatable(app, signed):
    database = app.extensions["database"]
    client, _ = signed
    if database.engine.dialect.name != "mysql":
        assert upgrade_resume_text(database) is False
        return
    # --run-mysql fixtures enforce a disposable database name before any DDL.
    assert database.engine.url.database.endswith("_test")
    content = profile(client)["content"]
    content["resumeDescription"] = "Preserved original text \U0001f9ea"
    content["researchInterestText"] = "Preserved interest description"
    saved = checked(save(signed, content, 0))
    with database.engine.begin() as connection:
        connection.exec_driver_sql("ALTER TABLE profile_text_details MODIFY COLUMN resume_description TEXT NOT NULL")
    assert type(next(c for c in inspect(database.engine).get_columns("profile_text_details")
                     if c["name"] == "resume_description")["type"]).__name__ == "TEXT"
    command = app.test_cli_runner().invoke(args=["upgrade-resume-text"])
    assert command.exit_code == 0, command.output
    assert "widened" in command.output
    assert app.test_cli_runner().invoke(args=["upgrade-resume-text"]).exit_code == 0
    assert profile(client) == saved
    assert type(next(c for c in inspect(database.engine).get_columns("profile_text_details")
                     if c["name"] == "resume_description")["type"]).__name__ == "MEDIUMTEXT"
    content["resumeDescription"] = "\U0001f9ea" * 20000
    updated = checked(save(signed, content, saved["revision"]))
    assert profile(client) == updated
    with database.transaction() as db:
        assert db.scalar(select(ProfileTextDetails.research_interest_text)) == "Preserved interest description"
