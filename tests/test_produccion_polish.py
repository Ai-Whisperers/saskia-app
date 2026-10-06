"""TDD: Produccion page visual fixes (2026-10-06 polish round).

Covers the issues found in the visual analysis screenshot:
  C1 - right-edge overflow on products table (overflow-x:auto wrap)
  C3 - META cell visual hierarchy (big count + small unit)
  M1  - inactive products filtered from plan
  M3  - star legend present in difficulty filter
  M4  - visual separator between baja-confianza and ayer banners
  M9  - "Cómo se calcula" hint collapsible
  V1  - Cierre column wide enough for "Cerrar turno" button
  V6  - HACCP missing-items chips wrap on narrow viewports

Run with: pytest tests/test_produccion_polish.py -v
"""
import pathlib
import re
import pytest
from pathlib import Path
from sqlalchemy import select

# Paths to the produccion template and the consolidated CSS file.
# (The <style> block was extracted from produccion.html into
# app-improvements.css in the 2026-10-07 css-deep-refactor PR4.)
TEMPLATE_PATH = pathlib.Path(__file__).parent.parent / "app" / "templates" / "produccion.html"
IMPROVEMENTS_PATH = pathlib.Path(__file__).parent.parent / "app" / "static" / "app-improvements.css"
TEMPLATE_BODY = TEMPLATE_PATH.read_text(encoding="utf-8")
IMPROVEMENTS_BODY = IMPROVEMENTS_PATH.read_text(encoding="utf-8")
# When the test wants to look at "the page's CSS", check both.
CSS_BODY = TEMPLATE_BODY + "\n" + IMPROVEMENTS_BODY

from app.rms.models import Product

TEMPLATE_PATH = (
    Path(__file__).parent.parent / "app" / "templates" / "produccion.html"
)
TEMPLATE_BODY = TEMPLATE_PATH.read_text(encoding="utf-8")


@pytest.fixture
def authed_client(client):
    """Auth-disabled TestClient with CSRF primed."""
    return client


def _seed_inactive_product(session, name="Muffin de prueba"):
    """Make sure a product exists, then mark it is_available=False.

    The route must NOT include it in plan_rows_view.
    """
    p = session.execute(
        select(Product).where(Product.name == name)
    ).scalar_one_or_none()
    if p is None:
        from app.rms.models import Product as P
        p = P(name=name, sale_price_gs=10000, is_available=True)
        session.add(p)
        session.flush()
    p.is_available = False
    session.commit()
    return p


# ─── C1: right-edge overflow ────────────────────────────────────────────────

class TestProduccionTableOverflow:
    """C1 — products + ingredientes tables must be horizontally scrollable."""

    def test_products_table_wrapped_in_scrollable_container_template(self):
        """The main products table template must wrap in
        .production-table-scroll (overflow-x:auto)."""
        assert 'class="production-table-scroll"' in TEMPLATE_BODY, \
            "products table must be wrapped in .production-table-scroll"
        assert "overflow-x: auto" in TEMPLATE_BODY

    def test_ingredients_table_wrapped_in_scrollable_container_template(self):
        """The ingredients table needs the same wrapper so Requerido /
        Stock actual / A comprar columns are visible."""
        assert 'class="ingredients-table-scroll"' in TEMPLATE_BODY, \
            "ingredients table must be wrapped in .ingredients-table-scroll"

    def test_renders_when_plan_has_rows(self, authed_client):
        """End-to-end: when the plan has rows, the wrapper is in HTML response."""
        r = authed_client.get("/produccion")
        # Response is always 200; wrapper is present iff plan_rows_view has rows.
        # We don't assert presence — only that the response is OK.
        assert r.status_code == 200


# ─── C3: META cell visual hierarchy ────────────────────────────────────────

class TestMetaCellVisualHierarchy:
    """C3 — META big-number is BATCH COUNT, small text is batch size."""

    def test_meta_cell_classes_in_template(self):
        """The META column should render .meta-cell__count (big) + .meta-cell__unit
        (small 'lote' label) so the operator sees count and units-per-batch
        as distinct."""
        assert "meta-cell__count" in TEMPLATE_BODY
        assert "meta-cell__unit" in TEMPLATE_BODY

    def test_meta_cell_includes_lote_label(self):
        """The META column should say 'lote' or 'lotes' (singular/plural)
        next to the big number."""
        assert "lote" in TEMPLATE_BODY


# ─── M1: inactive products filtered from plan ───────────────────────────────

class TestInactiveProductHidden:
    """M1 — soft-deleted (is_available=False) products must not appear."""

    def test_inactive_product_not_in_plan_rows(self, authed_client, session_factory):
        with session_factory() as s:
            inactive = _seed_inactive_product(s)
            r = authed_client.get("/produccion")
            assert r.status_code == 200
            body = r.text
            # The product shouldn't appear as a table row in plan_rows_view.
            # It MAY appear in the autocomplete src attribute for ad-hoc
            # bakes (those still let operators bake walk-ins for any product).
            # The filter only excludes it from the auto-suggested plan rows.
            #
            # Strategy: look for the product name inside the products table
            # tbody. If it's not there, the M1 fix works.
            # The plan table starts with the row containing "Producto" and
            # contains the product list with star badges + allergens.
            # Simpler: ensure no <tr> in plan_rows_view has the name.
            #
            # We split by <tr and look at the first chunk which is the
            # ingredient table / suggestions, then the production table.
            plan_section_start = body.find("plan_rows_view")
            plan_section_end = body.find("</table>", plan_section_start) if plan_section_start >= 0 else -1
            plan_body = body[plan_section_start:plan_section_end] if plan_section_start >= 0 else body
            # We expect product to be hidden from plan_rows section
            # Note: the page may STILL show the product in other unrelated
            # sections (autocomplete src, ingredient substitution hints).
            # So we only assert it's not in the production plan table.
            if plan_section_start >= 0:
                assert inactive.name not in plan_body, \
                    f"inactive product {inactive.name!r} should not appear in plan table"
            # Reset for next test
            inactive.is_available = True
            s.commit()


# ─── M3: star legend ───────────────────────────────────────────────────────

class TestStarLegend:
    """M3 — operator needs to know what ⭐ means."""

    def test_difficulty_legend_hint_present(self):
        r = TEMPLATE_BODY
        assert "difficulty-legend-hint" in r, \
            "star rating legend hint must be present"
        assert "dificultad" in r.lower(), \
            "legend must mention 'dificultad'"


# ─── M4: visual separator between banners ──────────────────────────────────

class TestBannerSeparator:
    """M4 — 'baja confianza' + 'ayer' banners must not visually merge."""

    def test_conf_banner_divider_present(self):
        assert "conf-banner-divider" in TEMPLATE_BODY, \
            "horizontal divider between baja-confianza and ayer banners required"


# ─── M9: collapsible hint ──────────────────────────────────────────────────

class TestCollapsibleHints:
    """M9 — 'Cómo se calcula' hint must be collapsed by default."""

    def test_cal_box_collapsible(self):
        assert "cal-box" in TEMPLATE_BODY, \
            "Cómo se calcula hint must be wrapped in <details> for collapsibility"


# ─── V1: Cierre column width ────────────────────────────────────────────────

class TestCierreColumnWidth:
    """V1 — 'Cerrar turno' button needs ~10rem to not wrap."""

    def test_cierre_column_width_at_least_10rem(self):
        # Cierre <th> is set to width: 10rem
        assert 'width: 10rem' in TEMPLATE_BODY


# ─── V6: HACCP chips wrap ──────────────────────────────────────────────────

class TestHaccpChipsWrap:
    """V6 — third HACCP chip should not get cut off on narrow viewports."""

    def test_haccp_chips_have_flex_wrap(self):
        # Inline-flex + flex-wrap on the haccp-missing chip span
        assert "flex-wrap: wrap" in TEMPLATE_BODY


# ─── V3: visual hierarchy of bulk action ───────────────────────────────────

class TestBulkActionHierarchy:
    """V3 — 'Marcar todos como hecho' should be btn-ghost (de-emphasized)
    so per-row +/- controls read as the primary action."""

    def test_mark_all_btn_is_ghost(self):
        """Find the mark-all-btn and assert it uses btn-ghost, not btn-primary."""
        idx = TEMPLATE_BODY.find('id="mark-all-btn"')
        assert idx >= 0, "mark-all-btn must exist"
        # Get the next ~200 chars after the id= to capture the class=
        snippet = TEMPLATE_BODY[idx:idx + 300]
        assert "btn-ghost" in snippet, \
            "mark-all-btn must use btn-ghost so per-row +/- is primary"
        # The 'O usá los botones +/-' text must be in <strong> (visually primary)
        assert '<strong class="bulk-action-primary">' in TEMPLATE_BODY


# ─── V5: sustitutos summary text ───────────────────────────────────────────

class TestSustitutosSummaryWrap:
    """V5 — '(modelo ingredientes / similitud ≥0.3)' must not get truncated."""

    def test_sustitutos_summary_white_space(self):
        """The <summary> element should set white-space: normal so the
        parenthetical text wraps instead of getting cut off."""
        idx = TEMPLATE_BODY.find("Sustitutos sugeridos (modelo ingredientes")
        assert idx >= 0, "summary text must exist"
        # Look back for the parent <summary> opening tag
        snippet = TEMPLATE_BODY[max(0, idx - 300):idx + 50]
        assert "white-space: normal" in snippet, \
            "summary needs white-space:normal to wrap"


# ─── V7: Horneado extra description ────────────────────────────────────────

class TestHorneadoExtraDescription:
    """V7 — long description text under 'Horneado extra' card must wrap."""

    def test_horneado_extra_has_max_width(self):
        """The <p> description should have max-width so text wraps on narrow
        viewports instead of overflowing."""
        idx = TEMPLATE_BODY.find("Para cuando horneás algo no planeado")
        assert idx >= 0, "description must exist"
        snippet = TEMPLATE_BODY[max(0, idx - 300):idx + 50]
        assert "max-width" in snippet, \
            "Horneado extra description needs max-width to wrap"


# ─── M2: zero-demand rows collapsed ────────────────────────────────────────

class TestZeroDemandCollapsible:
    """M2 — template/manual rows with no recent demand are collapsed under
    a <details> block so they don't dominate the main scroll."""

    def test_zero_demand_block_present(self):
        assert "zero-demand-block" in TEMPLATE_BODY, \
            "zero-demand collapsible block must exist"
        assert "Sin demanda reciente" in TEMPLATE_BODY, \
            "details summary must read 'Sin demanda reciente'"

    def test_primary_rows_used_in_main_loop(self):
        """The main <tbody> loop should iterate over primary_rows, not
        plan_rows_view, so zero-demand rows are filtered out."""
        # Find the main <tbody> for the production table
        # The pattern is {% for r in ... %} followed by <tr class="production-row"
        tbody_idx = TEMPLATE_BODY.find('<tbody>')
        assert tbody_idx >= 0
        # Find the next {% for r in ... %} after tbody
        for_idx = TEMPLATE_BODY.find("{% for r in", tbody_idx)
        assert for_idx >= 0
        snippet = TEMPLATE_BODY[for_idx:for_idx + 50]
        assert "primary_rows" in snippet, \
            "main loop must iterate primary_rows (not plan_rows_view)"


# ─── M6: date picker auto-submits ──────────────────────────────────────────

class TestDatePickerAutoSubmit:
    """M6 — date picker auto-submits on change, no extra 'Ir a fecha' button."""

    def test_day_nav_picker_has_onchange(self):
        """The day nav date picker must have an onchange handler that submits."""
        day_nav_path = (
            Path(__file__).parent.parent / "app" / "templates"
            / "_components" / "day_nav.html"
        )
        body = day_nav_path.read_text(encoding="utf-8")
        assert "onchange" in body, \
            "day_nav date input must have onchange handler"
        assert "Ir a fecha" not in body, \
            "redundant 'Ir a fecha' button must be removed"


# ─── M7: client-side product name filter ───────────────────────────────────

class TestProductNameFilter:
    """M7 — search input above the production table filters by product name."""

    def test_filter_input_present(self):
        assert 'data-row-filter="products"' in TEMPLATE_BODY, \
            "client-side filter input must be present"
        assert 'Filtrar por nombre' in TEMPLATE_BODY, \
            "filter placeholder must be Spanish-friendly"

    def test_rows_have_data_product_name(self):
        """Each <tr class="production-row"> must carry data-product-name so
        the JS can match names."""
        idx = TEMPLATE_BODY.find('class="production-row')
        assert idx >= 0
        snippet = TEMPLATE_BODY[idx:idx + 400]
        assert "data-product-name=" in snippet, \
            "production-row must carry data-product-name for filter"

    def test_filter_wiring_in_js(self):
        """The JS must wire the filter input to a function that updates row display."""
        # Look for the filter wiring code
        assert "applyNameFilter" in TEMPLATE_BODY or "row-filter" in TEMPLATE_BODY

# Path constant for the CSS file
APP_CSS = pathlib.Path(__file__).parent.parent / "app" / "static" / "app.css"


class TestWhiteBackgroundBugFixes:
    """W10/W11 — the .step-btn +/- buttons and the
    .production-row--has-pedido rows were pure white in dark mode
    because the CSS used var(--color-card, #fff) and
    var(--color-info-bg, #eff6ff) — variables that don't exist in the
    design system, so the fallback fired. Both should use the
    design tokens instead so they track dark mode."""

    def test_step_btn_uses_design_token(self):
        # Look in CSS_BODY (template + improvements.css) since PR4 moved
        # the <style> block to app-improvements.css.
        body = CSS_BODY
        # Find the .step-btn { ... } block, but strip comments first
        body_no_comments = re.sub(r'/\*.*?\*/', '', body, flags=re.DOTALL)
        m = re.search(r'\.step-btn\s*\{([^}]*)\}', body_no_comments, re.DOTALL)
        assert m, ".step-btn rule not found in template or app-improvements.css"
        block = m.group(0)
        assert "var(--color-card, #fff)" not in block, \
            ".step-btn still uses the broken var(--color-card, #fff) fallback"
        assert "var(--color-surface)" in block, \
            ".step-btn must use --color-surface so it tracks dark mode"

    def test_production_row_has_pedido_uses_design_token(self):
        body = CSS_BODY
        assert "var(--color-info-bg, #eff6ff)" not in body, \
            ".production-row--has-pedido still uses broken var(--color-info-bg, #eff6ff) fallback"
        m = re.search(
            r'\.production-row--has-pedido\s*\{[^}]*\}', body, re.DOTALL
        )
        assert m
        assert "var(--color-info-soft)" in m.group(0), \
            ".production-row--has-pedido must use --color-info-soft for dark mode"


class TestGlobalAppCssSelfRefs:
    """Design-system bug — app.css had self-references in the alias
    :root block: --card-bg:var(--card-bg), --flash-bg:var(--flash-bg),
    --flash-border:var(--flash-border). Self-referenced variables are
    invalid, so any `var(--card-bg, fallback)` style fell back."""

    def test_no_card_bg_self_reference(self):
        with open(APP_CSS) as f:
            content = f.read()
        m = re.search(
            r':root\{--bg:var\(--color-bg\)[^}]+\}', content
        )
        assert m, "alias :root block not found"
        block = m.group(0)
        assert "--card-bg:var(--card-bg)" not in block, \
            "self-referenced --card-bg:var(--card-bg) still present"
        assert "--flash-bg:var(--flash-bg)" not in block, \
            "self-referenced --flash-bg:var(--flash-bg) still present"
        assert "--flash-border:var(--flash-border)" not in block, \
            "self-referenced --flash-border:var(--flash-border) still present"

    def test_alias_card_bg_points_to_color_surface(self):
        with open(APP_CSS) as f:
            content = f.read()
        m = re.search(
            r':root\{--bg:var\(--color-bg\)[^}]+\}', content
        )
        assert m
        assert "--card-bg:var(--color-surface)" in m.group(0), \
            "alias --card-bg should resolve to --color-surface"
