"""PR A4 — tests for app/rms/static_paths.py.

Pins the contract that app/rms/static_paths.py provides path resolvers
that work regardless of the current working directory (portability:
local install, VPS, Docker all resolve to the same paths).

The module is small (4 functions) but it's the single source of truth
for the recipe-photo and uploads directories — getting it wrong means
photos silently land in the wrong folder on prod.
"""

from __future__ import annotations

import os
from pathlib import Path

from app.rms.static_paths import app_root, recipes_dir


def test_app_root_is_absolute() -> None:
    """All path resolvers return absolute paths (no `Path('app')` leaks)."""
    assert app_root().is_absolute()


def test_app_root_resolves_to_app_package() -> None:
    """`app_root()` must end in `/app` and be the package containing
    `app/rms/static_paths.py`.
    """
    # The test file is in tests/ (a sibling of app/). The static_paths
    # module lives at app/rms/static_paths.py. From the test file:
    #   __file__         = tests/test_static_paths.py
    #   .parent          = tests/
    #   .parent.parent   = repo_root/
    #   .parent.parent / "app" = app/  (== app_root())
    expected = Path(__file__).resolve().parent.parent / "app"
    assert app_root() == expected
    assert app_root().name == "app"


def test_app_root_independent_of_cwd(tmp_path: Path) -> None:
    """`app_root()` must NOT depend on the current working directory."""
    root_from_default = app_root()
    try:
        os.chdir(tmp_path)
        assert app_root() == root_from_default
    finally:
        os.chdir(root_from_default.parent)  # best-effort restore


def test_recipes_dir_is_under_app_root() -> None:
    """`recipes_dir()` returns a path under `app_root()`."""
    assert recipes_dir().is_absolute()
    assert recipes_dir().parent.parent == app_root()
    assert recipes_dir().name == "recipes"


def test_recipes_dir_path_components() -> None:
    """The exact path is `app_root() / 'static' / 'recipes'`."""
    assert recipes_dir() == app_root() / "static" / "recipes"


def test_recipes_dir_independent_of_cwd(tmp_path: Path) -> None:
    """Same cwd-independence as `app_root()`."""
    expected = recipes_dir()
    try:
        os.chdir(tmp_path)
        assert recipes_dir() == expected
    finally:
        os.chdir(expected.parent.parent.parent)


def test_app_root_is_path_instance() -> None:
    """Return type must be pathlib.Path, not str."""
    assert isinstance(app_root(), Path)
    assert isinstance(recipes_dir(), Path)
