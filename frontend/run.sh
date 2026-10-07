#!/bin/sh
set -eu
repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
python="$repo_root/.venv/bin/python"
if [ ! -x "$python" ]; then
  echo "Run sh setup.sh from the repository root first (Python 3.12+ and Node.js 22.12+ with npm required)." >&2
  exit 1
fi
exec "$python" "$repo_root/scripts/dev.py" frontend "$@"
