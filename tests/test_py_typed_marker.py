"""tests/test_py_typed_marker.py — package declares type info via py.typed."""
from __future__ import annotations


def test_py_typed_marker_exists():
    """The py.typed marker file is present and non-empty."""
    from pathlib import Path
    p = Path("/opt/data/profiles/ivan/scratch/saskia-app-work/app/py.typed")
    assert p.exists(), "app/py.typed is missing"
    # PEP 561: even an empty file is valid. We use a docstring for clarity.
    assert p.stat().st_size > 0
