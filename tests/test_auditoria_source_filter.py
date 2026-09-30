"""PROD-MERMA-2: /auditoria ?source= filter narrows merma rows.

Adds a filter so operators can quickly see only the production-entrypoint
merma events (or only the legacy /merma-form entries).
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.rms.models import AuditLog


def _insert(session_factory, *, action: str, source: str | None):
    with session_factory() as s:
        detail = {"ingredient_id": 1, "qty": 0.5}
        if source is not None:
            detail["source"] = source
        row = AuditLog(
            occurred_at=datetime.now(timezone.utc),
            user_id="1",
            action=action,
            target_type="merma",
            target_id="1",
            detail=detail,
        )
        s.add(row)
        s.commit()


def test_source_filter_narrows_to_production(authed_client, session_factory):
    """?source=production only renders rows with detail.source='production'."""
    _insert(session_factory, action="write.merma.create", source="production")
    _insert(session_factory, action="write.merma.create", source="manual")
    r = authed_client.get("/auditoria?action_filter=write.merma.create&source=production")
    assert r.status_code == 200
    body = r.text
    assert "📍 Producción" in body, "Production chip should appear under source=production filter"
    # Manual chip rendered in the same page when filtered, so use a stronger check:
    # find the action column and ensure we only see ONE write.merma.create row.
    # Easier check: count occurrences of write.merma.create in tbody (not thead).
    import re
    tbody = body.split("<tbody>", 1)[1].split("</tbody>", 1)[0] if "<tbody>" in body else body
    rows_with_action = tbody.count("write.merma.create")
    assert rows_with_action == 1, f"Expected exactly 1 merma row under source=production, got {rows_with_action}"


def test_source_filter_narrows_to_manual(authed_client, session_factory):
    """?source=manual only renders rows with detail.source='manual'."""
    _insert(session_factory, action="write.merma.create", source="production")
    _insert(session_factory, action="write.merma.create", source="manual")
    r = authed_client.get("/auditoria?action_filter=write.merma.create&source=manual")
    assert r.status_code == 200
    body = r.text
    assert "✍️ Manual" in body
    import re
    tbody = body.split("<tbody>", 1)[1].split("</tbody>", 1)[0] if "<tbody>" in body else body
    rows_with_action = tbody.count("write.merma.create")
    assert rows_with_action == 1, f"Expected exactly 1 merma row under source=manual, got {rows_with_action}"


def test_no_source_filter_returns_all(authed_client, session_factory):
    """Without ?source=, both production and manual rows render."""
    _insert(session_factory, action="write.merma.create", source="production")
    _insert(session_factory, action="write.merma.create", source="manual")
    r = authed_client.get("/auditoria?action_filter=write.merma.create")
    assert r.status_code == 200
    body = r.text
    assert "📍 Producción" in body
    assert "✍️ Manual" in body


def test_auditoria_api_sources_returns_canonical_list(authed_client):
    """The /auditoria/api/sources combo endpoint always returns the two known sources."""
    r = authed_client.get("/auditoria/api/sources")
    assert r.status_code == 200
    data = r.json()
    values = sorted([item["value"] for item in data])
    assert values == ["manual", "production"], f"Expected ['manual', 'production'], got {values}"


def test_auditoria_api_sources_substring_filter(authed_client):
    """The /auditoria/api/sources combo endpoint supports a substring query."""
    r = authed_client.get("/auditoria/api/sources?q=prod")
    assert r.status_code == 200
    data = r.json()
    values = [item["value"] for item in data]
    assert values == ["production"], f"Expected only ['production'], got {values}"
