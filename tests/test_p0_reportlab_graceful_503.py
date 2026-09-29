"""P0-2: tests for /reportes/iva/pdf (and friends) reportlab handling.

The PDF endpoints must:
  1. Generate valid PDFs when reportlab is installed (happy path)
  2. Return a clean 503 with install hint when reportlab is missing
     (instead of 500 with stack trace)
"""
from __future__ import annotations

import importlib
import sys
from typing import Any


def test_pdf_endpoints_generate_valid_pdf(client) -> None:
    """Each /reportes/*/pdf endpoint returns a valid PDF (with reportlab installed).

    reportlab is installed in this venv (per pyproject.toml).
    """
    for path in (
        "/reportes/iva/pdf",
        "/reportes/diario/pdf",
    ):
        r = client.get(path)
        assert r.status_code == 200, f"{path}: {r.status_code} {r.text[:200]}"
        assert r.headers.get("content-type") == "application/pdf"
        # PDF magic header
        assert r.content[:5] == b"%PDF-", f"{path}: not a valid PDF"


def test_pdf_endpoint_returns_503_when_reportlab_missing(client) -> None:
    """When reportlab is uninstalled, /reportes/iva/pdf returns 503 with hint.

    We block the import at the meta_path level (more reliable than
    monkeypatching a single attribute — reportlab imports subpackages
    that all need to fail).
    """

    class _Blocker:
        def find_spec(self, name: str, path: Any = None, target: Any = None) -> None:
            if name == "reportlab" or name.startswith("reportlab."):
                raise ImportError("SIMULATED: reportlab unavailable")
            return None

    blocker: Any = _Blocker()
    sys.meta_path.insert(0, blocker)

    # Also evict any cached reportlab submodules so the next import re-runs
    for mod_name in list(sys.modules.keys()):
        if mod_name == "reportlab" or mod_name.startswith("reportlab."):
            del sys.modules[mod_name]

    try:
        r = client.get("/reportes/iva/pdf")
        assert r.status_code == 503, (
            f"Expected 503 when reportlab missing, got {r.status_code}: {r.text[:300]}"
        )
        # The detail message should mention 'reportlab' so an operator
        # reading the error knows what to install.
        assert "reportlab" in r.text.lower()
    finally:
        try:
            sys.meta_path.remove(blocker)
        except ValueError:
            pass
