from copy import deepcopy
import os
from pathlib import Path
import shlex
import subprocess
import sys
from sqlalchemy import inspect, text
from sqlalchemy.exc import OperationalError

from backend.src.db.academic_upgrade import (
    KINDS,
    kind_values,
    upgrade_academic_requirements,
)
import pytest

from test_us04 import (
    OPPORTUNITIES,
    checked,
    confirm_profile,
    example,
    make_opportunity,
    research_team,
)
from test_us05 import share
from test_docker_backend import posix_shell
from backend.src.shared.paths import ROOT
from conftest import headers
from test_us04 import MATCHES, PROFILE, assert_error


@pytest.mark.parametrize("values", [("SKILL", "INTEREST"), KINDS])
@pytest.mark.parametrize("charset", ["", "_utf8mb4", "_utf8mb3"])
def test_reflected_kind_constraint_preserves_underscores(values, charset):
    literals = ", ".join(f"{charset}'{value}'" for value in values)
    assert kind_values(f"(`kind` in ({literals}))") == set(values)


@pytest.mark.parametrize("expression", [
    "kind IN ('SKILL', 'UNSUPPORTED')",
    "other_kind IN ('SKILL', 'INTEREST')",
    "kind IN ('SKILL', 'INTEREST') OR 1=1",
])
def test_unrecognised_kind_constraints_are_not_silently_replaced(expression):
    with pytest.raises(ValueError, match="Unrecognised"):
        kind_values(expression)


def test_academic_upgrade_explicitly_skips_only_when_requested(app):
    if app.extensions["database"].engine.dialect.name == "mysql":
        pytest.skip("This test exercises the non-MySQL startup path.")
    runner = app.test_cli_runner()
    skipped = runner.invoke(args=["upgrade-academic-requirements", "--if-mysql"])
    assert skipped.exit_code == 0, skipped.output
    assert "skipped for non-MySQL" in skipped.output
    explicit = runner.invoke(args=["upgrade-academic-requirements"])
    assert explicit.exit_code != 0
    assert "targets existing MySQL databases" in explicit.output


@pytest.fixture(
    params=[False, True, "startup"],
    ids=["fresh-schema", "upgraded-legacy-schema", "upgraded-startup-schema"],
)
def academic_schema(request, app, research_team, tmp_path):
    if not request.param:
        return

    database = app.extensions["database"]

    if database.engine.dialect.name != "mysql":
        pytest.skip("Run with --run-mysql to test the legacy upgrade.")

    assert database.engine.url.database.endswith("_test")
    # Create a legacy opportunity with a narrow kind column, no criteria column, and a check constraint that only allows SKILL and INTEREST.
    legacy = make_opportunity(
        research_team,
        [
            {
                "id": "legacy_tag",
                "label": "Python",
                "kind": "SKILL",
                "importance": "REQUIRED",
                "tagIds": ["skill_python"],
            },
            {
                "id": "legacy_text",
                "label": "Python research",
                "kind": "SKILL",
                "importance": "PREFERRED",
                "tagIds": [],
                "skillTitles": ["Python"],
            },
        ],
    )
    # The legacy opportunity has a narrow kind column, no criteria column, and a check constraint that only allows SKILL and INTEREST.
    team = research_team[0]
    url = f"{OPPORTUNITIES}/{legacy['id']}"
    before = checked(team.get(url), "Opportunity")

    def read_children(connection):
        return {
            table: [
                dict(row)
                for row in connection.execute(
                    text(
                        f"SELECT * FROM {table} "
                        "WHERE opportunity_id = :id "
                        "ORDER BY requirement_id"
                    ),
                    {"id": legacy["id"]},
                ).mappings()
            ]
            for table in (
                "requirement_tags",
                "opportunity_skill_details",
            )
        }
    # Simulate a legacy schema with a narrow kind column, no criteria column, and a check constraint that only allows SKILL and INTEREST.
    with database.engine.begin() as connection:
        children_before = read_children(connection)

        
        connection.exec_driver_sql("""
            ALTER TABLE opportunity_requirements
                DROP CHECK ck_opportunity_requirement_kind,
                DROP COLUMN criteria,
                MODIFY COLUMN kind VARCHAR(16) NOT NULL,
                ADD CONSTRAINT ck_legacy_requirement_kind
                    CHECK (kind IN ('SKILL', 'INTEREST'))
        """)

    old_columns = {
        column["name"]: column
        for column in inspect(database.engine).get_columns(
            "opportunity_requirements"
        )
    }

    assert "criteria" not in old_columns
    assert old_columns["kind"]["type"].length == 16

    if request.param == "startup":
        # Exercise the same startup path used by both API and worker images,
        # against the old table and persistent MySQL data above.
        tools_dir = tmp_path / "startup tools"
        tools_dir.mkdir()
        python = tools_dir / "python"
        python.write_text(
            f"#!/bin/sh\nexec {shlex.quote(Path(sys.executable).as_posix())} \"$@\"\n",
            encoding="utf-8", newline="\n",
        )
        python.chmod(0o755)
        command = subprocess.run(
            [posix_shell(), (ROOT / "backend/docker/entrypoint.sh").as_posix(),
             sys.executable, "-c", "print('SERVER STARTED')"],
            cwd=ROOT,
            env={**os.environ, "DATABASE_URL": database.engine.url.render_as_string(hide_password=False),
                 "PATH": str(tools_dir) + os.pathsep + os.environ.get("PATH", ""),
                 "FLASK_SKIP_DOTENV": "1"},
            capture_output=True, text=True, timeout=60,
        )
        output = command.stdout + command.stderr
        assert command.returncode == 0, output
        assert "SERVER STARTED" in output
        assert "storage upgraded" in output
    else:
        command = app.test_cli_runner().invoke(args=["upgrade-academic-requirements"])
        assert command.exit_code == 0, command.output
        assert "storage upgraded" in command.output

    
    assert upgrade_academic_requirements(database) is False

    inspector = inspect(database.engine)

    columns = {
        column["name"]: column
        for column in inspector.get_columns("opportunity_requirements")
    }
    # Verify that the kind column is widened and the criteria column is added.
    assert columns["kind"]["type"].length >= 32
    assert "criteria" in columns
    assert columns["criteria"]["nullable"] is True

    checks = [
        check
        for check in inspector.get_check_constraints(
            "opportunity_requirements"
        )
        if "kind" in check["sqltext"].lower()
    ]

    assert len(checks) == 1
    assert kind_values(checks[0]["sqltext"]) == set(KINDS)

    # Verify that the opportunity and its children are unchanged.
    assert checked(team.get(url), "Opportunity") == before

    with database.engine.connect() as connection:
        assert read_children(connection) == children_before

    # MySQL/PyMySQL reports CHECK violations as OperationalError.
    with pytest.raises(OperationalError) as error:
        with database.engine.begin() as connection:
            connection.execute(
                text("""
                    UPDATE opportunity_requirements
                    SET kind = 'UNSUPPORTED'
                    WHERE opportunity_id = :id
                """),
                {"id": legacy["id"]},
            )
    assert error.value.orig.args[0] == 3819
    assert (
        "ck_opportunity_requirement_kind"
        in str(error.value.orig)
    )

@pytest.mark.parametrize(
    "kind,section,criteria,status,score,record_id",
    [
        (
            "EDUCATION",
            "education",
            {"qualification": "Master of Data Science"},
            "MATCHED",
            100,
            "edu_test",
        ),
        (
            "RESEARCH_EXPERIENCE",
            "researchExperience",
            {
                "title": "Research Assistant",
                "organisation": "Another laboratory",
            },
            "PARTIAL",
            50,
            "exp_test",
        ),
        (
            "RESEARCH_OUTPUT",
            "researchOutputs",
            {"type": "PUBLICATION"},
            "MATCHED",
            100,
            "output_test",
        ),
        (
            "RESEARCH_OUTPUT",
            "researchOutputs",
            {"type": "PROJECT"},
            "UNKNOWN",
            0,
            None,
        ),
    ],
)
def test_academic_evidence_api(
    signed,
    research_team,
    academic_schema,
    kind,
    section,
    criteria,
    status,
    score,
    record_id,
):
    content = deepcopy(example("profile-write.json")["content"])

    content["education"] = [{
        "id": "edu_test",
        "institution": "Example University",
        "qualification": "Master of Data Science",
        "discipline": "Data Science",
        "startYear": 2020,
        "endYear": 2022,
    }]

    content["researchExperience"] = [{
        "id": "exp_test",
        "title": "Research Assistant",
        "organisation": "Laboratory A",
        "description": "Research data analysis.",
    }]

    content["researchOutputs"] = [{
        "id": "output_test",
        "title": "Stored publication title",
        "type": "PUBLICATION",
        "url": None,
        "description": "Confirmed publication record.",
    }]

    profile = confirm_profile(signed, content)
    share(signed, [section])

    requirement = {
        "id": "req_academic",
        "label": "Academic requirement",
        "kind": kind,
        "importance": "REQUIRED",
        "tagIds": [],
        "criteria": criteria,
    }

    opportunity = make_opportunity(
        research_team,
        [requirement],
    )

    team = research_team[0]

    saved = checked(
        team.get(f"{OPPORTUNITIES}/{opportunity['id']}"),
        "Opportunity",
    )

    assert saved["content"]["requirements"][0] == requirement

    # Updating only the title must preserve academic criteria with empty tagIds.
    updated_content = deepcopy(saved["content"])
    updated_content["title"] = "Updated research opportunity title"
    saved = checked(team.put(
        f"{OPPORTUNITIES}/{opportunity['id']}",
        json={"expectedRevision": saved["revision"], "content": updated_content},
        headers=headers(research_team[1]),
    ), "Opportunity")
    assert saved["content"]["requirements"][0] == requirement

    url = (
        f"{OPPORTUNITIES}/{opportunity['id']}"
        f"/talent-matches/{profile['talentId']}"
    )

    detail = checked(team.get(url), "TeamMatch")
    result = detail["requirements"][0]

    assert result["status"] == status
    expected_codes = {
        "MATCHED": "ACADEMIC_CRITERIA_SUPPORTED",
        "PARTIAL": "ACADEMIC_CRITERIA_PARTIAL",
        "UNKNOWN": "INSUFFICIENT_EVIDENCE",
    }

    assert result["reasonCode"] == expected_codes[status]
    assert detail["summary"]["score"] == score
    assert detail["summary"]["algorithmVersion"] == "academic-evidence-v3"

    owner = checked(signed[0].get(f"{MATCHES}/{opportunity['id']}"), "OwnerMatch")
    owner_result = owner["requirements"][0]
    assert owner_result["status"] == status
    assert owner_result["reasonCode"] == expected_codes[status]
    assert owner["summary"] == detail["summary"]
    assert [
        {key: evidence[key] for key in ("field", "recordId", "valueSummary")}
        for evidence in owner_result["evidence"]
    ] == result["evidence"]
    for evidence in owner_result["evidence"]:
        assert evidence["confirmedRevision"] == profile["revision"]

    page = checked(team.get(
        f"{OPPORTUNITIES}/{opportunity['id']}/talent-matches"
    ), "TalentMatchPage")
    assert page["items"][0]["summary"] == detail["summary"]

    if record_id is None:
        assert result["evidence"] == []
    else:
        evidence = result["evidence"][0]
        expected_summaries = {
            "edu_test": (
                "Master of Data Science. Supporting fields: "
                "qualification: Master of Data Science"
            ),
            "exp_test": (
                "Research Assistant. Supporting fields: "
                "title: Research Assistant"
            ),
            "output_test": (
                "Stored publication title. Supporting fields: "
                "type: PUBLICATION"
            ),
        }

        assert (
            evidence["valueSummary"]
            == expected_summaries[record_id]
        )

        stored_record = next(
            record
            for record in profile["content"][section]
            if record["id"] == record_id
        )

        if section == "education":
            assert (
                stored_record["qualification"]
                in evidence["valueSummary"]
            )
        else:
            assert stored_record["title"] in evidence["valueSummary"]

        if status == "PARTIAL":
            assert "Another laboratory" not in evidence["valueSummary"]
        assert evidence["field"] == section
        assert evidence["recordId"] == record_id
        assert set(evidence) == {
            "field",
            "recordId",
            "valueSummary",
        }

    # Test that if the profile is not shared, the requirement is hidden and the score is 0.
    share(signed, [])

    hidden = checked(team.get(url), "TeamMatch")

    assert hidden["requirements"][0]["status"] == "UNKNOWN"
    assert hidden["requirements"][0]["evidence"] == []
    assert hidden["summary"]["score"] == 0
    assert (
        hidden["requirements"][0]["reasonCode"]
        == "INSUFFICIENT_EVIDENCE"
    )

    share(signed, [section])
    restored = checked(team.get(url), "TeamMatch")
    assert restored["requirements"] == detail["requirements"]

    changed_content = deepcopy(saved["content"])
    changed_content["requirements"][0]["criteria"] = {
        "EDUCATION": {"qualification": "A different qualification"},
        "RESEARCH_EXPERIENCE": {"title": "A different title"},
        "RESEARCH_OUTPUT": {"type": "OTHER"},
    }[kind]
    changed = checked(team.put(
        f"{OPPORTUNITIES}/{opportunity['id']}",
        json={"expectedRevision": saved["revision"], "content": changed_content},
        headers=headers(research_team[1]),
    ), "Opportunity")
    refreshed = checked(team.get(url), "TeamMatch")
    assert refreshed["opportunityRevision"] == changed["revision"]
    assert refreshed["requirements"][0]["status"] == "UNKNOWN"
    assert refreshed["requirements"][0]["reasonCode"] == "INSUFFICIENT_EVIDENCE"
    assert refreshed["requirements"][0]["evidence"] == []
    assert refreshed["summary"]["score"] == 0


@pytest.mark.parametrize("kind,criteria", [
    ("EDUCATION", {}),
    ("EDUCATION", {"qualification": "   "}),
    ("EDUCATION", {"type": "PUBLICATION"}),
    ("RESEARCH_EXPERIENCE", {"organisation": 123}),
    ("RESEARCH_OUTPUT", {"type": "JOURNAL"}),
    ("RESEARCH_OUTPUT", {"title": "x" * 301}),
])
def test_invalid_academic_criteria_are_rejected(research_team, kind, criteria):
    team, csrf = research_team
    content = example("opportunity-create.json")
    content["requirements"] = [{
        "id": "invalid", "label": "Academic requirement", "kind": kind,
        "importance": "REQUIRED", "tagIds": [], "criteria": criteria,
    }]
    assert_error(team.post(OPPORTUNITIES, json=content, headers=headers(csrf)),
                 422, "VALIDATION_ERROR")


def test_academic_profile_edits_require_confirmation_and_refresh_evidence(signed, research_team):
    content = deepcopy(example("profile-write.json")["content"])
    content["education"] = [{
        "id": "edu_refresh", "institution": "Example University",
        "qualification": "Master of Data Science", "discipline": "Data Science",
        "startYear": 2020, "endYear": 2022,
    }]
    profile = confirm_profile(signed, content)
    share(signed, ["education"])
    opportunity = make_opportunity(research_team, [{
        "id": "education", "label": "Master's degree", "kind": "EDUCATION",
        "importance": "REQUIRED", "tagIds": [],
        "criteria": {"qualification": "Master of Data Science"},
    }])
    team = research_team[0]
    base = f"{OPPORTUNITIES}/{opportunity['id']}/talent-matches"
    url = f"{base}/{profile['talentId']}"
    assert checked(team.get(url), "TeamMatch")["summary"]["score"] == 100

    content["education"][0]["qualification"] = "Bachelor of Science"
    saved = checked(signed[0].put(PROFILE, json={
        "expectedRevision": profile["revision"], "content": content,
    }, headers=headers(signed[1])), "Profile")
    assert checked(team.get(base), "TalentMatchPage")["items"] == []
    assert_error(team.get(url), 404, "NOT_FOUND")
    checked(signed[0].post(PROFILE + "/confirmation", json={
        "expectedRevision": saved["revision"],
    }, headers=headers(signed[1])), "Profile")

    refreshed = checked(team.get(url), "TeamMatch")
    result = refreshed["requirements"][0]
    assert result["status"] == "UNKNOWN"
    assert result["reasonCode"] == "INSUFFICIENT_EVIDENCE"
    assert result["evidence"] == []
    assert refreshed["summary"]["score"] == 0
