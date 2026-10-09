"""Nav dropdown ARIA tests."""

from __future__ import annotations


def test_nav_has_aria_haspopup(client):
    """Nav dropdown must use aria-haspopup attribute."""
    r = client.get("/")
    assert r.status_code == 200
    body = r.text
    assert "aria-haspopup" in body, f"Nav missing aria-haspopup. Body preview: {body[:500]}"


def test_nav_has_aria_expanded(client):
    """Nav dropdown must use aria-expanded attribute."""
    r = client.get("/")
    assert r.status_code == 200
    body = r.text
    assert "aria-expanded" in body, f"Nav missing aria-expanded. Body preview: {body[:500]}"


def test_nav_has_role_menu(client):
    """Nav dropdown menu must have role='menu'."""
    r = client.get("/")
    assert r.status_code == 200
    body = r.text
    # role=menu may be set via attribute or class
    assert 'role="menu"' in body or "role='menu'" in body or "role:menu" in body, (
        f"Nav missing role=menu. Body preview: {body[:500]}"
    )


def test_nav_role_navigation(client):
    """Nav element must have role='navigation' or <nav> tag."""
    r = client.get("/")
    assert r.status_code == 200
    body = r.text.lower()
    assert "<nav" in body or 'role="navigation"' in body, (
        f"Nav missing role. Body preview: {body[:500]}"
    )
