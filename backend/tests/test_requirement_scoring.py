"""Requirement-level model scoring, weighted totals and evidence boundaries."""

import math

import pytest

from backend.src.features.matching.engine import evaluate_opportunity
from backend.src.features.matching.semantic_runtime import enrich_matches
from conftest import headers
from test_semantic_matching import profile, semantic_app
from test_us04 import MATCHES, RECOMMENDATIONS, checked, confirm_profile, research_team
from test_us05 import share
from test_us14 import opportunity


class Vectors:
    def __init__(self, mapping):
        self.mapping = mapping
        self.calls = []

    def encode(self, texts):
        self.calls.append(list(texts))
        return [self.mapping[text] + [0] * 382 for text in texts]


def requirement(kind, label="target", *, importance="REQUIRED", **extra):
    value = {"id": "req_" + kind.lower(), "kind": kind, "label": label,
             "importance": importance, "tagIds": []}
    if kind == "SKILL":
        value["skillTitles"] = [label]
    return {**value, **extra}


def snapshot(**fields):
    return {"skills": {}, "skillRecords": [], "researchInterests": {},
            "researchInterestText": "", "customInterestTags": [],
            "education": [], "researchExperience": [], "researchOutputs": [],
            "origins": {}, "revision": 1, **fields}


def evaluate(app, requirements, fields, encoder):
    app.config["SEMANTIC_MATCHING_ENABLED"] = True
    app.extensions["semantic_matching"]._encoder = encoder
    published = {"content": {"researchArea": "", "requirements": requirements}}
    with app.app_context():
        results, summary = evaluate_opportunity(published, fields)
        enrich_matches([(published, fields, results, summary)])
    return results, summary


@pytest.mark.parametrize("kind,fields,criteria,expected", [
    ("SKILL", {"skillRecords": [{"id": "skill_test", "title": "source", "evidenceText": ""}]}, {}, 80),
    ("INTEREST", {"researchInterestText": "source"}, {}, 80),
    ("EDUCATION", {"education": [{"id": "edu_test", "qualification": "Masters", "discipline": "source"}]},
     {"criteria": {"qualification": "Masters", "discipline": "target"}}, 90),
    ("RESEARCH_EXPERIENCE", {"researchExperience": [{"id": "exp_test", "title": "source", "description": ""}]},
     {"criteria": {"title": "target"}}, 80),
    ("RESEARCH_OUTPUT", {"researchOutputs": [{"id": "out_test", "type": "PUBLICATION", "title": "source", "description": ""}]},
     {"criteria": {"type": "PUBLICATION", "title": "target"}}, 90),
])
def test_all_requirement_kinds_have_individual_scores(app, kind, fields, criteria, expected):
    rows, summary = evaluate(app, [requirement(kind, **criteria)], snapshot(**fields),
                             Vectors({"source": [1, 0], "target": [.8, .6]}))
    scoring = rows[0]["scoring"]
    assert scoring["score"] == scoring["contribution"] == expected
    assert scoring["method"] == "SEMANTIC"
    assert scoring["matches"][0]["recordId"] == (None if kind == "INTEREST" else fields[next(iter(fields))][0]["id"])
    assert summary["recommendationScore"] == expected
    assert summary["rankingAlgorithmVersion"] == "requirement-semantic-v1"


def test_total_uses_each_requirement_weight_and_retains_missing_denominator(app):
    requirements = [requirement("SKILL", "skill-target"),
                    requirement("INTEREST", "interest-target", importance="PREFERRED"),
                    requirement("EDUCATION", criteria={"qualification": "PhD"})]
    fields = snapshot(skillRecords=[{"id": "skill_test", "title": "source", "evidenceText": ""}],
                      researchInterestText="source")
    encoder = Vectors({"source": [1, 0], "skill-target": [.8, .6], "interest-target": [.6, .8]})
    rows, summary = evaluate(app, requirements, fields, encoder)
    assert [row["scoring"]["score"] for row in rows] == [80, 60, 0]
    assert [row["scoring"]["weight"] for row in rows] == [2, 1, 2]
    assert [row["scoring"]["contribution"] for row in rows] == [32, 12, 0]
    assert summary["recommendationScore"] == 44
    assert summary["semanticRequirements"]["totalWeight"] == 5
    assert len(encoder.calls) == 1
    assert len(encoder.calls[0]) == len(set(encoder.calls[0]))
    assert summary["semanticInterest"]["weight"] == 0


def test_multi_skill_requirement_scores_all_requested_skills(app):
    fields = snapshot(skillRecords=[{"id": "skill_python", "title": "Python", "evidenceText": ""}],
                      skills={"python": {"id": "skill_python", "label": "Python", "claim": "HAS", "evidenceText": ""}})
    rows, summary = evaluate(app, [requirement("SKILL", skillTitles=["Python", "SQL"])], fields,
                             Vectors({"Python": [1, 0], "SQL": [0, 1]}))
    assert rows[0]["scoring"]["score"] == 50
    assert summary["recommendationScore"] == 50


def test_semantic_similarity_does_not_substitute_degree_level_or_output_type(app):
    reqs = [requirement("EDUCATION", criteria={"qualification": "Masters", "discipline": "target"}),
            requirement("RESEARCH_OUTPUT", criteria={"type": "PUBLICATION", "title": "target"})]
    fields = snapshot(education=[{"id": "edu_test", "qualification": "Bachelor", "discipline": "source"}],
                      researchOutputs=[{"id": "out_test", "type": "PROJECT", "title": "source"}])
    encoder = Vectors({"source": [1, 0], "target": [1, 0]})
    rows, summary = evaluate(app, reqs, fields, encoder)
    assert [row["scoring"]["score"] for row in rows] == [50, 50]
    assert summary["recommendationScore"] == 50
    assert not {"Masters", "Bachelor", "PUBLICATION", "PROJECT"} & set(encoder.calls[0])


def test_academic_criteria_cannot_combine_unrelated_records(app):
    req = requirement("EDUCATION", criteria={"qualification": "Masters", "discipline": "target"})
    fields = snapshot(education=[{"id": "edu_a", "qualification": "Masters", "discipline": "other"},
                                 {"id": "edu_b", "qualification": "Bachelor", "discipline": "source"}])
    rows, summary = evaluate(app, [req], fields,
                             Vectors({"source": [1, 0], "target": [1, 0], "other": [0, 1]}))
    assert rows[0]["scoring"]["score"] == 50
    assert summary["recommendationScore"] == 50


@pytest.mark.parametrize("title,evidence", [("No source", ""), ("source", "No experience with source"),
                                            ("source", "\u4e0d\u4f1asource")])
def test_negative_skill_alias_never_receives_positive_semantic_credit(app, title, evidence):
    fields = snapshot(skillRecords=[{"id": "skill_test", "title": title, "evidenceText": evidence}])
    rows, summary = evaluate(app, [requirement("SKILL")], fields,
                             Vectors({"source": [1, 0], "target": [1, 0]}))
    assert rows[0]["scoring"]["score"] == 0
    assert rows[0]["scoring"]["method"] == "EXPLICIT_GAP"
    assert summary["recommendationScore"] == 0


def test_interest_text_cannot_supply_skill_or_degree_credit(app):
    fields = snapshot(researchInterestText="source")
    rows, summary = evaluate(app, [requirement("SKILL"),
                                   requirement("EDUCATION", criteria={"qualification": "target"})],
                             fields, Vectors({}))
    assert [row["scoring"]["method"] for row in rows] == ["MISSING_EVIDENCE"] * 2
    assert summary["recommendationScore"] == 0


def test_skill_privacy_and_reconfirmation_apply_to_every_endpoint(semantic_app, signed, research_team):
    app, encoder = semantic_app
    saved = profile(signed, text="")
    content = saved["content"]
    content["skills"] = [{"id": "skill_test", "title": "Bioengineering", "evidenceText": ""}]
    saved = confirm_profile(signed, content)
    published = opportunity(research_team, requirements=[requirement("SKILL", "Biotechnology")])
    share(signed, ["skills"])
    team, token = research_team
    url = f"/api/v1/opportunities/{published['id']}/talent-matches"
    shortlist = f"/api/v1/opportunities/{published['id']}/shortlist"
    checked(team.put(f"{shortlist}/{saved['talentId']}", headers=headers(token)), "CollectionState")
    owner = checked(signed[0].get(f"{MATCHES}/{published['id']}"), "OwnerMatch")
    detail = checked(team.get(f"{url}/{saved['talentId']}"), "TeamMatch")
    assert detail["summary"]["recommendationScore"] == owner["summary"]["recommendationScore"] == 100
    assert detail["requirements"][0]["scoring"]["matches"][0]["recordId"] == "skill_test"
    share(signed, [])
    encoder.calls.clear()
    for path, schema in [(url, "TalentMatchPage"), (shortlist, "TalentMatchPage"),
                          (f"{url}/{saved['talentId']}", "TeamMatch")]:
        data = checked(team.get(path), schema)
        summary = data.get("summary") or data["items"][0]["summary"]
        assert summary["recommendationScore"] == 0
        assert "Bioengineering" not in str(data)
    assert encoder.calls == []
    client, csrf = signed
    current = checked(client.get('/api/v1/me/profile'), 'Profile')
    content = current['content']
    content['skills'][0]['title'] = 'Changed skill'
    checked(client.put('/api/v1/me/profile', headers=headers(csrf),
                       json={'expectedRevision':current['revision'],'content':content}), 'Profile')
    assert client.get(f"{MATCHES}/{published['id']}").status_code == 409
    assert checked(team.get(url), "TalentMatchPage")["total"] == 0


def test_real_chinese_synonyms_and_distinct_meanings_through_http(application_model, app, signed, research_team):
    app.config['SEMANTIC_MATCHING_ENABLED'] = True
    saved = profile(signed, text='')
    content = saved['content']
    content['skills'] = [{'id':'skill_bio','title':'生物科技研究','evidenceText':''}]
    confirm_profile(signed, content)
    related = opportunity(research_team, requirements=[requirement('SKILL', '生物技术研究')])
    unrelated = opportunity(research_team, requirements=[requirement('SKILL', '法国文学研究')])
    detail = checked(signed[0].get(f"{MATCHES}/{related['id']}"), 'OwnerMatch')
    row = detail['requirements'][0]
    assert 75 < row['scoring']['score'] < 100
    assert row['scoring']['method'] == 'SEMANTIC'
    assert row['scoring']['matches'][0]['text'] == '生物科技研究'
    other = checked(signed[0].get(f"{MATCHES}/{unrelated['id']}"), 'OwnerMatch')
    assert other['requirements'][0]['scoring']['score'] == 0
    page = checked(signed[0].get(RECOMMENDATIONS + '?pageSize=1'), 'RecommendationPage')
    assert page['items'][0]['opportunity']['id'] == related['id']
    assert page['items'][0]['summary'] == detail['summary']
    runtime=app.extensions['semantic_matching']
    vectors=runtime.encode(['生物科技研究','生物技术研究','生物经济研究'])
    assert not all(math.isclose(a,b,abs_tol=1e-7) for a,b in zip(vectors[0],vectors[2]))
    assert runtime.encode(['生物科技研究'])[0] == vectors[0]
