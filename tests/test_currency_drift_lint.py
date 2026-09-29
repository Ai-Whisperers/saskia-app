"""tests/test_currency_drift_lint.py — verify scripts/check_currency_drift.sh behavior.

This test does NOT shell out (it's a bash script test, but we test the
behavior via static analysis + an actual run on the live tree). The goal
is to catch regressions in the script's allowlist and patterns.

If this script breaks (false negatives or false positives), the D3 currency
drift defect becomes undetectable again. Treat as P0.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "check_currency_drift.sh"


def test_script_exists_and_executable():
    """The script must exist and be executable (CI runs it directly)."""
    assert SCRIPT.exists(), "scripts/check_currency_drift.sh is missing"
    import os
    import stat
    mode = SCRIPT.stat().st_mode
    assert mode & stat.S_IXUSR, "script is not user-executable"


def test_script_exits_zero_on_clean_tree():
    """On the current tree (after Session A's allowlist tuning), exit code is 0.

    If this fails, either:
    - A new raw 'Gs. {{ value }}' was added (drift detected — fix it).
    - The allowlist was over-broadened (script is broken — restore strictness).
    """
    result = subprocess.run(
        [str(SCRIPT)],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"Currency drift detected:\n{result.stdout}\n{result.stderr}\n"
        "Run ./scripts/check_currency_drift.sh locally to see violations."
    )
    assert "✅ No currency drift detected" in result.stdout


def test_script_reports_scanned_count():
    """Output must include a 'Files scanned' line (telemetry for CI logs)."""
    result = subprocess.run(
        [str(SCRIPT)],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    assert "Files scanned:" in result.stdout


def test_allowlist_excludes_money_formatting_modules():
    """app/rms/money.py and app/rms/display.py are the format_gs SOURCE — they
    MUST be allowed to contain raw 'Gs.' literals (they define them).
    The bash regex uses escaped dots (\\.) — the test checks for the bare path."""
    text = SCRIPT.read_text(encoding="utf-8")
    # bash-escaped: app/rms/money\.py
    assert "app/rms/money\\.py" in text or "app/rms/money.py" in text, \
        "format_gs source module must be in allowlist (else self-lint fails)"
    assert "app/rms/display\\.py" in text or "app/rms/display.py" in text, \
        "display formatter module must be in allowlist"


def test_allowlist_excludes_receta_form():
    """receta_form.html is a 1149-LOC form that we're not refactoring without
    e2e tests (hat 7+28). The Gs. literals inside it are JS-updated placeholders.
    Excluded from lint until tests exist."""
    text = SCRIPT.read_text(encoding="utf-8")
    assert "receta_form.html" in text, \
        "receta_form.html must be in allowlist (untouchable until e2e tests)"


def test_allowlist_excludes_changelog_and_tests():
    """CHANGELOG.md and tests/ may contain literal 'Gs.' strings (historical
    references, test fixtures). Excluded."""
    text = SCRIPT.read_text(encoding="utf-8")
    assert "app/CHANGELOG.md" in text, "CHANGELOG must be in allowlist"
    assert "tests/" in text, "tests/ must be in allowlist"


def test_fixed_templates_use_money_macro():
    """The two drift violations fixed in Session A — pedido_stock_preview.html
    line 32 and produccion.html line 141 — must now use m.gs(), not raw Gs. {{}}."""
    preview = (REPO / "app/templates/pedido_stock_preview.html").read_text(encoding="utf-8")
    assert "m.gs(consumed|sum" in preview, \
        "pedido_stock_preview.html must use m.gs() (Session A fix)"
    assert "Gs. {{ consumed|sum" not in preview, \
        "raw Gs. {{ consumed|sum still present (regression)"

    produccion = (REPO / "app/templates/produccion.html").read_text(encoding="utf-8")
    assert "{% import \"_components/macros.html\" as m %}" in produccion, \
        "produccion.html must import the money macros module"
    assert "m.gs(it.unit_price_gs)" in produccion, \
        "produccion.html must use m.gs() for unit_price_gs (Session A fix)"


def test_workflow_file_exists():
    """The .github/workflows/currency-drift.yml gate must exist."""
    workflow = REPO / ".github/workflows/currency-drift.yml"
    assert workflow.exists(), "currency-drift.yml workflow is missing"
    text = workflow.read_text(encoding="utf-8")
    assert "check_currency_drift.sh" in text, \
        "workflow must invoke the drift script"
    assert "pull_request" in text, "workflow must run on pull_request"


@pytest.mark.parametrize("template", [
    "app/templates/inicio.html",
    "app/templates/analisis.html",
    "app/templates/bank.html",
])
def test_kpi_card_adoptions_use_format_gs(template):
    """All three pages that adopted <saskia-kpi-card> in Session A must still
    use format_gs (m.gs_full or m.gs) for any currency rendering."""
    text = (REPO / template).read_text(encoding="utf-8")
    if template == "app/templates/bank.html":
        # bank uses m.gs (compact form)
        assert "m.gs(" in text, f"{template} must use m.gs() for currency"
    else:
        # inicio + analisis use m.gs_full (full Gs. prefix)
        assert "m.gs_full" in text, f"{template} must use m.gs_full for currency"


def test_kpi_card_value_has_uniform_height():
    """The KPI tile value cell must have a min-height so that short values
    ('Sáb') and long values ('G. 10.948.527' / '10:00 hs') render at the
    same row height — flagged by the Session A screenshot subagent."""
    css = (REPO / "app/static/app-components.css").read_text(encoding="utf-8")
    # The min-height rule on .metric-card__value
    assert ".metric-card__value" in css, "value cell class missing"
    assert "min-height" in css, "uniform tile height missing — panorama row will misalign"
    # The rule must apply to both compact and full tiles
    assert ".metric-card--compact .metric-card__value" in css, \
        "compact tiles (e.g. /bank) need a smaller uniform height"
