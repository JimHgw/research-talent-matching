"""One explicit transaction per operation, with SQLite writer serialization."""

from contextlib import contextmanager
from pathlib import Path

from flask import current_app
from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from .models import Base
from ..shared.paths import ROOT


def database():
    return current_app.extensions["database"]


class Database:
    def __init__(self, url):
        parsed = make_url(url)
        if parsed.drivername not in ("sqlite", "sqlite+pysqlite") or parsed.database in (
            None, "", ":memory:"
        ) or parsed.query:
            raise ValueError("DATABASE_URL must name a file-backed SQLite database without URI options.")
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

    @contextmanager
    def transaction(self, *, write=False):
        with self.engine.connect().execution_options(sqlite_write=write) as connection:
            with Session(connection, expire_on_commit=False) as session:
                with session.begin():
                    yield session
