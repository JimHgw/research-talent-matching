"""Offline, non-destructive copy from SQLite into an empty MySQL schema."""

import hashlib
import json
from pathlib import Path

import click
from sqlalchemy import func, inspect, select
from sqlalchemy.exc import SQLAlchemyError

from .database import Database
from .models import Base, DatabaseWriteLock


def _checksum(rows):
    digest = hashlib.sha256()
    count = 0
    for row in rows:
        payload = json.dumps(dict(row._mapping), ensure_ascii=False, sort_keys=True,
                             separators=(",", ":"), default=str).encode("utf-8")
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
        count += 1
    return count, digest.digest()


def migrate_sqlite(source_url, target):
    """Preserve IDs, hashes, JSON, timestamps and FKs; rollback all rows on failure."""
    if target.engine.dialect.name != "mysql":
        raise ValueError("The migration destination must be MySQL.")
    source = Database(source_url)
    try:
        if source.engine.dialect.name != "sqlite":
            raise ValueError("The migration source must be a file-backed SQLite database.")
        if not Path(source.engine.url.database).is_file():
            raise ValueError("The source SQLite file does not exist.")
        with source.engine.connect() as old, old.begin():
            inspector = inspect(old)
            available = set(inspector.get_table_names())
            if "users" not in available:
                raise ValueError("The source is not a project database (users table is missing).")
            tables = [table for table in Base.metadata.sorted_tables
                      if table.name != DatabaseWriteLock.__tablename__]
            for table in tables:
                if table.name in available:
                    columns = {column["name"] for column in inspector.get_columns(table.name)}
                    if columns != set(table.c.keys()):
                        raise ValueError(f"Source schema differs for {table.name}; upgrade SQLite first.")
            unknown = available - set(Base.metadata.tables) - {"sqlite_sequence"}
            if unknown:
                raise ValueError("Unrecognised source tables: " + ", ".join(sorted(unknown)))

            # MySQL DDL commits separately. All subsequent data writes share one transaction.
            target.initialise()
            counts = {}
            with target.transaction(write=True) as new:
                for table in tables:
                    if new.scalar(select(func.count()).select_from(table)):
                        raise ValueError("Destination is not empty; use a fresh MySQL database. Nothing was copied.")
                for table in tables:
                    if table.name not in available:
                        counts[table.name] = 0
                        continue
                    query = select(table).order_by(*table.primary_key.columns)
                    rows = old.execute(query)
                    for batch in rows.mappings().partitions(500):
                        new.execute(table.insert(), [dict(row) for row in batch])
                    before = _checksum(old.execute(query))
                    after = _checksum(new.execute(query))
                    if before != after:
                        raise ValueError(f"Verification failed for {table.name}; migration rolled back.")
                    counts[table.name] = before[0]
            return counts
    finally:
        source.engine.dispose()


def register_migration_command(app):
    @app.cli.command("upgrade-resume-text")
    def upgrade_resume():
        """Widen legacy MySQL resume storage; run before starting API/worker writes."""
        from .schema_upgrades import upgrade_resume_text
        try:
            changed = upgrade_resume_text(app.extensions["database"])
        except (ValueError, SQLAlchemyError) as error:
            message = str(error) if isinstance(error, ValueError) else "Resume storage upgrade failed; check the schema and database connection."
            raise click.ClickException(message) from None
        click.echo("Resume text storage widened to MEDIUMTEXT." if changed else "Resume text storage is already sufficient.")

    @app.cli.command("migrate-sqlite")
    @click.option("--source", required=True, help="Existing SQLite URL, e.g. sqlite:////app/data/h18abanana.db")
    def migrate(source):
        """Copy and verify SQLite data. Stop API/worker writes before running."""
        try:
            counts = migrate_sqlite(source, app.extensions["database"])
        except (ValueError, SQLAlchemyError) as error:
            # Driver messages may include row values; never echo them or credentials.
            message = str(error) if isinstance(error, ValueError) else (
                "Database operation failed; copied rows were rolled back. "
                "Check schema, connectivity and source values."
            )
            raise click.ClickException(message) from None
        for name, count in counts.items():
            click.echo(f"{name}: {count} rows verified")
        click.echo("Migration committed. SQLite was left unchanged. Copy/retain DOCUMENT_STORAGE_DIR separately.")

    @app.cli.command("upgrade-academic-requirements")
    @click.option("--if-mysql", is_flag=True,
                  help="Skip non-MySQL databases when running container startup.")
    def upgrade_academic(if_mysql):
        """Upgrade existing MySQL academic criteria before API/worker startup."""
        from .academic_upgrade import upgrade_academic_requirements

        database = app.extensions["database"]
        if if_mysql and database.engine.dialect.name != "mysql":
            click.echo("Academic requirement upgrade skipped for non-MySQL database.")
            return

        try:
            changed = upgrade_academic_requirements(
                database
            )
        except (ValueError, SQLAlchemyError) as error:
            message = (
                str(error)
                if isinstance(error, ValueError)
                else "Requirement storage upgrade failed."
            )
            raise click.ClickException(message) from None

        click.echo(
            "Academic requirement storage upgraded."
            if changed
            else "Academic requirement storage is current."
        )
