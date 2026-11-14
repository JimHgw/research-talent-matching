"""Release gates, legacy preservation and real MySQL backup/recovery rehearsal."""

import json
import os
import secrets
import subprocess
import time
from datetime import datetime

import pytest
from sqlalchemy import MetaData, inspect, select, text

from backend.src.app import create_app
from backend.src.db.database import Database
from backend.src.db.migration import migrate_sqlite
from backend.src.db.models import (PrivacySettings, PrivacyVisibleField, ProfileOrigin,
    ProfileTextDetails, TalentProfile, Opportunity, PersonalInterestTag,
    ProfilePersonalInterest)
from backend.src.shared.paths import ROOT
from backend.tests.conftest import sign_in
from backend.tests.test_mysql import sqlite_source


def prepare(app):
    result = app.test_cli_runner().invoke(args=["prepare-db"])
    assert result.exit_code == 0, result.output
    assert "Database schema is compatible" in result.output


def snapshot(database):
    metadata = MetaData()
    metadata.reflect(database.engine)
    with database.engine.connect() as connection:
        return {table.name: [dict(row) for row in connection.execute(
            select(table).order_by(*table.primary_key.columns)).mappings()]
            for table in metadata.sorted_tables}


def assert_preserved(before, after):
    for table, rows in before.items():
        assert len(rows) == len(after[table]), table
        for old, new in zip(rows, after[table]):
            assert old == {key: new[key] for key in old}, table


def structure(database):
    inspector = inspect(database.engine)
    return {name: {
        "columns": [(c["name"], str(c["type"]), c["nullable"], c["default"])
                    for c in inspector.get_columns(name)],
        "indexes": sorted(inspector.get_indexes(name), key=lambda i: i["name"]),
        "checks": sorted(inspector.get_check_constraints(name), key=lambda c: c["name"] or ""),
        "unique": sorted(inspector.get_unique_constraints(name), key=lambda c: c["name"] or ""),
    } for name in inspector.get_table_names()}


@pytest.mark.parametrize("step", ["init-db", "upgrade-opportunity-search", "upgrade-query-indexes",
    "upgrade-academic-requirements", "upgrade-resume-text", "seed-tags", "check-schema"])
def test_release_sequence_stops_at_failed_step(app, monkeypatch, step):
    import click
    executed = []
    order = ["init-db", "upgrade-opportunity-search", "upgrade-query-indexes",
             "upgrade-academic-requirements", "upgrade-resume-text", "seed-tags", "check-schema"]
    for name in order:
        def callback(name=name, **kwargs):
            executed.append(name)
            if name == step:
                raise click.ClickException("Injected release failure")
        monkeypatch.setattr(app.cli.commands[name], "callback", callback)
    result = app.test_cli_runner().invoke(args=["prepare-db"])
    assert result.exit_code != 0 and "Injected release failure" in result.output
    assert executed == order[:order.index(step) + 1]


def test_missing_schema_blocks_health_and_native_worker(app):
    database = app.extensions["database"]
    with database.engine.begin() as connection:
        connection.exec_driver_sql("DROP INDEX ix_opportunities_active_page" +
                                   (" ON opportunities" if connection.dialect.name == "mysql" else ""))
    try:
        assert app.test_client().get("/healthz").status_code == 503
        result = app.test_cli_runner().invoke(args=["process-documents", "--once"])
        assert result.exit_code != 0 and "Worker schema is incompatible" in result.output
    finally:
        prepare(app)
    assert app.test_client().get("/healthz").status_code == 200


@pytest.fixture
def release_mysql(request):
    if not request.config.getoption("--run-docker"):
        pytest.skip("Use --run-docker for the isolated MySQL 8.4 recovery rehearsal.")
    name = "be9-release-" + secrets.token_hex(6)
    password = secrets.token_hex(24)
    dbname = "be9_" + secrets.token_hex(6) + "_test"
    created = False
    database = None
    try:
        started = subprocess.run(["docker", "run", "--detach", "--name", name,
            "--tmpfs", "/var/lib/mysql", "-p", "127.0.0.1::3306",
            "-e", "MYSQL_ROOT_PASSWORD=" + password, "-e", "MYSQL_DATABASE=" + dbname,
            "mysql:8.4", "--character-set-server=utf8mb4", "--collation-server=utf8mb4_0900_bin"],
            capture_output=True, timeout=90)
        assert started.returncode == 0, "Could not start isolated MySQL 8.4 container"
        created = True
        port = subprocess.check_output(["docker", "port", name, "3306"], text=True).strip().rsplit(":", 1)[1]
        url = f"mysql+pymysql://root:{password}@127.0.0.1:{port}/{dbname}"
        database = Database(url)
        for attempt in range(90):
            try:
                with database.engine.connect() as connection:
                    assert connection.scalar(text("SELECT VERSION()")).startswith("8.4.")
                break
            except Exception:
                if attempt == 89:
                    pytest.fail("Isolated MySQL readiness timed out")
                time.sleep(1)
        def mysql_tool(program, *args, input=None):
            # Credentials stay in the subprocess environment, never logs or reports.
            result = subprocess.run(["docker", "exec", "-i", "-e", "MYSQL_PWD", name,
                program, "-uroot", *args], env={**os.environ, "MYSQL_PWD": password},
                input=input, capture_output=True, timeout=90)
            assert result.returncode == 0, f"Isolated {program} operation failed"
            return result.stdout
        yield database, mysql_tool
    finally:
        if database:
            database.engine.dispose()
        if created:
            result = subprocess.run(["docker", "rm", "--force", "--volumes", name], capture_output=True, timeout=60)
            assert result.returncode == 0, "Could not remove isolated release container"


def test_mysql_fresh_legacy_repeat_unicode_and_restore(release_mysql, sqlite_source):
    database, mysql_tool = release_mysql
    url = database.engine.url
    config = {"TESTING": True, "DATABASE_URL": url, "COOKIE_SECURE": False,
              "SEMANTIC_MATCHING_ENABLED": False}
    app = create_app(config)
    try:
        prepare(app)
        assert app.test_client().get("/healthz").status_code == 200
        assert app.test_cli_runner().invoke(args=["process-documents", "--once"]).exit_code == 0
        # Empty fresh schema verified; copy a fictional existing-data fixture.
        from backend.tests.conftest import clear_mysql_data
        clear_mysql_data(database)
        source, _, user_id, timestamp = sqlite_source
        with source.transaction(write=True) as db:
            profile = db.scalar(select(TalentProfile).where(TalentProfile.user_id == user_id))
            talent_id = profile.talent_id
            profile.revision = profile.confirmed_revision = 7
            profile.confirmation_status = "CONFIRMED"
            profile.confirmed_at = timestamp
            profile.discipline_group = "STEM"
            profile.education = [{"id": "education_test", "institution": "大学 🧪",
                "qualification": "Bachelor of Computer Science", "discipline": "Computer Science",
                "startYear": 2023, "endYear": 2026}]
            privacy = db.get(PrivacySettings, talent_id)
            privacy.revision = 4
            privacy.discoverable = True
            db.add(PrivacyVisibleField(talent_id=talent_id, field="education"))
            db.add(ProfileOrigin(talent_id=talent_id, field="education", source_type="USER_REVIEWED_DOCUMENT", document_id="doc_test"))
            db.add(ProfileTextDetails(talent_id=talent_id, research_interest_text="中文研究 🧪", resume_description="旧简历 🧪"))
            db.add(PersonalInterestTag(id="personal_test", talent_id=talent_id, label="中文研究 🧪", normalised_label="中文研究 🧪"))
            db.flush()
            db.add(ProfilePersonalInterest(talent_id=talent_id, tag_id="personal_test", position=0))
            published = db.get(Opportunity, "opp_test")
            published.status = "PUBLISHED"
            db.add(Opportunity(id="opp_expired", owner_user_id="user_team", title="Expired research",
                university="UNSW", discipline_group="STEM", discipline="CS", research_area="AI",
                description="Fictional research", status="PUBLISHED", expired_at=datetime(2025, 1, 1)))
            from backend.src.db.models import User
            db.get(User, "user_team").password_hash = db.get(User, user_id).password_hash
            from backend.src.db.models import Document, DocumentProcessingLease
            db.add(Document(id="doc_processing", talent_id=talent_id, kind="CV", file_name="pending.docx",
                media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                storage_key="fictional-pending", status="PROCESSING", size_bytes=100))
            db.flush()
            db.add(DocumentProcessingLease(document_id="doc_processing", token="existing-lease",
                attempts=2, expires_at=datetime(2099, 1, 1)))
        migrate_sqlite(source.engine.url, database)
        # Populate the controlled vocabulary before the preservation snapshot.
        assert app.test_cli_runner().invoke(args=["seed-tags"]).exit_code == 0
        with database.engine.begin() as connection:
            connection.exec_driver_sql("ALTER TABLE profile_text_details MODIFY resume_description TEXT NOT NULL")
            connection.exec_driver_sql("ALTER TABLE opportunity_requirements DROP CHECK ck_opportunity_requirement_kind, DROP COLUMN criteria, MODIFY kind VARCHAR(16) NOT NULL, ADD CONSTRAINT ck_legacy_kind CHECK (kind IN ('SKILL', 'INTEREST'))")
            connection.exec_driver_sql("ALTER TABLE opportunities DROP INDEX ix_opportunities_owner_page, DROP INDEX ix_opportunities_active_page, DROP COLUMN source_url, DROP COLUMN opportunity_type")
            connection.exec_driver_sql("DROP TABLE personal_interest_tag_details")
        before = snapshot(database)
        backup = mysql_tool("mysqldump", "--single-transaction", "--skip-lock-tables", "--no-tablespaces",
                            "--set-gtid-purged=OFF", "--hex-blob", url.database)
        assert backup
        assert app.test_client().get("/healthz").status_code == 503
        prepare(app)
        upgraded = snapshot(database)
        assert_preserved(before, upgraded)
        assert all(row["criteria"] is None for row in upgraded["opportunity_requirements"])
        assert all(row["source_url"] is None and row["opportunity_type"] is None for row in upgraded["opportunities"])
        assert upgraded["personal_interest_tag_details"] == []
        upgraded_structure = structure(database)
        prepare(app)
        assert snapshot(database) == upgraded
        assert structure(database) == upgraded_structure
        # Read the application contract's boundary, rather than defining a new limit.
        schema = json.loads((ROOT / "docs/api/openapi.json").read_text(encoding="utf-8"))
        limits = [value["properties"]["resumeDescription"]["maxLength"]
                  for value in schema["components"]["schemas"].values()
                  if "resumeDescription" in value.get("properties", {})
                  and "maxLength" in value["properties"]["resumeDescription"]]
        assert limits and len(set(limits)) == 1
        resume = "中文" + "🧪" * (limits[0] - 2)
        with database.transaction(write=True) as db:
            db.get(ProfileTextDetails, talent_id).resume_description = resume
        boundary = snapshot(database)
        prepare(app)
        app.extensions["database"].engine.dispose()
        restarted = create_app(config)
        try:
            assert snapshot(restarted.extensions["database"]) == boundary
            assert restarted.test_client().get("/healthz").status_code == 200
            assert restarted.test_cli_runner().invoke(args=["process-documents", "--once"]).exit_code == 0
            for email, role in (("migrated@example.test", "TALENT"), ("team-source@example.test", "RESEARCH_TEAM")):
                client = restarted.test_client()
                sign_in(client, email)
                assert client.get("/api/v1/auth/session").json["user"]["role"] == role
                if role == "TALENT":
                    response = client.get("/api/v1/me/profile")
                    assert response.status_code == 200
                    from backend.src.shared.validation import validator
                    validator("Profile").validate(response.json)
                    assert response.json["revision"] == 7
                    assert response.json["content"]["resumeDescription"] == resume
        finally:
            restarted.extensions["database"].engine.dispose()
        # Real incompatible DDL: preparation fails, neither readiness nor worker can pass.
        with database.engine.begin() as connection:
            connection.exec_driver_sql("ALTER TABLE opportunity_requirements MODIFY criteria VARCHAR(40) NULL")
        failed = app.test_cli_runner().invoke(args=["prepare-db"])
        assert failed.exit_code != 0 and "Unsupported existing criteria" in failed.output
        assert app.test_client().get("/healthz").status_code == 503
        assert app.test_cli_runner().invoke(args=["process-documents", "--once"]).exit_code != 0
        # Restore into a separate empty database, never overwrite the original.
        restored_name = url.database.removesuffix("_test") + "_restore_test"
        mysql_tool("mysql", "-e", f"CREATE DATABASE `{restored_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin")
        mysql_tool("mysql", restored_name, input=backup)
        restored = create_app({**config, "DATABASE_URL": url.set(database=restored_name)})
        try:
            assert snapshot(restored.extensions["database"]) == before
            prepare(restored)
            assert snapshot(restored.extensions["database"]) == upgraded
            sign_in(restored.test_client(), "migrated@example.test")
            assert restored.test_client().get("/healthz").status_code == 200
        finally:
            restored.extensions["database"].engine.dispose()
    finally:
        app.extensions["database"].engine.dispose()
