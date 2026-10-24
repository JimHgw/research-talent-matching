#!/bin/sh
set -eu

# These CLI operations are safe to repeat with the same schema and vocabulary.
python -m flask --app backend.app init-db
python -m flask --app backend.app upgrade-opportunity-search
# The reviewed resume TEXT -> MEDIUMTEXT upgrade preserves existing data.
python -m flask --app backend.app upgrade-resume-text
python -m flask --app backend.app seed-tags

# Forward container stop signals to the server; never create default accounts.
exec "$@"
