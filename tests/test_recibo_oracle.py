from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
GOLDEN_DIR = REPO / "tests" / "fixtures" / "recibo"
GOLDEN_FILE = GOLDEN_DIR / "golden_recibo_v1.html"

# Volatile parts of the rendered HTML that should NOT be pinned:
# - The exact byte sequence of the timestamp (varies by timezone)
# - The sale ID (auto-increments per test run; we always use id=1 in fixture)
# - Asset version querystrings (?v=...)
# - The "Impreso N vez(es)" counter (depends on test interaction)
VOLATILE_PATTERNS = [
    # Timestamps in the format "DD/MM/YYYY HH:MM" or "YYYY-MM-DD"
    (re.compile(r"\d{4}-\d{2}-\d{2}[T ]?\d{2}:\d{2}:\d{2}[Z+][\w:]*"), "<TS>"),
    (re.compile(r"\d{2}/\d{2}/\d{4}"), "<TS>"),
    (re.compile(r"\d{2}/\d{2}/\d{4} \d{2}:\d{2}"), "<TS>"),
    # The topbar date in Spanish: "miércoles 7 oct 2026 · 11:47" — captures
    # day-of-week + day + month-name + year + time. Localized format
    # means the regex must be permissive about the day name + month name.
    (re.compile(r"[a-záéíóúñ]+ \d{1,2} [a-záéíóúñ]+ \d{4} · \d{2}:\d{2}"), "<TOPBAR_TS>"),
    # The sale ID in the URL / receipt (e.g., /ventas/123/recibo or Recibo #123)
    (re.compile(r"/ventas/\d+/"), "<DT>/ventas/<ID>/"),
    (re.compile(r"Recibo #\d+"), "Recibo #<ID>"),
    # Asset versions on static files
    (re.compile(r"\?v=[a-f0-9]+"), "?v=<VER>"),
    # The print counter
    (re.compile(r"Impreso <span[^>]*>\d+</span>"), "Impreso <span><N></span>"),
    # Generated tokens / CSRF (the public_mode shows a token in the URL)
    (re.compile(r"/r/[a-zA-Z0-9_-]{16,}"), "<DT>/r/<TOKEN>"),
]


def normalize(html: str) -> str:
    """Apply VOLATILE_PATTERNS substitutions to the rendered HTML."""
    out = html
    for pattern, replacement in VOLATILE_PATTERNS:
        out = pattern.sub(replacement, out)
    out = "\n".join(line.rstrip() for line in out.split("\n"))
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out


@pytest.fixture
def recibo_sale_id(session_factory) -> int:
    """Seed a deterministic sale for the recibo oracle and return its id."""
    from app.rms.config import ASUNCION_TZ
    from app.rms.models import Product, Sale

    with session_factory() as s:
        p = Product(name="Torta", sku="TOR-ORACLE", sale_price_gs=10000, recipe_id=None)
        s.add(p)
        s.flush()
        sale = Sale(
            product_id=p.id,
            qty=1,
            unit_price_gs=10000,
            sold_at=datetime(2026, 10, 7, 12, 0, 0, tzinfo=ASUNCION_TZ),
            voided_at=None,
        )
        s.add(sale)
        s.commit()
        return sale.id


@pytest.fixture
def rendered_recibo_html(client, recibo_sale_id):
    """Render the recibo template via the live HTTP route."""
    resp = client.get(f"/ventas/{recibo_sale_id}/recibo")
    assert resp.status_code == 200, f"recibo route returned {resp.status_code}, expected 200"
    return resp.text


# ---- 1. Receipt renders without error ----------------------------------


def test_recibo_renders_200(rendered_recibo_html):
    """Floor: the HTTP route returns 200 and non-empty HTML."""
    assert rendered_recibo_html
    assert "<html" in rendered_recibo_html.lower()


# ---- 2. Golden fixture exists --------------------------------------------


def test_golden_fixture_file_exists():
    """The pinned golden fixture must exist on disk."""
    assert GOLDEN_FILE.exists(), (
        f"Golden fixture missing at {GOLDEN_FILE}. "
        f"Regenerate with: UPDATE_RECIBO_GOLDEN=1 uv run pytest "
        f"tests/test_recibo_oracle.py::test_recibo_matches_golden -v"
    )


# ---- 3. Golden fixture matches rendered HTML ----------------------------


def _diff(expected: str, actual: str) -> list[str]:
    """Line-by-line diff for the assertion message."""
    import difflib

    diff = difflib.unified_diff(
        expected.splitlines(),
        actual.splitlines(),
        fromfile="golden",
        tofile="actual",
        lineterm="",
    )
    return list(diff)


def test_recibo_matches_golden(rendered_recibo_html):
    """The rendered recibo must match the pinned golden fixture
    (after Volatile substitutions).

    On intentional format change:
    1. Make the template change
    2. Run `UPDATE_RECIBO_GOLDEN=1 uv run pytest tests/test_recibo_oracle.py::test_recibo_matches_golden -v`
    3. Commit template + golden together
    """
    actual = normalize(rendered_recibo_html)

    if os.environ.get("UPDATE_RECIBO_GOLDEN") == "1":
        # Regenerate mode: write the golden, skip the comparison.
        GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
        GOLDEN_FILE.write_text(actual, encoding="utf-8")
        pytest.skip(
            f"Wrote new golden ({len(actual)} bytes). "
            f"Re-run without UPDATE_RECIBO_GOLDEN to verify the comparison passes."
        )

    if not GOLDEN_FILE.exists():
        pytest.skip("Golden file missing — run with UPDATE_RECIBO_GOLDEN=1 to create it")

    golden = GOLDEN_FILE.read_text(encoding="utf-8")
    expected = normalize(golden)

    if actual != expected:
        actual_path = GOLDEN_DIR / "_actual.html"
        actual_path.write_text(actual, encoding="utf-8")
        diff_lines = _diff(expected, actual)
        assert False, (
            f"Receipt rendered differently than the golden fixture.\n"
            f"Expected: {GOLDEN_FILE}\n"
            f"Actual:   {actual_path} (also written to disk for diff)\n"
            f"Diff (first 30 lines):\n" + "\n".join(diff_lines[:30])
        )


# ---- 4. Required sections present in the rendered HTML -------------------


@pytest.mark.parametrize(
    "required_substring",
    [
        "Sazón",
        "Venta",
        "Número",
        "Fecha",
        "Torta",
        "¡Gracias por tu compra!",
        "Este recibo no es un comprobante fiscal.",
    ],
)
def test_recibo_contains_required_sections(rendered_recibo_html, required_substring):
    """Sanity: the rendered receipt must contain brand, metadata,
    product name, and standard footer."""
    assert required_substring in rendered_recibo_html, (
        f"Recibo missing required section: '{required_substring}'. "
        f"This is a regression from the standard receipt format."
    )


# ---- 5. No accidental voids banner in non-voided sale ------------------


def test_recibo_no_void_banner_for_active_sale(rendered_recibo_html):
    """The voided banner ('ANULADO') must NOT appear in a non-voided sale."""
    assert "ANULADO" not in rendered_recibo_html.upper(), (
        "Active sale shows 'ANULADO' banner — the void banner is appearing in the wrong condition."
    )


# ---- 6. Receipt is print-optimized (no nav in print mode) --------------


def test_recibo_uses_print_stylesheet_navigation_hiding():
    """The receipt template uses the app.css print stylesheet, which
    hides .topnav, .nav-right, etc. when printing.
    """
    app_css = (REPO / "app" / "static" / "app.css").read_text(encoding="utf-8")
    assert "@media print" in app_css, "app.css has no @media print block"
    print_blocks = re.findall(
        r"@media print\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}",
        app_css,
        re.DOTALL,
    )
    found_topnav_hide = any(".topnav" in block and "none" in block for block in print_blocks)
    assert found_topnav_hide, (
        "@media print in app.css does not hide .topnav. "
        "Operator's printed receipt will show the navigation chrome."
    )


# ---- 7. CSS oracle — column-width stability ----------------------------


def test_recibo_container_max_width_is_reasonable_for_thermal():
    """The receipt's outer container caps max-width at 360px (80mm
    thermal printer width including margins). If this changes, the
    receipt won't fit on a thermal printer.
    """
    template = (REPO / "app" / "templates" / "recibo.html").read_text(encoding="utf-8")
    m = re.search(r"max-width:\s*(\d+)px", template)
    assert m, (
        "recibo.html has no max-width:NNNpx rule. "
        "A printed receipt without an explicit width could overflow."
    )
    width = int(m.group(1))
    assert 300 <= width <= 400, (
        f"recibo.html max-width is {width}px; expected 300-400px "
        f"to fit an 80mm thermal printer. Update this assertion "
        f"if you intentionally changed the format."
    )
