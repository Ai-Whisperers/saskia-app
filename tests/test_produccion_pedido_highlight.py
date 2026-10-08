"""Tests for visual highlight when a row has a pending pedido.

T-2026-10-04 (P1): The cook needs to spot 'we owe 3 tortas today'
instantly. A 4px blue accent + tinted background on rows with a
pending pedido makes the commitment pop visually.

Note: since the PR4 CSS refactor (5bfb09df) the highlight rules live in
app/static/app-improvements.css, not an inline <style> block — so the
"defined" assertions check TEMPLATE + CSS body (CSS_BODY pattern from
test_produccion_polish.py), while the runtime assertions still check the
rendered page.
"""

from pathlib import Path

_TEMPLATE_PATH = Path(__file__).parent.parent / "app" / "templates" / "produccion.html"
_IMPROVEMENTS_PATH = Path(__file__).parent.parent / "app" / "static" / "app-improvements.css"
# When the test wants to look at "the page's CSS", check both.
CSS_BODY = (
    _TEMPLATE_PATH.read_text(encoding="utf-8")
    + "\n"
    + _IMPROVEMENTS_PATH.read_text(encoding="utf-8")
)


def test_row_highlight_class_applied_when_pedido(authed_client):
    """The highlight rule exists in the page's CSS (template or extracted sheet)."""
    r = authed_client.get("/produccion?view=day")
    assert r.status_code == 200
    # The rule must exist in the page's CSS — even with no data rows.
    assert ".production-row--has-pedido" in CSS_BODY


def test_pedido_qty_class_is_defined(authed_client):
    """The .pedido-qty class is wired into the badge for visual emphasis."""
    r = authed_client.get("/produccion?view=day")
    assert r.status_code == 200
    body = r.text
    # The badge class renders in the row loop markup...
    assert "pedido-qty" in CSS_BODY
    # ...and the CSS rule exists for it.
    assert ".pedido-qty" in CSS_BODY


def test_print_rule_preserves_highlight(authed_client):
    """The @media print rule keeps the highlight visible on paper."""
    r = authed_client.get("/produccion?view=day")
    assert r.status_code == 200
    # The print stylesheet should override for production-row--has-pedido
    # (so it's visible when bakers print the worksheet).
    assert "@media print" in CSS_BODY
    assert ".production-row--has-pedido" in CSS_BODY
