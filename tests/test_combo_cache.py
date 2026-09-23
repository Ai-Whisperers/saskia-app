"""Test that combo.js cache implementation is correct."""

import re
from pathlib import Path


def test_combo_cache_ttl_constant():
    """Cache TTL should be a finite, reasonable value (30s)."""
    js = Path("/opt/data/profiles/ivan/scratch/saskia-app-work/app/static/combo.js").read_text()
    # Find the TTL check
    m = re.search(r"Date\.now\(\)\s*-\s*entry\.ts\s*<\s*(\d+)", js)
    assert m is not None, "Expected a TTL check in combo.js"
    ttl_ms = int(m.group(1))
    # Should be 30 seconds (30000ms) — long enough to dedupe across rapid
    # opens, short enough that listing pages don't show stale data.
    assert ttl_ms == 30000, f"Expected 30s TTL, got {ttl_ms}ms"


def test_combo_cache_writeback():
    """After a successful fetch, combo.js should write to the cache."""
    js = Path("/opt/data/profiles/ivan/scratch/saskia-app-work/app/static/combo.js").read_text()
    # Should set the cache with ts and data fields after the network call resolves
    assert "_sharedCache.set" in js
    assert "ts: Date.now()" in js
    assert "data: items" in js


def test_combo_cache_expiry_evicts():
    """Expired cache entries should be evicted on read."""
    js = Path("/opt/data/profiles/ivan/scratch/saskia-app-work/app/static/combo.js").read_text()
    # Should delete cache entry on expiry (using either instance or shared cache handle)
    assert "_sharedCache.delete(" in js or "sharedCache.delete(cacheKey)" in js, \
        "Expected cache eviction on expiry"


def test_combo_cache_shared_across_instances():
    """Cache lives on the class (not on each instance) so any combo can hit it."""
    js = Path("/opt/data/profiles/ivan/scratch/saskia-app-work/app/static/combo.js").read_text()
    # Class-level reference — not `this._cache`
    assert "SaskiaCombo._sharedCache" in js
    assert "this._cache" not in js, "Should not have a per-instance cache anymore"


def test_combo_clear_cache_helper():
    """A clearCache() method should be exposed on the class."""
    js = Path("/opt/data/profiles/ivan/scratch/saskia-app-work/app/static/combo.js").read_text()
    # Static method to flush the cache
    m = re.search(r"static\s+clearCache\s*\(\s*\)\s*\{[^}]*_sharedCache\.clear\s*\(\s*\)", js, re.DOTALL)
    assert m is not None, "Expected a static clearCache() method that clears _sharedCache"


def test_combo_render_uses_fragment():
    """The render path uses DocumentFragment to batch DOM writes."""
    js = Path("/opt/data/profiles/ivan/scratch/saskia-app-work/app/static/combo.js").read_text()
    # Should create a fragment and append all rows to it before one big append
    assert "createDocumentFragment" in js
    assert "frag.appendChild(row)" in js
    assert "this.results.appendChild(frag)" in js


def test_combo_no_naive_per_row_append():
    """_render should no longer call appendChild on the live results element per row."""
    js = Path("/opt/data/profiles/ivan/scratch/saskia-app-work/app/static/combo.js").read_text()
    # Find the _render section and confirm there's no direct results.appendChild inside
    # the forEach body (only fragment appendChild is allowed).
    render_section = js[js.index("_render(matches)"): js.index("setValue(item)")]
    # There should be results.appendChild(...) exactly once (the fragment mount)
    assert render_section.count("this.results.appendChild") == 1


def test_combo_debounce_preserved_after_cache():
    """Even with caching, debounce should still gate search input."""
    js = Path("/opt/data/profiles/ivan/scratch/saskia-app-work/app/static/combo.js").read_text()
    # The debounce timer should still wrap _fetch
    assert "clearTimeout(self.debounceTimer)" in js
    assert "self._fetch(q)" in js


def test_base_template_preloads_combo():
    """base.html should preload combo.js for faster form interactions."""
    base = Path("/opt/data/profiles/ivan/scratch/saskia-app-work/app/templates/base.html").read_text()
    # Preload hint should exist
    assert '<link rel="preload" href="/static/combo.js"' in base
    # And the script should be version-busted for safe cache hits
    assert 'combo.js?v={{ asset_version() }}' in base


def test_users_api_roles_response_shape():
    """/users/api/roles returns the expected JSON shape for the combo."""
    users_router = Path("/opt/data/profiles/ivan/scratch/saskia-app-work/app/routers/users.py").read_text()
    # Endpoint should exist and return JSON with results + count
    assert "/api/roles" in users_router
    assert "results" in users_router
    assert "count" in users_router
    assert "JSONResponse" in users_router
