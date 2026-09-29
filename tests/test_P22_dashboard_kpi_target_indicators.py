"""P-22 / audit #7: Dashboard KPIs show target visual feedback (not just text).

Audit finding: the 4 KPIs with objectives (food_cost_pct ≤35%,
gross_margin_pct ≥60%, repeat_pct ≥30%, waste_pct ≤5%) only render the
target as text — no progress bar with severity color. The owner has to
do mental math on every page load.

The metric_card macro supports `target=` and renders a colored progress
bar (is-ok / is-warn / is-danger) based on target ratio. The dashboard
must pass `target` to the macro.

Behavior:
- When actual data exists: KPI value + colored target progress bar
- When actual data is missing (e.g. no recipe costing → "sin escandallo"):
  plain text fallback (honest "unknown" state, not a target violation)

This test verifies BOTH paths.
"""
from __future__ import annotations

import re

import pytest

pytestmark = [pytest.mark.smoke]


# (label, direction). Direction 'low' = lower actual is better
# (cost/waste). 'high' = higher actual is better (margin/recurrence).
KPI_TILES = [
    {"label": "Costo de materia prima %", "direction": "low"},
    {"label": "Margen bruto %", "direction": "high"},
    {"label": "Recurrencia %", "direction": "high"},
    {"label": "Merma %", "direction": "low"},
]

# Text values that mean "data unavailable" (no target bar expected)
DATA_UNAVAILABLE_VALUES = {"sin escandallo", "—"}


def _kpi_block(body: str, label: str) -> str:
    """Return the metric-card block (everything between the label and
    the next metric-card opening) for the given label."""
    label_pat = rf'<div class="metric-card__label">{re.escape(label)}</div>'
    m = re.search(label_pat, body)
    assert m, f"KPI label '{label}' not found in dashboard HTML"
    rest = body[m.end():]
    # Find next metric-card OPEN (with space or > after the class name).
    # The "metric-card__label" / "metric-card__value" etc. won't match this.
    next_card = re.search(r'<div class="metric-card(?:\s|">)', rest)
    end = next_card.start() if next_card else 1500
    return rest[:end]


def _kpi_value(kpi_block: str) -> str:
    m = re.search(r'<div class="metric-card__value">(?P<v>.*?)</div>', kpi_block, re.DOTALL)
    assert m, f"No metric-card__value found in block: {kpi_block[:300]}"
    return m.group("v").strip()


def _kpi_has_bar(kpi_block: str) -> bool:
    return "metric-card__target" in kpi_block


def _kpi_severity(kpi_block: str) -> str | None:
    m = re.search(r'metric-card__target-fill\s+(?P<s>is-ok|is-warn|is-danger)', kpi_block)
    return m.group("s") if m else None


def _kpi_bar_width(kpi_block: str) -> int | None:
    m = re.search(r'width:\s*(?P<w>\d+)%', kpi_block)
    return int(m.group("w")) if m else None


@pytest.mark.parametrize("kpi", KPI_TILES)
def test_dashboard_kpi_renders_value(client, kpi):
    """P-22 sanity: every KPI tile must render a non-empty value."""
    r = client.get("/dashboard")
    assert r.status_code == 200
    block = _kpi_block(r.text, kpi["label"])
    val = _kpi_value(block)
    assert val, f"KPI '{kpi['label']}' has empty value"


@pytest.mark.parametrize("kpi", KPI_TILES)
def test_dashboard_kpi_either_bar_or_no_data_fallback(client, kpi):
    """P-22: Either target bar exists, OR the value is a known 'no data' marker.

    Catches both: missing the bar when data exists, AND missing the bar
    AND missing the fallback text.
    """
    r = client.get("/dashboard")
    assert r.status_code == 200
    block = _kpi_block(r.text, kpi["label"])
    val = _kpi_value(block)
    has_bar = _kpi_has_bar(block)
    if has_bar:
        sev = _kpi_severity(block)
        width = _kpi_bar_width(block)
        assert sev in {"is-ok", "is-warn", "is-danger"}, (
            f"KPI '{kpi['label']}' has bar but no severity class. Block:\n{block[:400]}"
        )
        assert width is not None and 0 <= width <= 100, (
            f"KPI '{kpi['label']}' has bar but bad width {width}. Block:\n{block[:400]}"
        )
    else:
        assert val in DATA_UNAVAILABLE_VALUES, (
            f"KPI '{kpi['label']}' has no target bar AND value '{val}' "
            f"is not a documented 'no data' marker. Block:\n{block[:400]}"
        )


@pytest.mark.parametrize("kpi", KPI_TILES)
def test_dashboard_kpi_no_data_fallback_shows_objective_text(client, kpi):
    """P-22: When KPI falls back to 'no data', the objective text MUST still appear."""
    r = client.get("/dashboard")
    assert r.status_code == 200
    block = _kpi_block(r.text, kpi["label"])
    if _kpi_has_bar(block):
        pytest.skip("Has bar (data exists) — N/A for this test")
    assert "objetivo:" in block, (
        f"KPI '{kpi['label']}' in no-data fallback but missing 'objetivo:' text. "
        f"Block:\n{block[:400]}"
    )


def test_dashboard_recurrencia_has_target_bar_even_at_zero(client):
    """P-22: For demo DB (zero sales), Recurrencia % MUST show target bar
    (showing 0% — danger color — not silently hiding the KPI)."""
    r = client.get("/dashboard")
    assert r.status_code == 200
    block = _kpi_block(r.text, "Recurrencia %")
    assert _kpi_has_bar(block), (
        f"Recurrencia % must render target bar even at 0% (demo state). Block:\n{block[:400]}"
    )
    # At 0% it should be is-danger (red)
    assert _kpi_severity(block) == "is-danger", (
        f"Recurrencia % at 0% should be is-danger. Got: {_kpi_severity(block)}. Block:\n{block[:400]}"
    )


def test_dashboard_merma_has_target_bar_even_at_zero(client):
    """P-22: For demo DB (zero waste), Merma % MUST show target bar."""
    r = client.get("/dashboard")
    assert r.status_code == 200
    block = _kpi_block(r.text, "Merma %")
    assert _kpi_has_bar(block), (
        f"Merma % must render target bar even at 0% (demo state). Block:\n{block[:400]}"
    )
    # At 0% / target 5% = 0% ratio → for 'low' direction, ratio=0 <= 1.0 → is-ok (green)
    assert _kpi_severity(block) == "is-ok", (
        f"Merma % at 0% should be is-ok (well under target). Got: {_kpi_severity(block)}."
    )
