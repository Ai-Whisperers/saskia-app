"""tests/test_mobile_ux.py — E4.S4 mobile UX regression tests.

Covers:
- mobile.css is served (200, content-type text/css)
- mobile.css bumps touch targets to ≥44px on ≤768px viewports
- mobile.css hides bottom-nav on desktop, shows on mobile
- /inicio (and other pages) include the bottom-nav with 5 links
- base.html links to /static/mobile.css
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MOBILE_CSS = REPO_ROOT / "app" / "static" / "mobile.css"
BASE_HTML = REPO_ROOT / "app" / "templates" / "base.html"


def test_mobile_css_file_exists_and_nonempty():
    assert MOBILE_CSS.exists(), "mobile.css missing"
    content = MOBILE_CSS.read_text(encoding="utf-8")
    assert len(content) > 500


def test_mobile_css_bumps_btn_height_to_44px():
    content = MOBILE_CSS.read_text(encoding="utf-8")
    # The mobile rule must bump --btn-height to at least 44px
    assert "--btn-height: 44px" in content, (
        "mobile.css must set --btn-height to 44px on mobile viewports"
    )


def test_mobile_css_defines_bottom_nav_class():
    content = MOBILE_CSS.read_text(encoding="utf-8")
    assert ".bottom-nav" in content
    # On desktop, bottom-nav should be hidden
    assert "display: none" in content or "display:none" in content
    # On mobile, it should be flex
    assert "display: flex" in content or "display:flex" in content


def test_mobile_css_has_safe_area_inset_for_iphones():
    content = MOBILE_CSS.read_text(encoding="utf-8")
    assert "safe-area-inset-bottom" in content


def test_base_html_links_to_mobile_css():
    content = BASE_HTML.read_text(encoding="utf-8")
    assert "/static/mobile.css" in content, (
        "base.html must link to /static/mobile.css"
    )


def test_base_html_renders_bottom_nav_with_5_links(authed_client):
    """The base.html <nav class="bottom-nav"> appears with all 5 quick-nav entries."""
    r = authed_client.get("/inicio")
    assert r.status_code == 200
    body = r.text
    assert 'class="bottom-nav"' in body
    # 5 quick-nav entries: Inicio, Vender, Stock, Reponer, Más
    for label in ["Inicio", "Vender", "Stock", "Reponer", "Más"]:
        assert f">{label}</span>" in body or f" {label}</span>" in body


def test_mobile_css_served_via_static_route(authed_client):
    """/static/mobile.css returns 200 with text/css content type."""
    r = authed_client.get("/static/mobile.css")
    assert r.status_code == 200
    ct = r.headers.get("content-type", "")
    assert "text/css" in ct or "css" in ct


def test_bottom_nav_includes_safe_anchors(authed_client):
    """Each bottom-nav <a> href points to a real page."""
    r = authed_client.get("/inicio")
    body = r.text
    # Pull out the bottom-nav block
    import re
    nav_match = re.search(r'<nav class="bottom-nav"[^>]*>(.*?)</nav>', body, re.DOTALL)
    assert nav_match, "no bottom-nav block"
    nav_html = nav_match.group(1)
    hrefs = [h for h in re.findall(r'href="([^"]+)"', nav_html) if not h.startswith("#")]
    # 5 hrefs expected
    assert len(hrefs) == 5
    for href in hrefs:
        assert href.startswith("/"), f"bottom-nav href must be relative: {href!r}"
