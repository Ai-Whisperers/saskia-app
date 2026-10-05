"""Tests for /produccion B.7 — Bulk CSV ad-hoc upload.

On a busy Saturday the cook has 8-12 walk-in bakes. Typing each into
the single-row form takes ~10s per row × 12 rows = 2 min of churn.
A single paste of CSV drops it to ~5s of paste + ~2s of commit = ~7s
total. Net: ~1.5 min saved per busy day.

The route POST /produccion/ad-hoc/bulk accepts:
    product_id,qty,notes
    42,1.5,Cliente VIP
    15,2.0,

Header is optional; column order is fixed (qty is always 2nd).
Invalid lines are skipped with a per-line reason — partial success
is more useful than a wholesale failure. Max 200 rows per upload.
"""

from __future__ import annotations

from pathlib import Path

TEMPLATE = Path(__file__).parent.parent / "app" / "templates" / "produccion.html"
ROUTER = Path(__file__).parent.parent / "app" / "routers" / "produccion.py"

TEMPLATE_SRC = TEMPLATE.read_text(encoding="utf-8")
ROUTER_SRC = ROUTER.read_text(encoding="utf-8")


# ────────────────────── route (B.7) ──────────────────────


def test_router_has_bulk_csv_route():
    """B.7 — POST /produccion/ad-hoc/bulk must exist."""
    assert '@router.post("/ad-hoc/bulk")' in ROUTER_SRC, (
        "B.7 — bulk CSV route must be wired at /ad-hoc/bulk"
    )


def test_router_bulk_csv_uses_upsert_completion():
    """B.7 — Each parsed row must reuse _upsert_completion."""
    idx = ROUTER_SRC.find("def produccion_ad_hoc_bulk")
    assert idx > 0
    block = ROUTER_SRC[idx : idx + 5000]
    assert "_upsert_completion(" in block, (
        "B.7 — bulk CSV route must reuse _upsert_completion "
        "so the existing single-row tests continue to cover it"
    )


def test_router_bulk_csv_rate_limited():
    """B.7 — Bulk upload must be rate-limited (anti-fat-finger)."""
    idx = ROUTER_SRC.find("def produccion_ad_hoc_bulk")
    assert idx > 0
    block = ROUTER_SRC[idx : idx + 1500]
    assert "is_write_rate_limited" in block, (
        "B.7 — bulk upload must apply the same 10/min rate limit as the single-row form"
    )


def test_router_bulk_csv_caps_at_200_rows():
    """B.7 — Cap at 200 rows per upload to prevent DoS / fat-finger."""
    idx = ROUTER_SRC.find("def produccion_ad_hoc_bulk")
    assert idx > 0
    block = ROUTER_SRC[idx : idx + 2500]
    assert "MAX_ROWS = 200" in block, "B.7 — must cap uploads at MAX_ROWS = 200"


def test_router_bulk_csv_handles_optional_header():
    """B.7 — Header row (product_id,qty,notes) must be optional."""
    idx = ROUTER_SRC.find("def produccion_ad_hoc_bulk")
    assert idx > 0
    block = ROUTER_SRC[idx : idx + 2500]
    assert 'startswith("product_id")' in block, "B.7 — must detect and skip an optional header row"


def test_router_bulk_csv_skips_invalid_lines():
    """B.7 — Invalid lines must be skipped with a reason, not crash."""
    idx = ROUTER_SRC.find("def produccion_ad_hoc_bulk")
    assert idx > 0
    block = ROUTER_SRC[idx : idx + 5000]
    assert "skipped" in block, "B.7 — must track skipped rows separately"
    # It must handle: non-numeric, missing columns, unknown product_id, qty<=0
    assert "Faltan columnas" in block or "Faltan columnas (minimo product_id, qty)" in block, (
        "B.7 — must report 'Faltan columnas' for short rows"
    )
    assert "no son números" in block or "no son n" in block, (
        "B.7 — must report non-numeric failures"
    )
    assert "no existe" in block, "B.7 — must report unknown product_id"
    assert "qty debe ser > 0" in block, "B.7 — must reject qty <= 0"


def test_router_bulk_csv_renders_summary_html():
    """B.7 — Response is a tiny HTML page showing created/skipped."""
    idx = ROUTER_SRC.find("def produccion_ad_hoc_bulk")
    assert idx > 0
    block = ROUTER_SRC[idx : idx + 10000]
    assert "HTMLResponse" in block, "B.7 — must return HTMLResponse with the import summary"
    assert "Registradas" in block, "B.7 — summary must include a 'Registradas' section"
    assert "Omitidas" in block, "B.7 — summary must include a 'Omitidas' section for skipped rows"
    assert "Volver al plan" in block, "B.7 — summary must include a 'Volver al plan' back-link"


def test_router_bulk_csv_audit_record():
    """B.7 — Bulk upload must write an audit record."""
    idx = ROUTER_SRC.find("def produccion_ad_hoc_bulk")
    assert idx > 0
    block = ROUTER_SRC[idx : idx + 10000]
    assert "record_audit" in block, "B.7 — bulk upload must call record_audit for traceability"
    assert "ad_hoc_bulk" in block, "B.7 — audit action must be write.production.ad_hoc_bulk"


# ────────────────────── template UI (B.7) ──────────────────────


def test_template_has_bulk_csv_modal():
    """B.7 — Day view must render the bulk-CSV modal."""
    assert 'id="adhoc-bulk-modal"' in TEMPLATE_SRC, (
        "B.7 — modal with id='adhoc-bulk-modal' must be in the template"
    )


def test_template_bulk_csv_form_posts_to_route():
    """B.7 — The form must POST to /produccion/ad-hoc/bulk."""
    idx = TEMPLATE_SRC.find('id="adhoc-bulk-modal"')
    assert idx > 0
    block = TEMPLATE_SRC[idx : idx + 2000]
    assert 'action="/produccion/ad-hoc/bulk"' in block, (
        "B.7 — form must POST to /produccion/ad-hoc/bulk"
    )
    assert 'name="csv"' in block, "B.7 — form must carry a 'csv' field (the paste textarea)"
    assert 'name="for_date"' in block, "B.7 — form must carry the for_date context"


def test_template_bulk_csv_button_in_adhoc_section():
    """B.7 — A 'Pegá varios' button next to the single-row trigger."""
    assert 'data-action="open-adhoc-bulk"' in TEMPLATE_SRC, (
        "B.7 — bulk trigger button must have data-action='open-adhoc-bulk'"
    )
    assert "Pegá varios" in TEMPLATE_SRC, "B.7 — button label must include 'Pegá varios (CSV)'"
    # The button uses no-print so paper plans stay clean.
    idx = TEMPLATE_SRC.find('data-action="open-adhoc-bulk"')
    # Skip past the first hit (the JS handler at line ~479) — the button
    # is the second occurrence.
    idx = TEMPLATE_SRC.find('data-action="open-adhoc-bulk"', idx + 1)
    block = TEMPLATE_SRC[max(0, idx - 300) : idx + 300]
    assert "no-print" in block, "B.7 — bulk button must be no-print (paper plans don't need it)"


def test_template_bulk_csv_click_handler():
    """B.7 — The click handler must open the modal + focus the textarea."""
    assert "open-adhoc-bulk" in TEMPLATE_SRC, "B.7 — click handler must reference the data-action"
    # The handler must call showModal() and focus the textarea.
    idx = TEMPLATE_SRC.find("open-adhoc-bulk")
    # Get the script block (look back for <script>)
    script_idx = TEMPLATE_SRC.rfind("<script", 0, idx)
    end_idx = TEMPLATE_SRC.find("</script>", idx)
    block = TEMPLATE_SRC[script_idx:end_idx]
    assert "showModal" in block, "B.7 — click handler must call showModal() on the dialog"
    assert "focus" in block, "B.7 — click handler must focus the textarea for instant paste"


def test_template_bulk_csv_includes_format_hint():
    """B.7 — The modal must explain the CSV format inline."""
    idx = TEMPLATE_SRC.find('id="adhoc-bulk-modal"')
    assert idx > 0
    block = TEMPLATE_SRC[idx : idx + 2500]
    # The hint must mention the column order
    assert "product_id,cantidad,nota" in block or "product_id,qty,notes" in block, (
        "B.7 — modal must show the CSV column order in the hint"
    )
    assert "Max 200" in block or "max 200" in block or "MAX_ROWS" in block, (
        "B.7 — modal must state the 200-row cap"
    )
