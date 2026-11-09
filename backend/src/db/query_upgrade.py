"""Add the measured BE-8 list indexes to existing databases, without data edits."""

from hashlib import sha256

from sqlalchemy import inspect, text

from .models import Opportunity

QUERY_INDEXES = {"ix_opportunities_owner_page", "ix_opportunities_active_page"}


def upgrade_query_indexes(database):
    engine = database.engine
    mysql = engine.dialect.name == "mysql"
    lock = "be8_" + sha256(str(engine.url.database).encode()).hexdigest()[:48]
    with engine.connect().execution_options(sqlite_write=True) as connection, connection.begin():
        if mysql and connection.scalar(text("SELECT GET_LOCK(:name, 60)"), {"name": lock}) != 1:
            raise ValueError("Could not acquire the query index upgrade lock.")
        try:
            inspector = inspect(connection)
            if not inspector.has_table("opportunities"):
                raise ValueError("Run init-db and upgrade-opportunity-search before upgrading query indexes.")
            columns = {column["name"] for column in inspector.get_columns("opportunities")}
            if "expired_at" not in columns:
                raise ValueError("Run upgrade-opportunity-search before upgrading query indexes.")
            existing = {index["name"] for index in inspector.get_indexes("opportunities")}
            changed = False
            for index in sorted(Opportunity.__table__.indexes, key=lambda value: value.name):
                if index.name in QUERY_INDEXES and index.name not in existing:
                    # MySQL CREATE INDEX commits independently; a retry adds only
                    # missing indexes. No transaction rollback of DDL is assumed.
                    index.create(connection)
                    changed = True
            return changed
        finally:
            if mysql:
                connection.execute(text("SELECT RELEASE_LOCK(:name)"), {"name": lock})
