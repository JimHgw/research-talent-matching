"""Resolve shared resources independently of the process working directory."""

from pathlib import Path

# Keep existing relative DATABASE_URL values anchored to the repository root.
ROOT = Path(__file__).resolve().parents[3]
