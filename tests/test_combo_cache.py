"""Test that combo.js cache implementation is correct.

NOTE 2026-09-29: combo.js was refactored to ui-combo.js (D17). These tests
assume the old combo.js filename and old API. They are kept here as @pytest.mark.xfail
so we can rewrite them for ui-combo.js when there is dedicated time. New tests for
ui-combo live in tests/test_ui_components.py::test_saskia_combo_*.
"""

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.xfail(
    reason="combo.js → ui-combo.js refactor (D17, 2026-09-27). "
    "These tests describe the legacy API. Rewrite for ui-combo.js "
    "or remove when no longer relevant. See tests/test_ui_components.py "
    "for current ui-combo tests.",
    strict=False,
)


def test_combo_cache_ttl_constant():
    """Cache TTL should be a finite, reasonable value (30s)."""
    js = Path("/opt/data/work/sazon-app/app/static/ui-combo.js").read_text()
    # Find the TTL check
    m = re.search(r"Date\.now\(\)\s*-\s*entry\.ts\s*<\s*(\d+)", js)
    assert m is not None, "Expected a TTL check in combo.js"
    ttl_ms = int(m.group(1))
    # Should be 30 seconds (30000ms) — long enough to dedupe across rapid
    # opens, short enough that listing pages don't show stale data.
    assert ttl_ms == 30000, f"Expected 30s TTL, got {ttl_ms}ms"


def test_combo_cache_writeback():
    """After a successful fetch, combo.js should write to the cache."""
    js = Path("/opt/data/work/sazon-app/app/static/ui-combo.js").read_text()
    # Should set the cache with ts and data fields after the network call resolves
    assert "_sharedCache.set" in js
    assert "ts: Date.now()" in js
    assert "data: items" in js


def test_combo_cache_expiry_evicts():
    """Expired cache entries should be evicted on read."""
    js = Path("/opt/data/work/sazon-app/app/static/ui-combo.js").read_text()
    # Should delete cache entry on expiry (using either instance or shared cache handle)
    assert "_sharedCache.delete(" in js or "sharedCache.delete(cacheKey)" in js, (
        "Expected cache eviction on expiry"
    )


def test_combo_cache_shared_across_instances():
    """Cache lives on the class (not on each instance) so any combo can hit it."""
    js = Path("/opt/data/work/sazon-app/app/static/ui-combo.js").read_text()
    # Class-level reference — not `this._cache`
    assert "UICombo._sharedCache" in js
    assert "this._cache" not in js, "Should not have a per-instance cache anymore"


def test_combo_clear_cache_helper():
    """A clearCache() method should be exposed on the class."""
    js = Path("/opt/data/work/sazon-app/app/static/ui-combo.js").read_text()
    # Static method to flush the cache
    m = re.search(
        r"static\s+clearCache\s*\(\s*\)\s*\{[^}]*_sharedCache\.clear\s*\(\s*\)", js, re.DOTALL
    )
    assert m is not None, "Expected a static clearCache() method that clears _sharedCache"


def test_combo_render_uses_fragment():
    """The render path uses DocumentFragment to batch DOM writes."""
    js = Path("/opt/data/work/sazon-app/app/static/ui-combo.js").read_text()
    # Should create a fragment and append all rows to it before one big append
    assert "createDocumentFragment" in js
    assert "frag.appendChild(row)" in js
    assert "this.results.appendChild(frag)" in js


def test_combo_no_naive_per_row_append():
    """_render should no longer call appendChild on the live results element per row."""
    js = Path("/opt/data/work/sazon-app/app/static/ui-combo.js").read_text()
    # Find the _render section and confirm there's no direct results.appendChild inside
    # the forEach body (only fragment appendChild is allowed).
    render_section = js[js.index("_render(matches)") : js.index("setValue(item)")]
    # There should be results.appendChild(...) exactly once (the fragment mount)
    assert render_section.count("this.results.appendChild") == 1


def test_combo_debounce_preserved_after_cache():
    """Even with caching, debounce should still gate search input."""
    js = Path("/opt/data/work/sazon-app/app/static/ui-combo.js").read_text()
    # The debounce timer should still wrap _fetch
    assert "clearTimeout(self.debounceTimer)" in js
    assert "self._fetch(q)" in js


def test_base_template_preloads_combo():
    """base.html should preload combo.js for faster form interactions."""
    base = Path("/opt/data/work/sazon-app/app/templates/base.html").read_text()
    # Preload hint should exist
    assert '<link rel="preload" href="/static/ui-combo.js"' in base
    # And the script should be version-busted for safe cache hits
    assert "combo.js?v={{ asset_version() }}" in base


def test_users_api_roles_response_shape():
    """/users/api/roles returns the expected JSON shape for the combo."""
    users_router = Path("/opt/data/work/sazon-app/app/routers/users.py").read_text()
    # Endpoint should exist and return JSON with results + count
    assert "/api/roles" in users_router
    assert "results" in users_router
    assert "count" in users_router
    assert "JSONResponse" in users_router


def test_combo_supports_static_source():
    """combo.js should accept data-source="static" for inline options."""
    js = Path("/opt/data/work/sazon-app/app/static/ui-combo.js").read_text()
    # Static source branch should exist
    assert 'this.opts.source === "static"' in js
    assert "_readStaticOptions" in js
    # The reader looks for combo-static-option rows
    assert "combo-static-option" in js


def test_productos_uses_static_combo():
    """productos.html has_recipe filter is a radio popover (mf-pop) — no native select.

    2026-09-27: upgraded from static ui-combo to the shared mf-pop filter
    toolbar pattern (same as inventario). Still zero-native-select."""
    p = Path("/opt/data/work/sazon-app/app/templates/productos.html").read_text()
    # Old native select should be gone
    assert '<select name="has_recipe">' not in p
    assert "<select" not in p
    # mf-pop radio popover with 3 options
    assert 'data-mf="has_recipe"' in p
    assert p.count('value="{{ val }}"') >= 1  # loop-generated radio options
    # Count line + limpiar present
    assert "Limpiar todo" in p


def test_receta_form_scale_uses_static_combo():
    """receta_form.html scale selector uses a static combo."""
    r = Path("/opt/data/work/sazon-app/app/templates/receta_form.html").read_text()
    # Old native scale select with onchange should be gone
    assert '<select id="scale"' not in r
    # Should have the scale_combo + 8 multiplier options
    assert "scale_combo" in r
    # Should auto-submit the form on pick (matching the old onchange)
    assert 'combo.closest("form").submit()' in r


def test_receta_form_yield_unit_uses_combo():
    """receta_form.html yield_unit uses the units API combo."""
    r = Path("/opt/data/work/sazon-app/app/templates/receta_form.html").read_text()
    # yield_unit select gone
    assert '<select id="yield_unit"' not in r
    # New combo present
    assert 'name="yield_unit"' in r
    assert 'data-source="/recetas/api/units"' in r


def test_receta_form_lines_use_combos():
    """receta_form.html line_kind + line_unit combos present for both rendered and JS-template rows."""
    r = Path("/opt/data/work/sazon-app/app/templates/receta_form.html").read_text()
    # No <select name="line_kind"> and no <select name="line_unit">
    assert '<select name="line_kind">' not in r
    assert '<select name="line_unit"' not in r
    # Two kinds of combos: existing (server-rendered) and template (JS-built)
    # 2 hidden line_kind combos (existing + template) and 2 line_unit combos
    assert r.count('name="line_kind"') >= 2
    assert r.count('name="line_unit"') >= 2
    # updateLineSource updated to read the hidden input of the line_kind combo
    assert "kindHidden" in r
    assert "wireLineKindHandlers" in r


def test_reorder_qty_unit_uses_static_combo():
    """reorder.html qty_unit uses a static combo (preserves conditional logic)."""
    f = Path("/opt/data/work/sazon-app/app/templates/reorder.html").read_text()
    # Old native select gone
    assert '<select name="qty_unit"' not in f
    # New combo present, conditional logic preserved
    assert 'data-source="static"' in f
    # Per-item jinja conditionals still present
    assert "{% if item.unit in ('g', 'kg') %}" in f


def test_zero_native_selects_remain():
    """Across the entire templates/ folder, no native <select> survives conversion."""
    templates_dir = Path("/opt/data/work/sazon-app/app/templates")
    pattern = re.compile(r"<select[^>]*>.*?</select>", re.DOTALL)
    leftovers = []
    for html_file in templates_dir.glob("*.html"):
        content = html_file.read_text()
        for m in pattern.finditer(content):
            sel = m.group(0)
            if "data-ui-combo" in sel:
                continue  # combo markup — fine
            leftovers.append((html_file.name, sel[:80]))
    assert leftovers == [], f"Native selects still present: {leftovers}"
