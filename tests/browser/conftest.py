"""tests/browser/conftest.py — register the fixtures for the browser layer.

Skips the whole layer gracefully when Chromium isn't installed (CI without
browsers) instead of erroring.
"""

from __future__ import annotations

import os

import pytest

from . import CHROME

# pytest_plugins is registered at the top-level conftest (tests/conftest.py)
# since pytest >=7 disallows non-top-level pytest_plugins declarations.


def pytest_collection_modifyitems(config, items):
    if not os.path.exists(CHROME):
        skip = pytest.mark.skip(reason=f"Chromium not installed at {CHROME}")
        for item in items:
            if "browser" in item.keywords:
                item.add_marker(skip)
