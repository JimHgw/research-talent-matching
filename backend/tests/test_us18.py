from copy import deepcopy
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
@pytest.fixture(
    params=[False, True],
    ids=["fresh-schema", "upgraded-legacy-schema"],
)
def academic_schema(request, app, research_team):
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

    command = app.test_cli_runner().invoke(
        args=["upgrade-academic-requirements"]
    )

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