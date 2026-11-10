"""Deterministic BE-8 data shared by equivalence tests and the HTTP benchmark."""

import json
from datetime import datetime, timedelta

from sqlalchemy import insert

from backend.src.db.models import (AuthSession, Opportunity, OpportunityRequirement,
    OpportunitySkillDetails, PrivacySettings, PrivacyVisibleField, ProfileInterest,
    ProfileSkill, ProfileSkillDetails, ProfileTextDetails, RequirementTag, Tag,
    TalentProfile, User)
from backend.src.features.profile.routes import seed_tags
from backend.src.shared.paths import ROOT
from backend.src.shared.security import COOKIE, digest

MANIFEST = json.loads((ROOT / "backend/tests/data/sprint3/be8-query.json").read_text(encoding="utf-8"))
NOW = datetime.fromisoformat(MANIFEST["referenceTime"])
TEAM = "be8_team"
OWNER = "be8_owner"
TARGET = "opp_be8_000004"
FIELDS = ("displayName", "disciplineGroup", "education", "courses", "researchExperience",
          "researchOutputs", "skills", "researchInterests")


def seed_dataset(app, size):
    """Use only a caller-created disposable database; never reset existing data."""
    database = app.extensions["database"]
    with app.app_context():
        seed_tags(json.loads((ROOT / "docs/api/examples/tags.json").read_text())["items"])
    users = [dict(id=TEAM, email="be8-team@example.test", display_name="BE8 team",
                  password_hash="!benchmark-only", role="RESEARCH_TEAM", active=True),
             dict(id=OWNER, email="be8-owner@example.test", display_name="BE8 owner",
                  password_hash="!benchmark-only", role="TALENT", active=True)]
    profiles, privacy, visibility, skills, legacy_skills, interests, texts = [], [], [], [], [], [], []
    education = [{"id": "edu", "institution": "The University of New South Wales",
                  "qualification": "Master of IT", "discipline": "Computer Science",
                  "startYear": 2025, "endYear": 2027}]
    for index in range(-1, size):
        owner = index == -1
        key = "be8_owner_profile" if owner else f"talent_be8_{index:06d}"
        user_id = OWNER if owner else f"user_be8_{index:06d}"
        state = index % 10
        if not owner:
            users.append(dict(id=user_id, email=f"be8-{index}@example.test", display_name="Candidate",
                              password_hash="!benchmark-only", role="RESEARCH_TEAM" if state == 3 else "TALENT",
                              active=state != 2))
        confirmed = owner or state != 1
        profiles.append(dict(talent_id=key, user_id=user_id, display_name=f"Candidate {index:06d}",
            discipline_group="STEM", education=education,
            courses=[{"id": "course", "name": "Data science", "code": "COMP", "description": "Synthetic course. " * 20}],
            research_experience=[{"id": "exp", "title": "Biotechnology", "organisation": "UNSW",
                                  "description": "Synthetic project. " * 20}],
            research_outputs=[{"id": "output", "title": "Data analysis", "type": "PUBLICATION",
                               "url": None, "description": "Synthetic output. " * 20}],
            revision=1, confirmation_status="CONFIRMED" if confirmed else "UNCONFIRMED",
            confirmed_revision=1 if confirmed else None, confirmed_at=NOW if confirmed else None,
            updated_at=NOW))
        privacy.append(dict(talent_id=key, revision=0, discoverable=not owner and state != 0))
        shared = [] if state == 4 else [f for f in FIELDS if state != 5 or f != "skills"]
        visibility.extend(dict(talent_id=key, field=f) for f in shared)
        records = [{"id": "python", "title": "No Python" if index % 4 == 0 else "Python",
                    "evidenceText": "" if index % 4 == 0 else "Used Python in research."},
                   {"id": "bio", "title": "生物科技研究", "evidenceText": "研究经验"}]
        if not owner and index % 7 == 0:
            legacy_skills.append(dict(talent_id=key, tag_id="skill_python", claim="HAS",
                                      evidence_text="Used Python in research.", position=0))
        else:
            skills.append(dict(talent_id=key, skills=records))
        interests.append(dict(talent_id=key, tag_id="interest_ml" if owner or index % 3 else "interest_health", position=0))
        texts.append(dict(talent_id=key, research_interest_text="生物科技研究", resume_description="PRIVATE resume. " * 100))
    opportunities, requirements, tags, titles = [], [], [], []
    for index in range(size):
        key, state = f"opp_be8_{index:06d}", index % 10
        deadline = NOW - timedelta(microseconds=1) if state == 1 else NOW if state == 3 else NOW + timedelta(days=30)
        if state >= 4 and index % 7 == 0:
            deadline = None  # Legacy optional field.
        opportunities.append(dict(id=key, owner_user_id=TEAM if index % 2 == 0 else OWNER,
            revision=1, status="DRAFT" if state == 0 else "PUBLISHED",
            title=["生物技术研究", "Straße Café", "ＡＩ 研究 %_'", "Data science"][index % 4],
            university="  UNSW\u00a0 Sydney " if index % 2 == 0 else "USYD",
            discipline_group="BUSINESS" if index % 3 == 0 else "STEM",
            discipline="Computer Science", research_area="研究 数据", description="Synthetic research. " * 30,
            opportunity_type=None if index % 9 == 0 else "PHD" if index % 2 == 0 else "MASTERS",
            source_url=None, deadline_at=deadline, expired_at=NOW if state == 2 else None,
            created_at=NOW, updated_at=NOW - timedelta(seconds=index // 4)))
        for position, kind in enumerate(("SKILL", "INTEREST")):
            req = f"req_{position}"
            requirements.append(dict(opportunity_id=key, id=req, label="生物技术研究" if position else "Python",
                                     kind=kind, importance="PREFERRED" if position else "REQUIRED", position=position))
            if position == 0:
                titles.append(dict(opportunity_id=key, requirement_id=req,
                                   titles=["生物技术研究" if index % 4 == 0 else "Python"]))
            else:
                tags.append(dict(opportunity_id=key, requirement_id=req, tag_id="interest_ml", position=0))
    with database.transaction(write=True) as db:
        # A shared tag used by this fixture but absent in some older tag catalogues.
        if db.get(Tag, "interest_health") is None:
            db.add(Tag(id="interest_health", label="Health", kind="INTEREST"))
            db.flush()
        for model, rows in ((User, users), (TalentProfile, profiles), (PrivacySettings, privacy),
                            (PrivacyVisibleField, visibility), (ProfileSkillDetails, skills),
                            (ProfileSkill, legacy_skills), (ProfileInterest, interests), (ProfileTextDetails, texts),
                            (Opportunity, opportunities), (OpportunityRequirement, requirements),
                            (OpportunitySkillDetails, titles), (RequirementTag, tags)):
            if rows:
                db.execute(insert(model), rows)
        for user_id in (TEAM, OWNER):
            db.add(AuthSession(token_hash=digest("token-" + user_id), user_id=user_id,
                               csrf_token="benchmark-csrf", created_at=NOW, expires_at=datetime(2099, 1, 1)))


def authenticated_client(app, user_id):
    client = app.test_client()
    client.set_cookie(COOKIE, "token-" + user_id)
    return client
