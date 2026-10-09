#!/bin/sh
set -eu

# These CLI operations are safe to repeat with the same schema and vocabulary.
# A changed existing table still needs an explicit migration.
python -m flask --app backend.app init-db
python -m flask --app backend.app seed-tags

# Forward container stop signals to the server; never create default accounts.
exec "$@"
