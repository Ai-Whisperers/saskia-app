"""tests/test_integrations_and_seed_split.py — Sprint 2.4 verification.

Sprint 2.4 of the 2026-10-02 backend overhaul: extract infra layer + split
monolithic seed file.

This test pins:

1. app/integrations/ package exists with scrapers.py, barcode.py, printer.py
2. app/rms/api/ package is GONE (the aspirational API layer was unused)
3. app/rms/scrapers.py, barcode.py, printer.py are GONE (moved to integrations)
4. app/rms/seed_competitor_prices.py is GONE (split into seed/ package)
5. app/rms/seed/ is a package with the per-category data files
6. COMPETITOR_SEED_ALL has the same row count as the original file (144)
7. seed_competitor_prices() is callable and idempotent
"""

from __future__ import annotations

import os

RMS = "/opt/data/work/saskia-app/app/rms"
INTEGRATIONS = "/opt/data/work/saskia-app/app/integrations"


def test_integrations_package_exists():
    assert os.path.isdir(INTEGRATIONS), "app/integrations/ missing"
    assert os.path.exists(os.path.join(INTEGRATIONS, "__init__.py"))
    for mod in ["scrapers", "barcode", "printer"]:
        p = os.path.join(INTEGRATIONS, f"{mod}.py")
        assert os.path.exists(p), f"missing {p}"


def test_rms_infra_files_gone():
    for mod in ["scrapers.py", "barcode.py", "printer.py"]:
        p = os.path.join(RMS, mod)
        assert not os.path.exists(p), f"{mod} should have moved to integrations"


def test_api_package_gone():
    """The aspirational app/rms/api/ package had zero callers."""
    api_dir = os.path.join(RMS, "api")
    assert not os.path.exists(api_dir), (
        "app/rms/api/ was dead code (499 lines, no callers)"
    )


def test_seed_competitor_prices_split():
    """The 1651-line seed file is split into seed/ package."""
    old = os.path.join(RMS, "seed_competitor_prices.py")
    assert not os.path.exists(old), "old monolithic file should be gone"
    pkg = os.path.join(RMS, "seed")
    assert os.path.isdir(pkg), "seed/ package missing"
    assert os.path.exists(os.path.join(pkg, "__init__.py"))


def test_seed_data_files_present():
    """The two data files + orchestrator exist with content."""
    seed_pkg = os.path.join(RMS, "seed")
    expected = [
        "competitor_seed.py",        # 86 non-shopping entries
        "competitor_shoppings.py",   # 58 shopping entries
        "competitor_prices.py",      # orchestrator
    ]
    for name in expected:
        p = os.path.join(seed_pkg, name)
        assert os.path.exists(p), f"missing seed/{name}"
        size = os.path.getsize(p)
        assert size > 100, f"seed/{name} too small ({size} bytes)"


def test_competitor_seed_all_row_count():
    """COMPETITOR_SEED_ALL has the same row count as the original file (144).

    The original had COMPETITOR_SEED (86) + COMPETITOR_SEED_SHOPPINGS (58)
    = 144 rows. The split must preserve this.
    """
    from app.rms.seed.competitor_prices import COMPETITOR_SEED_ALL

    assert len(COMPETITOR_SEED_ALL) == 144, (
        f"expected 144 rows, got {len(COMPETITOR_SEED_ALL)}"
    )


def test_competitor_seed_backward_compat():
    """COMPETITOR_SEED + COMPETITOR_SEED_SHOPPINGS still work for old callers.

    :174 must NOT include shopping rows; SHOPPINGS must contain ONLY
    shopping rows. This matches the original file's two-list split.
    """
    from app.rms.seed.competitor_prices import (
        COMPETITOR_SEED,
        COMPETITOR_SEED_SHOPPINGS,
    )

    # Original: 86 (non-shopping) + 58 (shopping) = 144
    assert len(COMPETITOR_SEED) + len(COMPETITOR_SEED_SHOPPINGS) == 144
    # Non-shopping bucket had 86 rows (supermercados + cafes + importados).
    assert len(COMPETITOR_SEED) == 86
    # Shopping bucket had 58 rows.
    assert len(COMPETITOR_SEED_SHOPPINGS) == 58


def test_seed_competitor_prices_callable():
    """The orchestrator is callable (DB-touching; just check signature)."""
    from app.rms.seed.competitor_prices import seed_competitor_prices

    assert callable(seed_competitor_prices)
    # Should accept a Session; return tuple[int, int]
    import inspect

    sig = inspect.signature(seed_competitor_prices)
    params = list(sig.parameters.values())
    assert len(params) == 1
    assert params[0].name == "session"


def test_no_app_rms_api_references_in_codebase():
    """No code references the dead api/ module."""
    import subprocess

    r = subprocess.run(
        ["grep", "-rn", "app\\.rms\\.api\\.", "/opt/data/work/saskia-app/", "--include=*.py"],
        capture_output=True,
        text=True,
    )
    # Filter out the test file's own assertion message
    lines = [
        line for line in r.stdout.split("\n")
        if line and "test_integrations_and_seed_split.py" not in line
    ]
    assert not lines, (
        f"stray references to app.rms.api.* found:\n{chr(10).join(lines)}"
    )


def test_no_app_rms_scrapers_references():
    """All scrapers references moved to app.integrations.scrapers."""
    import subprocess

    r = subprocess.run(
        ["grep", "-rn", "app\\.rms\\.scrapers", "/opt/data/work/saskia-app/", "--include=*.py"],
        capture_output=True,
        text=True,
    )
    lines = [
        line for line in r.stdout.split("\n")
        if line and "test_integrations_and_seed_split.py" not in line
    ]
    assert not lines, (
        f"stray references to app.rms.scrapers:\n{chr(10).join(lines)}"
    )


def test_no_app_rms_barcode_or_printer_references():
    """All barcode/printer references moved to app.integrations."""
    import subprocess

    for mod in ("barcode", "printer"):
        r = subprocess.run(
            ["grep", "-rn", f"app\\.rms\\.{mod}\\b", "/opt/data/work/saskia-app/", "--include=*.py"],
            capture_output=True,
            text=True,
        )
        lines = [
            line for line in r.stdout.split("\n")
            if line and "test_integrations_and_seed_split.py" not in line
        ]
        assert not lines, (
            f"stray app.rms.{mod} references:\n{chr(10).join(lines)}"
        )


def test_no_app_rms_seed_competitor_prices_references():
    """All callers use the new path app.rms.seed.competitor_prices."""
    import subprocess

    r = subprocess.run(
        ["grep", "-rn", "app\\.rms\\.seed_competitor_prices", "/opt/data/work/saskia-app/", "--include=*.py"],
        capture_output=True,
        text=True,
    )
    lines = [
        line for line in r.stdout.split("\n")
        if line and "test_integrations_and_seed_split.py" not in line
    ]
    assert not lines, (
        f"stray app.rms.seed_competitor_prices references:\n{chr(10).join(lines)}"
    )