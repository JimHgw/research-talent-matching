"""Explicit transactions for MySQL and legacy file-backed SQLite databases."""

from contextlib import contextmanager
from pathlib import Path

from flask import current_app
from sqlalchemy import create_engine, event, select
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from .models import Base, DatabaseWriteLock
from ..shared.paths import ROOT


WRITE_LOCK = "h18_write_lock"


def database():
    return current_app.extensions["database"]


def require_write_lock(db):
    """Guard revision comparisons: they must read state only after the writer lock is held.

    ``Database.transaction(write=True)`` takes that lock before any application read
    (SQLite ``BEGIN IMMEDIATE``; MySQL ``database_write_lock ... FOR UPDATE``). A
    comparison made in a read transaction could pass against a stale revision and
    lose a concurrent update, so it is rejected as a programming error.
    """
    if not db.info.get(WRITE_LOCK):
        raise RuntimeError("Revision checks require database().transaction(write=True).")


class Database:
    def __init__(self, url):
        parsed = make_url(url)
        if parsed.drivername == "mysql+pymysql":
            if not parsed.host or not parsed.database or not parsed.username:
                raise ValueError("MySQL DATABASE_URL must include a host, database and user.")
            self.engine = create_engine(
                parsed.update_query_dict({"charset": "utf8mb4"}), hide_parameters=True,
                pool_pre_ping=True, pool_recycle=1800, isolation_level="REPEATABLE READ",
                connect_args={"connect_timeout": 10},
            )
            return
        if parsed.drivername not in ("sqlite", "sqlite+pysqlite") or parsed.database in (
            None, "", ":memory:"
        ) or parsed.query:
            raise ValueError("DATABASE_URL must use mysql+pymysql or a file-backed SQLite database without URI options.")
        path = Path(parsed.database)
        if not path.is_absolute():
            path = ROOT / path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(parsed.set(database=str(path)), hide_parameters=True,
                                    connect_args={"timeout": 5, "check_same_thread": False})

        @event.listens_for(self.engine, "connect")
        def connect(connection, _):
            connection.isolation_level = None
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys = ON")
            cursor.close()

        @event.listens_for(self.engine, "begin")
        def begin(connection):
            connection.exec_driver_sql(
                "BEGIN IMMEDIATE" if connection.get_execution_options().get("sqlite_write") else "BEGIN"
            )

    def initialise(self):
        # Initialisation only: existing installations need explicit schema migrations.
        Base.metadata.create_all(self.engine)
        if self.engine.dialect.name == "mysql":
            with self.engine.begin() as connection:
                statement = mysql_insert(DatabaseWriteLock).values(id=1)
                connection.execute(statement.on_duplicate_key_update(id=1))

    @contextmanager
    def transaction(self, *, write=False):
        with self.engine.connect().execution_options(sqlite_write=write) as connection:
            with Session(connection, expire_on_commit=False) as session:
                with session.begin():
                    if write and self.engine.dialect.name == "mysql":
                        # Existing operations check revisions, quotas and leases before writing.
                        # Lock before any application read to preserve their SQLite semantics
                        # across API processes and document workers. Released on commit/rollback.
                        session.execute(select(DatabaseWriteLock.id).where(
                            DatabaseWriteLock.id == 1).with_for_update()).scalar_one()
                    session.info[WRITE_LOCK] = write
                    yield session
