"""Idempotent, additive upgrade for pre-US-14 opportunity tables."""

from hashlib import sha256

from sqlalchemy import inspect, text


def upgrade_opportunity_search(database):
    engine = database.engine
    mysql = engine.dialect.name == "mysql"
    # API and document-worker entrypoints can start together. Serialize DDL even
    # on MySQL, where ALTER TABLE implicitly commits ordinary transactions.
    lock = "us14_" + sha256(str(engine.url.database).encode()).hexdigest()[:48]
    with engine.connect().execution_options(sqlite_write=True) as connection, connection.begin():
        if mysql and connection.scalar(text("SELECT GET_LOCK(:name, 60)"), {"name": lock}) != 1:
            raise ValueError("Could not acquire the opportunity schema upgrade lock.")
        try:
            inspector = inspect(connection)
            if not inspector.has_table("opportunities"):
                raise ValueError("Run init-db before upgrading opportunity search storage.")
            columns = {column["name"] for column in inspector.get_columns("opportunities")}
            timestamp = "DATETIME(6)" if mysql else "DATETIME"
            additions = {"opportunity_type": "VARCHAR(32)", "deadline_at": timestamp, "expired_at": timestamp}
            changed = False
            for name, kind in additions.items():
                if name not in columns:
                    # Identifiers/types are fixed constants. Existing rows receive NULL.
                    connection.exec_driver_sql(f"ALTER TABLE opportunities ADD COLUMN {name} {kind} NULL")
                    changed = True
            return changed
        finally:
            if mysql:
                connection.execute(text("SELECT RELEASE_LOCK(:name)"), {"name": lock})
