"""One release sequence and read-only schema checks for API and worker readiness."""

from contextlib import contextmanager
from hashlib import sha256

import click
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import SQLAlchemyError

from .academic_upgrade import KINDS, kind_values
from .models import Base, DatabaseWriteLock, Opportunity
from .query_upgrade import QUERY_INDEXES


@contextmanager
def upgrade_lock(database):
    # Keep this connection alive across independently committed MySQL DDL.
    with database.engine.connect() as connection:
        mysql = connection.dialect.name == "mysql"
        name = "release_" + sha256(str(connection.engine.url.database).encode()).hexdigest()[:48]
        if mysql and connection.scalar(text("SELECT GET_LOCK(:name, 60)"), {"name": name}) != 1:
            raise ValueError("Could not acquire the database release lock.")
        try:
            yield
        finally:
            if mysql:
                connection.execute(text("SELECT RELEASE_LOCK(:name)"), {"name": name})


def check_schema(database):
    """Fail closed on missing structures and incompatible supported upgrade targets."""
    with database.engine.connect() as connection:
        inspector = inspect(connection)
        tables = set(inspector.get_table_names())
        for table in Base.metadata.sorted_tables:
            if table.name not in tables:
                raise ValueError(f"Missing table {table.name}; run prepare-db before starting services.")
            columns = {c["name"]: c for c in inspector.get_columns(table.name)}
            if set(table.c.keys()) - columns.keys():
                raise ValueError(f"Missing columns in {table.name}; run prepare-db before starting services.")
        indexes = {i["name"]: i for i in inspector.get_indexes("opportunities")}
        for expected in Opportunity.__table__.indexes:
            if expected.name in QUERY_INDEXES:
                actual = indexes.get(expected.name)
                if not actual or actual["column_names"] != [c.name for c in expected.columns] or actual["unique"]:
                    raise ValueError("Opportunity query indexes are incompatible; run prepare-db or review the schema.")
        if connection.dialect.name == "mysql":
            resume = connection.execute(text("""
                SELECT DATA_TYPE, CHARACTER_SET_NAME, IS_NULLABLE
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'profile_text_details'
                  AND COLUMN_NAME = 'resume_description'
            """)).mappings().one()
            if (resume["DATA_TYPE"] not in ("mediumtext", "longtext")
                    or resume["CHARACTER_SET_NAME"] != "utf8mb4" or resume["IS_NULLABLE"] != "NO"):
                raise ValueError("Resume storage is incompatible; run prepare-db or review the schema.")
            columns = {c["name"]: c for c in inspector.get_columns("opportunity_requirements")}
            if ((getattr(columns["kind"]["type"], "length", 0) or 0) < 32
                    or columns["kind"]["nullable"]
                    or str(columns["criteria"]["type"]).upper() != "JSON"
                    or not columns["criteria"]["nullable"]):
                raise ValueError("Academic requirement columns are incompatible.")
            checks = [c for c in inspector.get_check_constraints("opportunity_requirements")
                      if "kind" in c["sqltext"].lower()]
            if len(checks) != 1 or kind_values(checks[0]["sqltext"]) != set(KINDS):
                raise ValueError("Academic requirement constraint is incompatible.")
            if connection.scalar(select(DatabaseWriteLock.id)) != 1:
                raise ValueError("Database writer lock is missing; run prepare-db.")


def register_release_commands(app):
    @app.cli.command("check-schema")
    def check():
        """Read-only release preflight; never repairs or seeds a database."""
        try:
            check_schema(app.extensions["database"])
        except (ValueError, SQLAlchemyError) as error:
            raise click.ClickException(str(error) if isinstance(error, ValueError)
                                       else "Database schema check failed; review connectivity and schema.") from None
        click.echo("Database schema is compatible.")

    @app.cli.command("prepare-db")
    @click.pass_context
    def prepare(context):
        """Create missing tables, explicitly upgrade existing tables, seed and verify."""
        try:
            with upgrade_lock(app.extensions["database"]):
                for name, options in (
                    ("init-db", {}), ("upgrade-opportunity-search", {}),
                    ("upgrade-query-indexes", {}),
                    ("upgrade-academic-requirements", {"if_mysql": True}),
                    ("upgrade-resume-text", {}), ("seed-tags", {}), ("check-schema", {}),
                ):
                    click.echo(f"Database release step: {name}")
                    context.invoke(app.cli.commands[name], **options)
        except (ValueError, SQLAlchemyError) as error:
            raise click.ClickException(str(error) if isinstance(error, ValueError)
                                       else "Database preparation failed; services must remain stopped. Review the failed step and restore or retry.") from None
