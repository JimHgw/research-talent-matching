from copy import deepcopy

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
    assert detail["summary"]["score"] == score
    assert detail["summary"]["algorithmVersion"] == "academic-evidence-v3"

    if record_id is None:
        assert result["evidence"] == []
    else:
        evidence = result["evidence"][0]

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