"""tests/test_lazy_openpyxl.py — openpyxl is loaded on demand, not at startup."""

from __future__ import annotations


def test_openpyxl_not_loaded_until_excel_endpoint_hit():
    """Without hitting /excel, openpyxl should NOT be in sys.modules."""
    import sys

    # Ensure not loaded yet
    for mod in list(sys.modules):
        if mod.startswith("openpyxl"):
            del sys.modules[mod]

    # Import app.main (which imports all routers). openpyxl should NOT
    # have been loaded as a side effect.
    # Force reimport in a fresh module if possible.
    if "app.rms.main" in sys.modules:
        del sys.modules["app.rms.main"]

    import app.rms.main  # noqa: F401

    loaded = [m for m in sys.modules if m.startswith("openpyxl")]
    assert loaded == [], f"openpyxl should be lazy-loaded but found: {loaded[:3]}"


def test_excel_io_router_does_not_import_openpyxl_at_module_level():
    """The excel_io router file should not have openpyxl imports at top."""
    import ast
    from pathlib import Path

    src = Path("/opt/data/work/sazon-app/app/routers/excel_io.py").read_text()
    tree = ast.parse(src)
    # Walk top-level imports
    top_level_imports = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                top_level_imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            top_level_imports.append(node.module or "")
    assert not any("openpyxl" in m for m in top_level_imports), (
        f"openpyxl found at module-level: {top_level_imports}"
    )
