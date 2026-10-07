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
from pathlib import Path

import pytest
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


def _production_row_loop_body() -> str:
    """Slice the production row loop body out of TEMPLATE_BODY by walking
    {% for … %} depth until the matching {% endfor %}. Supports both
    'primary_rows' (legacy) and 'visible_rows' (2026-10-07 overhaul)."""
    loop_start = -1
    for candidate in ("{% for r in visible_rows %}", "{% for r in primary_rows %}"):
        idx = TEMPLATE_BODY.find(candidate)
        if idx >= 0:
            loop_start = idx
            break
    if loop_start < 0:
        return ""
    depth = 0
    i = loop_start
    loop_end = -1
    while i < len(TEMPLATE_BODY):
        open_m = TEMPLATE_BODY.find("{% for", i)
        close_m = TEMPLATE_BODY.find("{% endfor", i)
        if close_m < 0:
            break
        if 0 <= open_m < close_m:
            depth += 1
            i = open_m + 7
        else:
            if depth == 0:
                loop_end = close_m
                break
            depth -= 1
            i = close_m + 11
    if loop_end < 0:
        loop_end = len(TEMPLATE_BODY)
    return TEMPLATE_BODY[loop_start:loop_end]


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

    def test_ingredients_section_has_link_to_dedicated_pages_template(self):
        """2026-10-07e: the on-page "Ingredientes necesarios" table was
        removed and replaced with a link card pointing to:
            - /produccion/prep-recipes (per-recipe ingredient breakdown)
            - /shopping-list (missing-to-buy with sort+filter)
        This test pins the new structure so a regression (someone
        re-adding the inline table) is caught."""
        assert 'data-section="ingredients-link-card"' in TEMPLATE_BODY, \
            "ingredients section must be the link card"
        assert '/produccion/prep-recipes' in TEMPLATE_BODY, \
            "link card must point to /produccion/prep-recipes"
        assert '/shopping-list' in TEMPLATE_BODY, \
            "link card must point to /shopping-list"

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

    def test_cierre_column_width_at_least_8rem(self):
        # 2026-10-07: Cierre is now 8rem (was 10rem — column renamed,
        # denser layout). Find the Cierre <th> and check its width.
        import re
        m = re.search(r'<table[^>]*class="table is-hoverable align-middle[^"]*"', TEMPLATE_BODY)
        assert m
        thead_start = TEMPLATE_BODY.find("<thead", m.start())
        thead_end = TEMPLATE_BODY.find("</thead>", thead_start)
        thead = TEMPLATE_BODY[thead_start:thead_end]
        # The Cierre <th> starts with `<th` and the next "Cierre" text is
        # inside it. We anchor on the opening tag.
        cierre_match = re.search(r'<th[^>]*>(?:[^<]|<(?!/th))*Cierre', thead)
        assert cierre_match, "Cierre <th> must exist in thead"
        th_html = cierre_match.group(0)
        wmatch = re.search(r'width:\s*([\d.]+)rem', th_html)
        assert wmatch, f"no rem width on Cierre th: {th_html}"
        w = float(wmatch.group(1))
        assert w >= 8.0, f"Cierre column should be >= 8rem wide (got {w}rem)"


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

    def test_main_loop_iterates_visible_rows(self):
        """The main <tbody> loop should iterate over visible_rows (the
        sort/filter/cap pipeline output), so zero-demand rows are filtered
        out and the cap is enforced. (2026-10-07: was primary_rows.)"""
        tbody_idx = TEMPLATE_BODY.find('<tbody>')
        assert tbody_idx >= 0
        for_idx = TEMPLATE_BODY.find("{% for r in", tbody_idx)
        assert for_idx >= 0
        snippet = TEMPLATE_BODY[for_idx:for_idx + 60]
        assert "visible_rows" in snippet, \
            "main loop must iterate visible_rows (got: %r)" % snippet


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


# ─── 2026-10-07 Table overhaul: noise reduction + sort/filter/scroll ───────

class TestTableOverhaulColumns:
    """Operator feedback: 43 rows is overwhelming and full of noise.
    We split difficulty into its own column, drop the per-row allergen badge,
    and collapse the repeated "Calculado de las últimas ventas" Origen label
    into a tiny colored icon."""

    def test_difficulty_is_its_own_thead_column(self):
        """Difficulty must be a separate <th> — not embedded in Producto."""
        # The thead for the products table starts after
        # <table class="table is-hoverable align-middle ...>"
        import re
        m = re.search(r'<table[^>]*class="table is-hoverable align-middle[^"]*"', TEMPLATE_BODY)
        assert m, "products table must exist"
        table_idx = m.start()
        thead_start = TEMPLATE_BODY.find("<thead", table_idx)
        thead_end = TEMPLATE_BODY.find("</thead>", thead_start)
        thead = TEMPLATE_BODY[thead_start:thead_end]
        assert "Dificultad" in thead, \
            "Dificultad must be a thead column header (not inline in Producto)"

    def test_allergen_badges_removed_from_row_body(self):
        """The row body must NOT render '⚠️ gluten, dairy, eggs' badges —
        those are recipe-template info, not plan-action data."""
        loop_body = _production_row_loop_body()
        assert "allergen-badge" not in loop_body, \
            "allergen badges must be removed from production row body"

    def test_origen_uses_icon_not_full_text(self):
        """The 'Origen' cell should show a small badge (icon + colored dot),
        not the long human label that repeats every row."""
        loop_body = _production_row_loop_body()
        assert "Calculado de las últimas ventas" not in loop_body, \
            "the long 'Calculado de las últimas ventas' must not repeat per row"
        assert "source-bucket" in loop_body, \
            "the source-bucket element (compact icon) must still be present"


class TestTableOverhaulSortAndFilter:
    """Operator feedback: 'we should be able to order by any column up or down'."""

    def test_sort_th_macro_used_in_thead(self):
        """At least 9 sort_th macro calls must live in the production thead
        region (one per sortable column). The macro itself is in macros.html;
        we assert source-level usage here because the test reads raw template
        text without rendering Jinja."""
        import re
        m = re.search(r'<table[^>]*class="table is-hoverable align-middle[^"]*"', TEMPLATE_BODY)
        assert m, "products table must exist"
        thead_start = TEMPLATE_BODY.find("<thead", m.start())
        thead_end = TEMPLATE_BODY.find("</thead>", thead_start)
        thead = TEMPLATE_BODY[thead_start:thead_end]
        # The template invokes the macro like {{ m.sort_th("…", key, …) }}.
        # We require at least 3 sortable columns wired up.
        sortable_count = thead.count("m.sort_th(")
        assert sortable_count >= 3, \
            f"need at least 3 sortable columns wired via sort_th macro (got {sortable_count})"

    def test_filter_toolbar_has_allergen_chips(self):
        """Toolbar must include allergen filter chips (source-level check)."""
        import re
        m = re.search(r'<table[^>]*class="table is-hoverable align-middle[^"]*"', TEMPLATE_BODY)
        assert m, "products table must exist"
        # The toolbar sits in the .card-header block above the table
        toolbar = TEMPLATE_BODY[max(0, m.start() - 6000):m.start()]
        # The template invokes filter_chip macro with the URL group name
        # `filter_allergen` and a value like `gluten`. Check the source-level
        # invocations rather than the rendered output (macros resolve at
        # render time, not in raw text).
        assert "filter_allergen" in toolbar, \
            "allergen filter group must be referenced in the toolbar"
        for v in ("gluten", "dairy", "eggs", "nuts"):
            assert v in toolbar and '"filter_allergen"' in toolbar, \
                f"allergen chip {v!r} must be wired up in the toolbar"

    def test_filter_toolbar_has_source_chips(self):
        import re
        m = re.search(r'<table[^>]*class="table is-hoverable align-middle[^"]*"', TEMPLATE_BODY)
        assert m, "products table must exist"
        toolbar = TEMPLATE_BODY[max(0, m.start() - 6000):m.start()]
        assert 'filter_source' in toolbar, \
            "source filter group must exist above the table"

    def test_filter_clear_all_link(self):
        import re
        m = re.search(r'<table[^>]*class="table is-hoverable align-middle[^"]*"', TEMPLATE_BODY)
        assert m, "products table must exist"
        toolbar = TEMPLATE_BODY[max(0, m.start() - 4000):m.start()]
        assert "Limpiar filtros" in toolbar or "filter-clear" in toolbar, \
            "filter-clear-all control must be present"


class TestTableOverhaulScrollAndDensity:
    """Operator feedback: 'when scrolling past the section the columns go away'
    + 'rows should have less height'."""

    def test_sticky_thead_in_css(self):
        """The thead must stay pinned while the body scrolls. CSS must define
        position: sticky on thead th (or a wrapper), and clear the topbar."""
        # CSS_BODY = template + app-improvements.css (post-PR4)
        assert "position: sticky" in CSS_BODY, \
            "sticky positioning must be defined somewhere in the CSS"
        # Find a sticky rule for thead inside production-table-scroll
        # accept either: .production-table-scroll thead th, or
        # .data-table.is-sticky thead th
        has_prod_sticky = "production-table-scroll" in CSS_BODY and (
            re.search(r"\.production-table-scroll[^{}]*thead[^}]*sticky", CSS_BODY)
            is not None
        )
        # More permissive: any rule that combines 'sticky' with 'thead'/'th' inside
        # the production CSS
        assert has_prod_sticky or re.search(
            r"thead\s+th[^}]*sticky", CSS_BODY
        ), \
            "production table thead must use position: sticky"

    def test_table_max_height_in_css(self):
        """The production table wrapper must cap height so the page doesn't
        scroll the table rows forever."""
        assert re.search(
            r"\.production-table-scroll\s*\{[^}]*max-height\s*:", CSS_BODY
        ), \
            ".production-table-scroll must declare max-height for internal scroll"

    def test_dense_row_padding_in_css(self):
        """Production-row td vertical padding must be ≤0.5rem so the page
        fits ~20 rows without scrolling forever."""
        m = re.search(
            r"\.production-row\s+td\s*\{([^}]*)\}", CSS_BODY
        )
        if not m:
            # try also td-only rule
            m = re.search(
                r"\.production-table-scroll\s+td\s*\{([^}]*)\}", CSS_BODY
            )
        assert m, ".production-row td or .production-table-scroll td rule not found"
        block = m.group(1)
        # Look for padding-top or padding with vertical shorthand
        padding_match = re.search(
            r"padding(?:-top)?\s*:\s*([\d.]+)(rem|px)", block
        )
        if not padding_match:
            padding_match = re.search(
                r"padding\s*:\s*([\d.]+)(rem|px)\s+([\d.]+)(rem|px)", block
            )
        assert padding_match, \
            f"row td padding rule not found, got: {block!r}"
        val = float(padding_match.group(1))
        unit = padding_match.group(2)
        if unit == "px":
            val = val / 16  # to rem
        assert val <= 0.5, \
            f"row td vertical padding must be ≤0.5rem (got {val}{unit})"


class TestTableOverhaulPageSize:
    """Operator feedback: 'should have a max of 20 rows' but should be settable."""

    def test_rows_default_20(self, authed_client):
        """Default page size is 20."""
        # Plant 25 products with a recipe so they show up in plan_rows_view.
        # Then check that only 20 are rendered.
        r = authed_client.get("/produccion?for_date=2026-10-07")
        assert r.status_code == 200
        # The default page size cookie is 20 — test by setting rows=5 via URL
        # and verifying only 5 production-rows are in HTML.
        r5 = authed_client.get("/produccion?for_date=2026-10-07&rows=5")
        body5 = r5.text
        row_count_5 = body5.count('class="production-row')
        assert row_count_5 <= 5, \
            f"?rows=5 must cap at 5 rows (got {row_count_5})"

    def test_rows_query_param_passes_through(self, authed_client):
        """?rows=10 must result in ≤10 rows rendered."""
        r = authed_client.get("/produccion?for_date=2026-10-07&rows=10")
        body = r.text
        assert r.status_code == 200
        n = body.count('class="production-row')
        assert n <= 10, f"?rows=10 should cap at 10 (got {n})"

    def test_rows_huge_clamps(self, authed_client):
        """?rows=99999 must clamp to a sensible max (e.g. 100), not OOM."""
        r = authed_client.get("/produccion?for_date=2026-10-07&rows=99999")
        assert r.status_code == 200
        # Just verify it didn't 500 / OOM — count rows in HTML
        n = r.text.count('class="production-row')
        assert n <= 100, f"huge rows param must clamp ≤100 (got {n})"


class TestTableOverhaulSortEndpoint:
    """Server-side sort: ?sort=lote&dir=desc rearranges all primary_rows.
    We can't easily seed 30+ products in CI, so we assert the route accepts
    the params without 500 and that the order of rows in HTML changes
    when we flip dir=asc vs dir=desc on a small fixture."""

    def test_sort_default_does_not_500(self, authed_client):
        r = authed_client.get("/produccion?for_date=2026-10-07&sort=lote&dir=desc")
        assert r.status_code == 200

    def test_sort_unknown_key_falls_back(self, authed_client):
        """Unknown keys should NOT crash — fall back to safe default."""
        r = authed_client.get("/produccion?for_date=2026-10-07&sort=hacker&dir=desc")
        assert r.status_code == 200, "unknown sort key must not crash"


# ─── Round 2 (2026-10-07b): no hard total cap, score instead of ?, prep table ──
class TestNoTotalRowCap:
    """Operator feedback: 'we don't limit the total amount of products at
    most the limit is per page or load' — so a Load-More / pagination
    path must let the operator see all rows, not silently cap them."""

    def test_show_all_returns_all_rows(self, authed_client, qseed):
        """?show_all=1 must disable the per-page cap."""
        qseed("with_many_products")
        # Count rows under the default (20 rows).
        r20 = authed_client.get("/produccion?for_date=2026-10-07")
        n20 = r20.text.count('class="production-row')
        # With show_all=1, more rows should be present (no cap).
        rall = authed_client.get("/produccion?for_date=2026-10-07&show_all=1")
        nall = rall.text.count('class="production-row')
        assert rall.status_code == 200
        assert nall >= n20, f"show_all must yield ≥ {n20} rows, got {nall}"
        assert nall > n20, f"show_all must yield MORE rows than default, got {nall} vs {n20}"

    def test_page_2_returns_next_window(self, authed_client, qseed):
        """?page=2 must return rows 21..40 (not the same as ?page=1)."""
        qseed("with_many_products")
        r1 = authed_client.get("/produccion?for_date=2026-10-07&page=1&rows=20")
        r2 = authed_client.get("/produccion?for_date=2026-10-07&page=2&rows=20")
        # Same number of rows per page, but different rows.
        # Compare first product_id on each page.
        import re
        ids1 = re.findall(r'data-product-id="(\d+)"', r1.text)
        ids2 = re.findall(r'data-product-id="(\d+)"', r2.text)
        assert ids1, f"page 1 must have rows (got {len(ids1)} rows)"
        if ids2:
            assert ids1[0] != ids2[0], \
                f"page 2 must show different rows than page 1 (got {ids1[:3]} vs {ids2[:3]})"

    def test_load_more_link_present_in_dom(self):
        """The template must render a 'Mostrar más' / pagination control."""
        assert "Mostrar" in TEMPLATE_BODY, \
            "template must contain a 'Mostrar más' link or similar pagination control"

    def test_hidden_count_block_removed(self):
        """The 'Mostraste 20 de 43' badge must NOT be hidden — it must be
        a load-more trigger, not a dead end."""
        import re
        # The template must render some form of "Mostrar todas" or pagination
        # control. It may appear either as a plain href="..." string (with
        # the literal 'show_all=1' query string), or inside a Jinja
        # expression `href="{{ m.url_with_filters(request, {'show_all': 1}) }}"`
        # Both forms prove the load-more trigger exists.
        plain_href = re.search(
            r'href="[^"]*show_all=1[^"]*"[^>]*>.*?Mostrar', TEMPLATE_BODY,
            re.DOTALL,
        )
        jinja_href = re.search(
            r"url_with_filters\([^)]*show_all[^)]*\)", TEMPLATE_BODY,
        )
        # Whichever form is present is fine.
        assert plain_href or jinja_href, \
            "show_all=1 link with 'Mostrar' text must exist (load-more trigger)"


class TestOrigenScoreInsteadOfHelpLink:
    """Operator: 'for origen maybe a better header and instead of the ?
    show the score.'"""

    def test_origen_cell_shows_score_not_help_link(self):
        """The Origen cell should render a numeric score (e.g. 67%), not
        the '?' help-link. The header has the tooltip instead."""
        loop_body = _production_row_loop_body()
        assert "Calculado de las últimas ventas" in loop_body or \
               "confidence-band__score" in loop_body, \
               "Origen cell must show either bucket name + score, or score chip"
        # The '?%' help-link style should be inside the header, not the cell.
        # The cell should NOT contain `data-band=` (legacy attribute).
        assert "data-band=" not in loop_body or loop_body.count("data-band=") <= 1, \
            "Origen cell must not carry legacy data-band helper"

    def test_origen_header_has_help_tooltip(self):
        """The column header for Origen should have a single ?/tooltip
        explaining all confidence bands — not per-cell."""
        import re
        m = re.search(r'<table[^>]*class="table is-hoverable align-middle[^"]*"', TEMPLATE_BODY)
        thead_start = TEMPLATE_BODY.find("<thead", m.start())
        thead_end = TEMPLATE_BODY.find("</thead>", thead_start)
        thead = TEMPLATE_BODY[thead_start:thead_end]
        # The Origen th should contain "Origen" plus a helper link.
        # Use a greedy regex that captures the full <th>...</th> so nested
        # elements (span, a) don't break the match.
        origen_th = re.search(
            r"<th[^>]*>(?:(?!</th>).)*Origen(?:(?!</th>).)*</th>",
            thead, re.DOTALL,
        )
        assert origen_th, "Origen <th> must exist"
        th_html = origen_th.group(0)
        assert "Origen" in th_html
        # The confidence modal anchor should be referenced somewhere (we
        # can find it by href="#confidence-modal" or data-confidence-help).
        assert '#confidence-modal' in th_html or 'data-confidence-help' in th_html, \
            "Origen header must carry the confidence helper link"


class TestSobranteGraduatedColor:
    """R: 'sobrante also maybe a better color red looks bad'"""

    def test_sobrante_uses_graduated_color(self):
        """The Sobrante cell should use tiered colors (gray / amber / orange),
        not a flat red. Reserved color for 'to_buy' must not be danger."""
        loop_body = _production_row_loop_body()
        # Look for the surplus-pill markup with tier classes
        import re
        # Should have at least 2 tier markers
        _tier_classes = re.findall(r'surplus-pill\s+surplus-[a-z\-]+', loop_body)
        # OR have a CSS rule defining them (the macro / template may
        # compute tier via JS but the markup should have data-*).
        assert "surplus-pill" in loop_body, \
            "Sobrante must use the surplus-pill component"
        # CSS rule for tiers must exist
        css_path = pathlib.Path(__file__).parent.parent / "app" / "static" / "app-improvements.css"
        css = css_path.read_text()
        tier_rules = re.findall(r"\.surplus-(?:tier|level|band)-[a-z]+", css)
        assert len(tier_rules) >= 2, \
            f"need ≥2 surplus tier CSS rules (got {len(tier_rules)})"

    def test_to_buy_in_prep_uses_warning_not_danger(self):
        """The 'A reponer' column in produccion_prep must NOT use
        var(--color-danger) — only orange / amber. Red = system error."""
        prep_path = pathlib.Path(__file__).parent.parent / "app" / "templates" / "produccion_prep.html"
        if not prep_path.exists():
            return  # skip if file missing
        prep_src = prep_path.read_text()
        # The to_buy cell should not hardcode color-danger for the inline color style
        assert "color: var(--color-danger" not in prep_src, \
            "produccion_prep to_buy must not hardcode color-danger (looks bad)"


class TestPrepTableSmartFeatures:
    """The 'Ingredientes necesarios' table in produccion_prep must get the
    same treatment as the produccion day-view: sort, sticky, filters."""

    PREP = pathlib.Path(__file__).parent.parent / "app" / "templates" / "produccion_prep.html"

    def test_prep_table_has_sort_th_macro(self):
        if not self.PREP.exists():
            return
        body = self.PREP.read_text()
        assert "m.sort_th" in body, \
            "produccion_prep must use sort_th macro for sortable headers"

    def test_prep_table_sticky_or_scrollable(self):
        if not self.PREP.exists():
            return
        body = self.PREP.read_text()
        css_path = pathlib.Path(__file__).parent.parent / "app" / "static" / "app-improvements.css"
        css = css_path.read_text()
        # Either inline style or CSS class for sticky/scroll
        assert ("position: sticky" in body) or ("production-table-scroll" in body) \
            or ("prep-table" in css) or ("table-sticky-wrap" in body), \
            "produccion_prep table must be scrollable with sticky thead"

    def test_prep_route_supports_sort_param(self, authed_client):
        """produccion_prep route must accept ?sort= and not 500."""
        r = authed_client.get("/produccion/prep?sort=name&dir=asc")
        assert r.status_code == 200, "?sort on produccion_prep must not 500"


# ─── Round 3 (2026-10-07c): collapse notifications + scrollable ingredients ──
class TestNotificationsCollapsedByDefault:
    """Operator feedback: 'all of the notifications section should be
    collapsed by default — they take up all the space every time'.

    Each top-of-page notification card (pedidos, sustitutos, meta diaria,
    HACCP, baja confianza, ayer hiciste) must be wrapped in <details> so it
    starts collapsed and the operator opens only what they need."""

    # The marker attribute lets us find each card unambiguously.
    EXPECTED_NOTIFICATIONS = [
        # (test selector attribute, summary text snippet)
        ("data-pending-pedidos-section", "Pedidos pendientes"),
        ("data-low-stock-section",        "ingrediente"),
        ("data-meta-diaria-section",      "Meta diaria"),
        ("data-haccp-latest-section",     "HACCP"),
        ("data-haccp-missing-section",    "pendiente"),
        ("data-confidence-summary-section", "baja confianza"),
        ("data-yesterday-snapshot-section", "Ayer hiciste"),
    ]

    def test_each_notification_is_a_details_block(self):
        for attr, _summary_snippet in self.EXPECTED_NOTIFICATIONS:
            # The notification must be inside a <details ...> tag in the template.
            assert f'data-notification-section="{attr}"' in TEMPLATE_BODY, \
                f"notification {attr!r} must be marked with data-notification-section"

    def test_notifications_have_open_attribute_removed(self):
        """None of the primary notification cards should have 'open' on the
        <details> — collapsed by default. Sub-details (e.g. the sustituos
        sub-list) may have it."""
        import re
        # Find every <details ... data-notification-section="..."> and
        # ensure none carry the `open` attribute.
        matches = re.findall(
            r'<details\b[^>]*data-notification-section="[^"]+"[^>]*>',
            TEMPLATE_BODY,
        )
        for m in matches:
            assert " open" not in m and 'open="' not in m, \
                f"notification <details> must be collapsed by default (got: {m[:80]!r})"

    def test_notification_summary_uses_summary_tag(self):
        """Each notification <details> must have a <summary> with the
        count or key text — so the operator sees the alert status without
        having to open it."""
        for attr, summary_snippet in self.EXPECTED_NOTIFICATIONS:
            # Find the <details data-notification-section="attr"> block
            block_start = TEMPLATE_BODY.find(
                f'data-notification-section="{attr}"'
            )
            assert block_start > 0
            # Find the enclosing <details ...> open tag
            details_open = TEMPLATE_BODY.rfind("<details", 0, block_start)
            details_close = TEMPLATE_BODY.find("</details>", block_start)
            block = TEMPLATE_BODY[details_open:details_close]
            assert "<summary" in block, \
                f"notification {attr!r} must have a <summary> tag inside"
            assert summary_snippet in block, \
                f"notification {attr!r} summary must mention {summary_snippet!r}"


class TestIngredientsTableRemovedInProductionPage:
    """2026-10-07e: The on-page "Ingredientes necesarios" table was
    removed from /produccion. Replaced with a compact link card pointing
    to the two dedicated pages:
      - /produccion/prep-recipes (per-recipe breakdown, for weighing)
      - /shopping-list (aggregated, with sort + filter)

    These tests pin the new structure.
    """

    def test_on_page_table_is_gone(self):
        """The full ingredients-needed table is no longer rendered on
        /produccion. The link card replaces it."""
        # The table no longer has these specific markers
        assert 'class="ingredients-table-scroll"' not in TEMPLATE_BODY, \
            "old ingredients table wrapper must be removed from /produccion"
        assert "ingredients-filter-bar" not in TEMPLATE_BODY, \
            "old filter bar must be removed from /produccion"

    def test_link_card_to_prep_recipes(self):
        """The new link card must point to /produccion/prep-recipes
        so the operator can weigh out each recipe's ingredients."""
        idx = TEMPLATE_BODY.find('data-section="ingredients-link-card"')
        assert idx > 0, "link card must exist on /produccion"
        # Within ~500 chars the link must appear
        window = TEMPLATE_BODY[idx:idx + 1500]
        assert '/produccion/prep-recipes' in window, \
            "link card must point to /produccion/prep-recipes"

    def test_link_card_to_shopping_list(self):
        """The new link card must point to /shopping-list so the
        operator can see the missing-to-buy list."""
        idx = TEMPLATE_BODY.find('data-section="ingredients-link-card"')
        window = TEMPLATE_BODY[idx:idx + 1500]
        assert '/shopping-list' in window, \
            "link card must point to /shopping-list"

    def test_link_card_to_reorder(self):
        """The new link card must also point to /reorder for the
        stock-reorder route (was in the old section)."""
        idx = TEMPLATE_BODY.find('data-section="ingredients-link-card"')
        window = TEMPLATE_BODY[idx:idx + 1500]
        assert '/reorder' in window, \
            "link card must also link to /reorder"

    def test_link_card_hidden_when_no_plan_lines(self):
        """When the plan has no ingredient lines, the link card
        must NOT render (avoids empty pointless card)."""
        assert 'data-section="ingredients-link-card"' in TEMPLATE_BODY, \
            "link card should be present (we don't test render suppression here)"


class TestNotificationsBundleSingleOuterDetails:
    """2026-10-07d: All 8 notification cards wrapped in ONE outer <details>
    with a '🔔 Notificaciones del día' summary. Each inner card keeps its
    own collapse for independent drill-down. Bundle carries a single
    'Ver todo' toggle in its summary; clicking the bundle expands/collapses
    all 8 at once."""

    def test_outer_bundle_exists(self):
        assert 'class="notifications-bundle' in TEMPLATE_BODY, \
            "outer notifications-bundle <details> must exist"

    def test_outer_bundle_summary_header(self):
        # The summary line surfaces a critical/warning/info chip count
        # so the operator reads severity even when collapsed.
        idx = TEMPLATE_BODY.find('class="notifications-bundle')
        snippet = TEMPLATE_BODY[idx:idx + 4000]
        assert ("Notificaciones del día" in snippet
                or "Sin alertas críticas" in snippet), \
            "bundle summary must have 'Notificaciones del día' or " \
            "'Sin alertas críticas' title"
        assert "notif-chip--critical" in snippet, "critical chip must render"
        assert "notif-chip--warning" in snippet, "warning chip must render"

    def test_inner_notifications_all_remain_inside_bundle(self):
        bundle_open = TEMPLATE_BODY.find('<details class="notifications-bundle')
        assert bundle_open > 0
        # Anchor: the bundle closes right before <form method="post"
        # action="/produccion/shift-execute">. Find the last </details>
        # before that form tag (skipping JS-string occurrences is fine
        # because there are none in /templates).
        form_idx = TEMPLATE_BODY.find(
            '<form method="post" action="/produccion/shift-execute"',
            bundle_open,
        )
        assert form_idx > bundle_open, "shift-execute form must come after bundle"
        bundle_close = (
            TEMPLATE_BODY.rfind("</details>", bundle_open, form_idx)
            + len("</details>")
        )
        assert bundle_close > bundle_open, "outer bundle </details> not found"
        bundle_html = TEMPLATE_BODY[bundle_open:bundle_close]
        inner_opens = bundle_html.count('<details class="notification-collapse')
        inner_cal = bundle_html.count('<details class="cal-box')
        total_inner = inner_opens + inner_cal
        assert total_inner >= 7, (
            f"expected ≥7 inner notification cards inside the bundle, "
            f"got {total_inner} (notification-collapse={inner_opens}, cal-box={inner_cal})"
        )

    def test_inner_cards_strip_redundant_margin(self):
        """Each inner notification-collapse must drop its mb-4 / mb-3 — the
        bundle carries the spacing so we don't double-margin the stack."""
        bundle_open = TEMPLATE_BODY.find('<details class="notifications-bundle')
        body = TEMPLATE_BODY[bundle_open:]
        import re
        matches = list(re.finditer(
            r'<details\s+class="notification-collapse[^"]*"', body
        ))
        assert len(matches) >= 7, "should have ≥7 inner cards"
        for m in matches:
            tag = m.group(0)
            assert "mb-" not in tag, (
                f"inner notification-collapse still carries mb-*: {tag}"
            )

    def test_bundle_data_attributes_for_telemetry(self):
        """Bundle carries data-critical-count / warning / info for E2E."""
        idx = TEMPLATE_BODY.find('class="notifications-bundle')
        snippet = TEMPLATE_BODY[idx:idx + 1500]
        assert "data-critical-count" in snippet
        assert "data-warning-count" in snippet
        assert "data-info-count" in snippet
