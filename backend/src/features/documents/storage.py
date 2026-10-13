"""Private storage for original uploaded documents."""

from pathlib import Path
from uuid import uuid4

from flask import current_app

from ...shared.paths import ROOT
from ...shared.validation import ApiError

def storage_directory():
    directory = Path(current_app.config["DOCUMENT_STORAGE_DIR"])
    if not directory.is_absolute():
        directory = ROOT / directory

    directory.mkdir(parents=True, exist_ok=True)

    return directory.resolve()

def save_upload(content):
    storage_key = uuid4().hex
    path = storage_directory() / storage_key
    created = False

    try:
        # Create a new file; never overwrite an existing file.
        with path.open("xb") as stream:
            created = True
            stream.write(content)

    except OSError:
        # Remove a partially written file after a write failure.
        if created:
            path.unlink(missing_ok=True)
        raise

    return storage_key, path

def stored_file_path(storage_key):
    directory = storage_directory()
    path = (directory / storage_key).resolve()

    # The file must be directly inside the configured storage directory.
    if path.parent != directory or not path.is_file():
        raise ApiError(
            404,
            "NOT_FOUND",
            "Document file not found.",
        )

    return path
