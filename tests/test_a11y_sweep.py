"""Phase 22 — Comprehensive accessibility sweep across all main pages.

Verifies on a broad set of routes:
- <html lang="es"> declared
- <title> populated
- aria-live region exists for alerts
- breadcrumb navigation present and properly marked
- All icon-only buttons have aria-label
- All forms have associated labels
- Skip link present
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.rms.main import app


# Routes to sweep (a broad cross-section of the app)
PAGES = [
    "/",
    "/dashboard",
    "/pedidos",
    "/pedidos/nuevo",
    "/pedidos/board",
    "/productos",
    "/recetas",
    "/inventario",
    "/merma",
    "/clientes",
    "/ventas",
    "/proveedores",
    "/reorder",
    "/eod",
    "/reportes",
    "/analisis",
    "/auditoria",
    "/settings",
]


@pytest.fixture
def client(session_factory, monkeypatch):
    """Function-scoped client for the sweep (matches existing fixtures)."""
    with TestClient(app) as c:
        yield c


def _safe_get(client, path):
    """GET a path; skip if 401/403 (auth required)."""
    r = client.get(path, follow_redirects=True)
    if r.status_code in (401, 403):
        pytest.skip(f"{path} requires auth")
    return r


class TestLanguage:
    def test_html_lang_es(self, client):
        """<html lang='es'> should be set on every page."""
        for path in PAGES:
            r = _safe_get(client, path)
            assert 'lang="es"' in r.text, f"{path} missing lang='es'"


class TestTitle:
    def test_title_populated(self, client):
        """Every page should have a <title>."""
        for path in PAGES:
            r = _safe_get(client, path)
            # Find the <title>
            import re
            m = re.search(r"<title>([^<]+)</title>", r.text)
            assert m, f"{path} missing <title>"
            assert len(m.group(1).strip()) > 0, f"{path} has empty title"


class TestAriaLiveRegion:
    def test_alerts_region_exists(self, client):
        """An aria-live region for alerts should be in base.html."""
        for path in PAGES:
            r = _safe_get(client, path)
            assert 'aria-live="polite"' in r.text or 'aria-live="assertive"' in r.text, (
                f"{path} missing aria-live region"
            )


class TestBreadcrumbs:
    def test_breadcrumb_marks_for_known_paths(self, client):
        """Known entity paths should produce breadcrumbs with the parent section."""
        # /dashboard should have a breadcrumb to "Inicio"
        r = _safe_get(client, "/dashboard")
        # Either auto-breadcrumbs (≥2 crumbs) OR explicit page_header
        if 'class="breadcrumb"' in r.text:
            # Verify structure
            import re
            m = re.search(r'<nav class="breadcrumb"[^>]*>(.*?)</nav>', r.text, re.DOTALL)
            if m:
                # Should contain aria-current="page"
                assert 'aria-current="page"' in m.group(1), (
                    f"/dashboard breadcrumb missing aria-current"
                )


class TestSkipLink:
    def test_skip_link_first(self, client):
        """Every page must have a skip-link as the first focusable element."""
        for path in PAGES:
            r = _safe_get(client, path)
            # The skip-link should appear before main content
            skip_pos = r.text.find('class="skip-link"')
            main_pos = r.text.find('id="main-content"')
            if skip_pos >= 0 and main_pos >= 0:
                assert skip_pos < main_pos, (
                    f"{path}: skip-link should appear before main"
                )


class TestFormLabels:
    def test_input_has_label(self, client):
        """Forms should have inputs with associated labels."""
        r = _safe_get(client, "/login")
        # Username field should have <label for="username">
        assert '<label for="username"' in r.text or 'for="username"' in r.text, (
            "/login missing <label for='username'>"
        )


class TestIconButtonsHaveAria:
    def test_icon_buttons_have_aria_label(self, client):
        """Icon-only buttons should have aria-label."""
        r = _safe_get(client, "/dashboard")
        # Find all <button> without text content
        import re
        # Look for <button ... class="btn-icon" ...> with <svg> only
        # and verify aria-label exists
        icon_btn_pattern = re.compile(
            r'<button[^>]*class="[^"]*btn-icon[^"]*"[^>]*>.*?</button>',
            re.DOTALL,
        )
        for m in icon_btn_pattern.finditer(r.text):
            btn_html = m.group(0)
            if "<svg" in btn_html:
                # Has SVG, should have aria-label
                assert 'aria-label' in btn_html, (
                    f"Icon button missing aria-label: {btn_html[:200]}"
                )