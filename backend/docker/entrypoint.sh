#!/bin/sh
set -eu

# Local and Docker releases share the same ordered, fail-closed preflight.
python -m flask --app backend.app prepare-db

# Forward container stop signals to the server; never create default accounts.
exec "$@"
