"""app/rms/static_paths.py — resolve writable/static dirs without
hardcoded absolute dev paths (portability: local install, VPS, Docker)."""

from __future__ import annotations

from pathlib import Path


def app_root() -> Path:
    """The app package root (…/app), regardless of cwd."""
    return Path(__file__).resolve().parent.parent


def recipes_dir() -> Path:
    """Directory of recipe photos (app/static/recipes)."""
    return app_root() / "static" / "recipes"
