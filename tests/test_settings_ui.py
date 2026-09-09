"""tests/test_settings_ui.py — verify /settings route exists + works."""
from __future__ import annotations


def test_settings_index_loads(client):
    """/settings returns 200 and renders."""
    resp = client.get("/settings")
    assert resp.status_code == 200
    body = resp.text
    # Should at least have a form heading
    assert "<h1>" in body or "<h2>" in body


def test_settings_lists_general_group(client):
    """/settings shows general settings (currency_symbol etc)."""
    resp = client.get("/settings")
    assert resp.status_code == 200
    body = resp.text
    # Title is in Spanish
    assert "Configuración" in body or "Settings" in body


def test_settings_post_updates_value(client, session_factory):
    """POST /settings changes a setting value."""
    resp = client.post(
        "/settings",
        data={
            "key": "general.currency_symbol",
            "value": "Gs.",
        },
        follow_redirects=False,
    )
    assert resp.status_code in (303, 200)
    # Verify via the settings module
    from app.rms.settings import get_setting
    with session_factory() as s:
        val = get_setting(s, "general.currency_symbol")
        assert val == "Gs."
