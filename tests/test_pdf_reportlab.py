"""PR A4 — tests for app/services/pdf_reportlab.py.

Pins the lazy-import shim contract:
  - When reportlab IS installed: import_reportlab() returns the expected
    names from the reportlab tree in a single dict.
  - When reportlab is NOT installed: HTTPException(503) is raised with
    a clear install hint (NOT a raw 500 with a stack trace).

The "import is missing" path is hard to reproduce without uninstalling
reportlab, so we use sys.modules manipulation to simulate the failure
in-process.
"""

from __future__ import annotations

import builtins
import sys
from importlib import reload

import pytest
from fastapi import HTTPException


def test_import_reportlab_returns_expected_keys() -> None:
    """When reportlab is installed, the dict has all 10 expected names."""
    from app.services import pdf_reportlab

    names = pdf_reportlab.import_reportlab()
    expected = {
        "colors",
        "A4",
        "ParagraphStyle",
        "getSampleStyleSheet",
        "cm",
        "Paragraph",
        "SimpleDocTemplate",
        "Spacer",
        "Table",
        "TableStyle",
    }
    assert set(names.keys()) == expected
    # Spot-check that each value is the actual class/module (not a Mock)
    assert names["A4"] is not None
    assert callable(names["TableStyle"])


def test_import_reportlab_caches_module_import() -> None:
    """Calling import_reportlab twice should not be more expensive than once.

    This is a soft assertion: we just check the returned names are the
    same object identity (Python's import cache makes the second call
    return the same module objects).
    """
    from app.services import pdf_reportlab

    a = pdf_reportlab.import_reportlab()
    b = pdf_reportlab.import_reportlab()
    assert a["A4"] is b["A4"]
    assert a["Table"] is b["Table"]


def test_missing_reportlab_raises_503_with_install_hint() -> None:
    """Simulate reportlab not being installed → HTTPException(503) + hint."""
    # Save the real module + all reportlab.* submodules
    saved_modules = {
        name: mod
        for name, mod in sys.modules.items()
        if name == "reportlab" or name.startswith("reportlab.")
    }

    # Remove the reportlab tree
    for name in list(sys.modules):
        if name == "reportlab" or name.startswith("reportlab."):
            del sys.modules[name]

    # Block re-import: any `import reportlab...` raises ImportError
    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "reportlab" or name.startswith("reportlab."):
            raise ImportError(f"No module named '{name}' (simulated by test)")
        return real_import(name, globals, locals, fromlist, level)

    builtins.__import__ = fake_import
    try:
        # Reload the shim so it picks up the blocked import
        from app.services import pdf_reportlab

        reloaded = reload(pdf_reportlab)

        with pytest.raises(HTTPException) as exc_info:
            reloaded.import_reportlab()
        assert exc_info.value.status_code == 503
        # The error message must include the install hint
        detail = exc_info.value.detail
        assert "reportlab" in detail.lower()
        assert "install" in detail.lower() or "uv sync" in detail.lower()
        # The original ImportError must be preserved as __cause__
        assert isinstance(exc_info.value.__cause__, ImportError)
    finally:
        # Restore reportlab modules
        builtins.__import__ = real_import
        # Clear the simulated-empty state
        for name in list(sys.modules):
            if name == "reportlab" or name.startswith("reportlab."):
                del sys.modules[name]
        # Re-import the reportlab tree from cache (or fresh)
        for name, mod in saved_modules.items():
            sys.modules[name] = mod
        # Re-reload the shim to restore the real `import_reportlab`
        from app.services import pdf_reportlab

        reload(pdf_reportlab)
