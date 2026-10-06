#!/bin/sh
set -eu
cd "$(dirname "$0")"
# Use a standard Node installation, or the local Codex runtime when available.
if ! command -v node >/dev/null 2>&1; then
  runtime_bin="$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin"
  if [ -x "$runtime_bin/node" ]; then
    PATH="$runtime_bin:$PATH"
    export PATH
  else
    echo "Node.js 22.12 or newer is required. Install Node, then reopen the terminal." >&2
    exit 1
  fi
fi
if command -v pnpm >/dev/null 2>&1; then
  exec pnpm "$@"
fi
fallback_pnpm="$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/fallback/pnpm"
if [ -x "$fallback_pnpm" ]; then exec "$fallback_pnpm" "$@"; fi
echo "pnpm is required. Install pnpm, then rerun this command." >&2
exit 1
