"""Pytest fixtures for the test suite.

Per docs/operations/2026-09-fase-1-specs.md §9 (test-suite minimum).

Tests use an in-memory SQLite for speed. For the full DB integration
tests (costing, stock-drop, void), see test_costing.py and friends.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def temp_dir(tmp_path):
    """A fresh temp directory for file-based tests (backups, exports)."""
    return tmp_path


@pytest.fixture
def make_decimal():
    """Factory for Decimal values; convenient for parametrize."""
    from decimal import Decimal

    def _make(value):
        return Decimal(str(value))

    return _make
