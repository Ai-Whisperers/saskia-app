"""Tests for the merma-ok flash banner on /produccion.

After the quick-merma modal POSTs to /merma/registrar (or /merma/receta),
the redirect goes to /produccion?merma=ok&lines=N. The page must render a
green banner matching the merma event count.
"""

from __future__ import annotations


def test_produccion_renders_merma_banner_with_count(authed_client):
    """/produccion?merma=ok&lines=3 must show a 'Merma registrada (3)' banner."""
    r = authed_client.get("/produccion?view=day&merma=ok&lines=3")
    assert r.status_code == 200
    body = r.text
    # Banner text — must include the count
    assert "Merma registrada" in body, "Merma flash banner missing"
    # Count 3 must appear near the banner text
    # (look for the count within ~120 chars of the banner phrase)
    idx = body.find("Merma registrada")
    assert idx != -1
    window = body[idx : idx + 200]
    assert "3" in window, f"expected '3' near banner, got window: {window!r}"


def test_produccion_banner_absent_without_query(authed_client):
    """/produccion without ?merma=ok must NOT show the banner."""
    r = authed_client.get("/produccion?view=day")
    assert r.status_code == 200
    assert "Merma registrada" not in r.text, "Merma banner should only render when ?merma=ok is set"


def test_produccion_banner_handles_singular(authed_client):
    """lines=1 (singular) must not break — operator logs one event at a time."""
    r = authed_client.get("/produccion?view=day&merma=ok&lines=1")
    assert r.status_code == 200
    body = r.text
    assert "Merma registrada" in body
    # Should mention "1" or "un" / "una"
    idx = body.find("Merma registrada")
    window = body[idx : idx + 200]
    assert "1" in window
