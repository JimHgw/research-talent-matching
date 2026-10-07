"""Stable Flask entry point; the application implementation lives in src/."""

from .src.app import create_app

__all__ = ["create_app"]
