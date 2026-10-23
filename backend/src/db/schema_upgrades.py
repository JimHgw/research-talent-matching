"""Explicit, repeatable widening of existing MySQL resume-text storage."""

import re

from sqlalchemy import text


def upgrade_resume_text(database):
    if database.engine.dialect.name != "mysql":
        return False  # SQLite TEXT already accommodates the API character limit.
    with database.engine.connect() as connection:
        column = connection.execute(text("""
            SELECT DATA_TYPE, CHARACTER_SET_NAME, COLLATION_NAME, IS_NULLABLE,
                   COLUMN_DEFAULT, EXTRA
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'profile_text_details'
              AND COLUMN_NAME = 'resume_description'
        """)).mappings().one_or_none()
        if column is None:
            raise ValueError("Initialise the database before upgrading resume text storage.")
        if column["DATA_TYPE"] in ("mediumtext", "longtext"):
            return False
        collation = column["COLLATION_NAME"] or ""
        if (column["DATA_TYPE"] != "text" or column["CHARACTER_SET_NAME"] != "utf8mb4"
                or not re.fullmatch(r"utf8mb4_[a-z0-9_]+", collation)
                or column["IS_NULLABLE"] != "NO" or column["COLUMN_DEFAULT"] is not None or column["EXTRA"]):
            raise ValueError("Resume text column differs from the supported legacy schema; review it before upgrading.")
        # MySQL DDL commits independently. This only widens the existing column,
        # preserving its character set, collation, nullability and every stored value.
        connection.exec_driver_sql(
            "ALTER TABLE profile_text_details MODIFY COLUMN resume_description "
            f"MEDIUMTEXT CHARACTER SET utf8mb4 COLLATE {collation} NOT NULL")
    return True
