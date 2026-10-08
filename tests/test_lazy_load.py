"""Phase 34 — Lazy load images tests.

Verifies the data-lazy-src auto-applied IntersectionObserver utility.
"""

from __future__ import annotations

from pathlib import Path

LAZY_JS = Path(__file__).parent.parent / "app" / "static" / "lazy-load.js"
BASE_HTML = Path(__file__).parent.parent / "app" / "templates" / "base.html"


def test_lazy_load_js_exists():
    """Should have lazy load script."""
    assert LAZY_JS.exists()


def test_lazy_load_loaded_in_base():
    """Should be loaded in base.html."""
    text = BASE_HTML.read_text()
    assert "lazy-load.js" in text


def test_lazy_load_exposes_global():
    """Should expose LazyLoad globally."""
    js = LAZY_JS.read_text()
    assert "window.LazyLoad" in js


def test_lazy_load_uses_iife():
    """Should be wrapped in IIFE."""
    js = LAZY_JS.read_text()
    assert "(function()" in js
    assert "'use strict'" in js


def test_lazy_load_uses_data_attribute():
    """Should use data-lazy-src attribute."""
    js = LAZY_JS.read_text()
    assert "data-lazy-src" in js


def test_lazy_load_checks_native_support():
    """Should check native loading support first."""
    js = LAZY_JS.read_text()
    assert "'loading' in HTMLImageElement.prototype" in js
    assert "_applyNativeLazy" in js


def test_lazy_load_uses_native_lazy():
    """Should use native loading='lazy' when supported."""
    js = LAZY_JS.read_text()
    assert 'setAttribute("loading"' in js or "setAttribute('loading'" in js
    assert "lazy" in js


def test_lazy_load_sets_decoding_async():
    """Should set decoding='async'."""
    js = LAZY_JS.read_text()
    assert "decoding" in js
    assert "async" in js


def test_lazy_load_uses_intersection_observer():
    """Should use IntersectionObserver for older browsers."""
    js = LAZY_JS.read_text()
    assert "IntersectionObserver" in js


def test_lazy_load_has_observer():
    """Should store observer reference."""
    js = LAZY_JS.read_text()
    assert "observer:" in js
    assert "this.observer" in js


def test_lazy_load_has_root_margin():
    """Should have rootMargin for early loading."""
    js = LAZY_JS.read_text()
    assert "rootMargin" in js
    assert "200px" in js


def test_lazy_load_has_threshold():
    """Should have threshold for intersection detection."""
    js = LAZY_JS.read_text()
    assert "threshold" in js


def test_lazy_load_unobserves_after_load():
    """Should unobserve images after loading."""
    js = LAZY_JS.read_text()
    assert "this.observer.unobserve" in js


def test_lazy_load_watches_new_images():
    """Should observe new images added to DOM."""
    js = LAZY_JS.read_text()
    assert "MutationObserver" in js
    assert "addedNodes" in js
    assert "childList: true" in js
    assert "subtree: true" in js


def test_lazy_load_loads_intersecting_images():
    """Should load images when intersecting."""
    js = LAZY_JS.read_text()
    assert "isIntersecting" in js
    assert "_loadImage" in js


def test_lazy_load_removes_attribute_after_load():
    """Should remove data-lazy-src after loading."""
    js = LAZY_JS.read_text()
    assert "removeAttribute('data-lazy-src')" in js or 'removeAttribute("data-lazy-src")' in js


def test_lazy_load_sets_src():
    """Should set src from data-lazy-src."""
    js = LAZY_JS.read_text()
    assert "img.src = src" in js


def test_lazy_load_public_load_all():
    """Should have public loadAll method."""
    js = LAZY_JS.read_text()
    assert "loadAll()" in js
    assert "_loadImage(img)" in js


def test_lazy_load_fallback_to_native():
    """Should fall back to native if no IntersectionObserver."""
    js = LAZY_JS.read_text()
    assert "'IntersectionObserver' in window" in js


def test_lazy_load_dom_ready():
    """Should wait for DOM ready."""
    js = LAZY_JS.read_text()
    assert "readyState" in js
    assert "DOMContentLoaded" in js


def test_lazy_load_handles_nested():
    """Should find nested images via querySelectorAll."""
    js = LAZY_JS.read_text()
    assert "querySelectorAll" in js
    assert "node.matches" in js


def test_lazy_load_checks_element_type():
    """Should filter to element nodes only."""
    js = LAZY_JS.read_text()
    assert "nodeType === 1" in js


def test_lazy_load_handles_no_data_lazy():
    """Should not load if no data-lazy-src."""
    js = LAZY_JS.read_text()
    assert "if (!src) return" in js


def test_lazy_load_skips_already_loaded():
    """Should skip images that already have src."""
    js = LAZY_JS.read_text()
    assert "!img.getAttribute('src')" in js or '!img.getAttribute("src")' in js
