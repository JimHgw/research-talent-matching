"""MySQL schema portability and verified SQLite migration against a real server."""

from datetime import datetime, timedelta
import hashlib

import pytest
from sqlalchemy import String, event, func, select
from sqlalchemy.dialects.mysql import dialect
from sqlalchemy.exc import DataError
from sqlalchemy.schema import CreateTable

from backend.src.app import create_app
from backend.src.db.database import Database
from backend.src.db.migration import migrate_sqlite
from backend.src.db.models import (Base, Document, DocumentExtraction, LoginAttempt,
                                   Opportunity, OpportunityRequirement, ProfileSkill,
                                   RequirementTag, Tag, TalentProfile, User)
from backend.src.db.collections import SavedOpportunity, ShortlistedTalent
from backend.tests.conftest import PASSWORD, sign_in


def test_all_tables_compile_for_mysql_and_preserve_timestamp_precision():
    for table in Base.metadata.sorted_tables:
        ddl = str(CreateTable(table).compile(dialect=dialect()))
        assert "ENGINE=InnoDB" in ddl and "utf8mb4_0900_bin" in ddl
        for column in table.columns:
            if type(column.type) is String:
                assert column.type.length, f"{table.name}.{column.name} needs a VARCHAR length"
            if column.name.endswith("_at"):
                assert "DATETIME(6)" in ddl


def test_default_mysql_config_handles_password_url_characters(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("MYSQL_PASSWORD", "p@ss:/?#%中文")
    app = create_app()
    engine = app.extensions["database"].engine
    try:
        assert engine.url.drivername == "mysql+pymysql"
        assert engine.url.password == "p@ss:/?#%中文"
        assert engine.url.query["charset"] == "utf8mb4"
    finally:
        engine.dispose()


@pytest.mark.parametrize("url", ["mysql://user:pass@host/db", "mysql+pymysql://host/db",
                                  "sqlite:///:memory:", "postgresql://user:pass@host/db"])
def test_unsupported_database_urls_are_rejected(url):
    with pytest.raises(ValueError):
        Database(url)


@pytest.fixture
def mysql_target(app):
    target = app.extensions["database"]
    if target.engine.dialect.name != "mysql":
        pytest.skip("Use --run-mysql and a disposable MYSQL_TEST_DATABASE_URL.")
    Base.metadata.drop_all(target.engine)
    target.initialise()
    return target


@pytest.fixture
def sqlite_source(tmp_path):
    from backend.src.features.auth.routes import provision_user
    from backend.src.features.profile.routes import seed_tags
    path = tmp_path / "source.db"
    app = create_app({"TESTING": True, "DATABASE_URL": f"sqlite:///{path.as_posix()}",
                      "COOKIE_SECURE": False})
    source = app.extensions["database"]
    source.initialise()
    with app.app_context():
        seed_tags([{"id": "skill_test", "label": "研究 🧪", "kind": "SKILL", "disciplineGroups": ["STEM"]}])
        user_id = provision_user("migrated@example.test", PASSWORD, "研究员 🧪", "TALENT")
    timestamp = datetime(2026, 10, 20, 1, 2, 3, 123456)
    with source.transaction(write=True) as db:
        profile = db.scalar(select(TalentProfile).where(TalentProfile.user_id == user_id))
        profile.education = [{"institution": "大学 🧪", "extra": [None, True, "中文"]}]
        profile.updated_at = timestamp
        db.add(ProfileSkill(talent_id=profile.talent_id, tag_id="skill_test", claim="HAS",
                            evidence_text="研究" * 1000, position=0))
        db.add(LoginAttempt(id=123, email_hash="a" * 64, ip_hash="b" * 64, attempted_at=timestamp))
        db.add(Document(id="doc_test", talent_id=profile.talent_id, kind="CV", file_name="研究" * 200 + ".docx",
                        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        storage_key="private-doc-test", status="READY", size_bytes=100,
                        error=None, created_at=timestamp, updated_at=timestamp))
        db.flush()
        db.add(DocumentExtraction(document_id="doc_test", result={"text": "中文 🧪", "empty": None},
                                  created_at=timestamp))
        db.add(User(id="user_team", email="team-source@example.test", display_name="Team",
                    password_hash="unused", role="RESEARCH_TEAM"))
        db.flush()
        db.add(Opportunity(id="opp_test", owner_user_id="user_team", title="研究 🧪",
                           university="大学", discipline_group="STEM", discipline="Computing",
                           research_area="AI", description="研究" * 5000))
        db.flush()
        db.add(OpportunityRequirement(opportunity_id="opp_test", id="req_test", label="研究",
                                      kind="SKILL", importance="REQUIRED", position=0))
        db.flush()
        db.add(RequirementTag(opportunity_id="opp_test", requirement_id="req_test",
                              tag_id="skill_test", position=0))
        db.add(SavedOpportunity(user_id=user_id, opportunity_id="opp_test", created_at=timestamp))
        db.add(ShortlistedTalent(opportunity_id="opp_test", talent_id=profile.talent_id, created_at=timestamp))
    yield source, path, user_id, timestamp
    source.engine.dispose()


def test_migration_verifies_values_preserves_login_and_refuses_overwrite(mysql_target, sqlite_source, app):
    source, path, user_id, timestamp = sqlite_source
    original = hashlib.sha256(path.read_bytes()).digest()
    counts = migrate_sqlite(source.engine.url, mysql_target)
    assert counts["users"] == 2 and counts["documents"] == 1
    assert counts["saved_opportunities"] == counts["shortlisted_talent"] == 1
    assert counts["requirement_tags"] == 1
    assert hashlib.sha256(path.read_bytes()).digest() == original
    with mysql_target.transaction() as db:
        profile = db.scalar(select(TalentProfile).where(TalentProfile.user_id == user_id))
        assert profile.updated_at == timestamp
        assert profile.education[0]["extra"] == [None, True, "中文"]
        assert db.scalar(select(ProfileSkill.evidence_text)) == "研究" * 1000
        assert db.get(Document, "doc_test").error is None
        assert db.get(Document, "doc_test").file_name == "研究" * 200 + ".docx"
        assert db.get(DocumentExtraction, "doc_test").result == {"text": "中文 🧪", "empty": None}
    assert sign_in(app.test_client(), "migrated@example.test")
    with pytest.raises(ValueError, match="not empty"):
        migrate_sqlite(source.engine.url, mysql_target)
    with mysql_target.transaction(write=True) as db:
        attempt = LoginAttempt(email_hash="c" * 64, ip_hash="d" * 64,
                               attempted_at=timestamp + timedelta(seconds=1))
        db.add(attempt)
        db.flush()
        assert attempt.id > 123


def test_failed_migration_rolls_back_every_table(mysql_target, sqlite_source):
    source, _, _, _ = sqlite_source
    def fail(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO document_extractions"):
            raise RuntimeError("Injected late migration failure")
    event.listen(mysql_target.engine, "before_cursor_execute", fail)
    try:
        with pytest.raises(RuntimeError, match="Injected"):
            migrate_sqlite(source.engine.url, mysql_target)
    finally:
        event.remove(mysql_target.engine, "before_cursor_execute", fail)
    with mysql_target.transaction() as db:
        for table in Base.metadata.sorted_tables:
            if table.name != "database_write_lock":
                assert db.scalar(select(func.count()).select_from(table)) == 0
    # A retry after rollback remains possible and preserves all rows.
    assert migrate_sqlite(source.engine.url, mysql_target)["users"] == 2


def test_invalid_source_does_not_create_sqlite_file(mysql_target, tmp_path):
    path = tmp_path / "missing.db"
    with pytest.raises(ValueError, match="does not exist"):
        migrate_sqlite(f"sqlite:///{path.as_posix()}", mysql_target)
    assert not path.exists()


def test_mysql_enforces_lengths_and_case_sensitive_ids(mysql_target):
    with mysql_target.transaction(write=True) as db:
        db.add_all([Tag(id="Skill", label="A", kind="SKILL"), Tag(id="skill", label="B", kind="SKILL")])
    with mysql_target.transaction() as db:
        assert db.get(Tag, "Skill").label == "A"
        assert db.get(Tag, "skill").label == "B"
    with pytest.raises(DataError), mysql_target.transaction(write=True) as db:
        db.add(User(id="u", email="x" * 255, display_name="A", password_hash="hash", role="TALENT"))
