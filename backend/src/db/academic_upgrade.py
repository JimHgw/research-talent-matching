"""Explicit, repeatable upgrade of existing US-18 MySQL requirements."""

import re
from hashlib import sha256

from sqlalchemy import JSON, VARCHAR, Column, inspect, text
from sqlalchemy.schema import CreateColumn


TABLE = "opportunity_requirements"

OLD_KINDS = {"SKILL", "INTEREST"}

KINDS = (
    "SKILL",
    "INTEREST",
    "EDUCATION",
    "RESEARCH_EXPERIENCE",
    "RESEARCH_OUTPUT",
)

def kind_values(sql):
    # MySQL may include charset introducers in reflected CHECK expressions.
    expression = re.sub(
        r"(?<![\w'])_[a-zA-Z0-9]+(?=')",
        "",
        sql,
    )
    expression = re.sub(r"[\s`()]", "", expression)

    if not re.fullmatch(
        r"kindin'[A-Z_]+'(?:,'[A-Z_]+')*",
        expression,
        flags=re.IGNORECASE,
    ):
        raise ValueError(
            "Unrecognised kind constraint; review the schema before upgrading."
        )

    values = set(re.findall(r"'([A-Z_]+)'", expression))

    if values not in (OLD_KINDS, set(KINDS)):
        raise ValueError(
            "Unrecognised allowed requirement types; review before upgrading."
        )

    return values


def upgrade_academic_requirements(database):
    engine = database.engine

    if engine.dialect.name != "mysql":
        raise ValueError("This upgrade command targets existing MySQL databases.")

    lock = "us18_" + sha256(
        str(engine.url.database).encode()
    ).hexdigest()[:48]

    with engine.connect() as connection, connection.begin():
        acquired = connection.scalar(
            text("SELECT GET_LOCK(:name, 60)"),
            {"name": lock},
        )

        if acquired != 1:
            raise ValueError("Could not acquire the US-18 schema upgrade lock.")

        try:
            inspector = inspect(connection)

            if not inspector.has_table(TABLE):
                raise ValueError("Run init-db before upgrading requirements.")

            columns = {
                column["name"]: column
                for column in inspector.get_columns(TABLE)
            }

            kind = columns["kind"]

            if (
                not isinstance(kind["type"], VARCHAR)
                or kind["type"].length is None
                or kind["nullable"]
                or kind.get("default") is not None
            ):
                raise ValueError("Unsupported existing kind column definition.")

            criteria = columns.get("criteria")

            if criteria is not None and (
                not isinstance(criteria["type"], JSON)
                or not criteria["nullable"]
                or criteria.get("default") is not None
            ):
                raise ValueError("Unsupported existing criteria column definition.")

            kind_checks = []

            for check in inspector.get_check_constraints(TABLE):
                sql = check["sqltext"]

                if re.search(r"\bkind\b", sql, flags=re.IGNORECASE):
                    values = kind_values(sql)

                    if not check["name"]:
                        raise ValueError("The kind constraint has no usable name.")

                    kind_checks.append((check["name"], values))

            widen_kind = kind["type"].length < 32

            replace_check = (
                widen_kind
                or len(kind_checks) != 1
                or kind_checks[0][1] != set(KINDS)
            )

            changes = []
            quote = engine.dialect.identifier_preparer.quote

            if replace_check:
                for name, _ in kind_checks:
                    changes.append(f"DROP CHECK {quote(name)}")

            if criteria is None:
                changes.append("ADD COLUMN criteria JSON NULL")

            if widen_kind:
                # Preserve reflected charset/collation and column comment.
                wider_type = kind["type"].copy()
                wider_type.length = 32

                definition = str(
                    CreateColumn(
                        Column(
                            "kind",
                            wider_type,
                            nullable=False,
                            comment=kind.get("comment"),
                        )
                    ).compile(dialect=engine.dialect)
                )

                changes.append(f"MODIFY COLUMN {definition}")

            if replace_check:
                values = ", ".join(f"'{value}'" for value in KINDS)

                changes.append(
                    "ADD CONSTRAINT ck_opportunity_requirement_kind "
                    f"CHECK (kind IN ({values}))"
                )

            if not changes:
                return False

            # One MySQL ALTER, rather than separately committed upgrade steps.
            connection.exec_driver_sql(
                f"ALTER TABLE {quote(TABLE)} " + ", ".join(changes)
            )

            return True

        finally:
            connection.execute(
                text("SELECT RELEASE_LOCK(:name)"),
                {"name": lock},
            )
