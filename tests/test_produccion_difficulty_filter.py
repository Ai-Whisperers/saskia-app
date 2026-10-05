"""Tests for /produccion B.10 — difficulty filter on plan rows.

Cooks can self-select "fácil" tasks when they're tired. We surface a
6-pill filter above the table (Todas + ⭐..⭐⭐⭐⭐⭐) so the cook can
quickly narrow the day's work. The filter:
- Is purely a UX layer (no SQL change)
- Persists via ?difficulty=<1-5|all> in the URL
- Pre-filters via JS for instant feedback; the URL still drives the
  server-side state for deep-link + refresh safety
- Always shows ad-hoc (extra hornos) rows regardless of filter — they
  don't have a recipe difficulty and the cook needs to see them

Verified by structural test (template source) since the filter is
client-side JS and the count is just a span.
"""

from __future__ import annotations

from pathlib import Path

TEMPLATE = Path(__file__).parent.parent / "app" / "templates" / "produccion.html"
SRC = TEMPLATE.read_text(encoding="utf-8")


def test_produccion_template_has_difficulty_filter_pills():
    """B.10 — 6-way pill filter above the table."""
    assert "difficulty-filter" in SRC, "B.10 — difficulty-filter div must exist in produccion.html"
    assert "Filtrar por dificultad" in SRC, (
        "B.10 — filter must have an accessible aria-label in Spanish"
    )
    # The 6 options: all, ⭐, ⭐⭐, ⭐⭐⭐, ⭐⭐⭐⭐, ⭐⭐⭐⭐⭐
    for opt in ("'all'", "'1'", "'2'", "'3'", "'4'", "'5'"):
        assert opt in SRC, f"B.10 — filter option {opt} missing from pill set"


def test_produccion_template_difficulty_filter_uses_url_param():
    """B.10 — ?difficulty= query param drives the active state."""
    assert "request.query_params.get('difficulty', 'all')" in SRC, (
        "B.10 — template must read ?difficulty= from request.query_params"
    )
    assert "data-difficulty-active=" in SRC, (
        "B.10 — table must carry data-difficulty-active for JS to read"
    )


def test_produccion_template_rows_carry_difficulty_attribute():
    """B.10 — Each <tr> has data-difficulty for client-side filtering."""
    # Find the row block
    idx = SRC.find("production-row")
    assert idx > 0
    window = SRC[idx : idx + 500]
    assert "data-difficulty=" in window, (
        "B.10 — production-row must carry data-difficulty attribute"
    )
    assert "data-ad-hoc=" in window, (
        "B.10 — production-row must carry data-ad-hoc for ad-hoc exemption"
    )


def test_produccion_template_difficulty_filter_js_present():
    """B.10 — Client-side filter JS that hides/shows rows by level."""
    assert "function applyFilter" in SRC, (
        "B.10 — applyFilter function must exist for client-side filter"
    )
    assert "row.style.display" in SRC, "B.10 — applyFilter must toggle row.style.display"
    # Ad-hoc rows are always visible
    assert "isAdHoc" in SRC, "B.10 — ad-hoc rows must always remain visible"
    assert "data-ad-hoc" in SRC, "B.10 — JS must read data-ad-hoc attribute to detect ad-hoc rows"


def test_produccion_template_difficulty_count_display():
    """B.10 — Section header shows 'X / Y productos' for filter visibility."""
    assert "data-difficulty-count" in SRC, (
        "B.10 — section header must have data-difficulty-count span"
    )
    # The span has the initial "X / X productos" content (server-rendered).
    assert "productos" in SRC, "B.10 — count display must mention 'productos' (Spanish)"
    # The JS that updates the count on filter change is in the second
    # occurrence of `data-difficulty-count` (in the JS at the bottom).
    last_idx = SRC.rfind("data-difficulty-count")
    assert last_idx > 0
    window = SRC[last_idx : last_idx + 1000]
    assert "' productos'" in window, "B.10 — JS update must append 'productos' to the count"
    assert "textContent" in window, "B.10 — count must be updated via textContent"


def test_produccion_template_difficulty_filter_pills_are_anchors():
    """B.10 — Pills are anchor tags with href so deep-links work."""
    idx = SRC.find("difficulty-filter")
    assert idx > 0
    window = SRC[idx : idx + 1500]
    # The pill <a> tags carry href
    assert 'href="?for_date=' in window, "B.10 — pills must be anchor tags with href for deep-link"
    # And they include &difficulty= to persist the choice
    assert "&difficulty=" in window, "B.10 — pill href must include the &difficulty= param"
    # And shift context is preserved
    assert "&shift=" in window, "B.10 — pill href must preserve shift context (D.2)"
