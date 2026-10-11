"""Private storage for original uploaded documents."""

from pathlib import Path
from uuid import uuid4

from flask import current_app

from ...shared.paths import ROOT

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