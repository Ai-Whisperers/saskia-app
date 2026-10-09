"""PROD-MERMA-2: /auditoria surfaces the source chip for merma events.

Operators triaging merma events on /auditoria should see the same chip
text as on /merma so the vocabulary stays consistent across surfaces.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.rms.models import AuditLog


def _insert_audit(session_factory, *, action: str, source: str | None = None, target_id: str = "1"):
    with session_factory() as s:
        detail = {"ingredient_id": 1, "qty": 0.5}
        if source is not None:
            detail["source"] = source
        row = AuditLog(
            occurred_at=datetime.now(timezone.utc),
            user_id="1",
            action=action,
            target_type="merma" if action.startswith("write.merma") else None,
            target_id=target_id,
            detail=detail,
        )
        s.add(row)
        s.commit()


def test_auditoria_renders_source_chip_for_merma_audit(authed_client, session_factory):
    """write.merma.create with detail.source='production' renders 📍 Producción."""
    _insert_audit(session_factory, action="write.merma.create", source="production")
    r = authed_client.get("/auditoria?action_filter=write.merma.create")
    assert r.status_code == 200
    body = r.text
    assert "📍 Producción" in body, "Source chip missing on /auditoria for production merma event"
    assert "badge-info" in body, "badge-info class missing on /auditoria source chip"


def test_auditoria_renders_manual_chip_for_legacy_merma(authed_client, session_factory):
    """write.merma.create with detail.source='manual' renders ✍️ Manual."""
    _insert_audit(session_factory, action="write.merma.create", source="manual")
    r = authed_client.get("/auditoria?action_filter=write.merma.create")
    assert r.status_code == 200
    body = r.text
    assert "✍️ Manual" in body, "Manual chip missing on /auditoria"


def test_auditoria_no_chip_for_unrelated_action(authed_client, session_factory):
    """Non-merma audit rows do NOT render any source chip."""
    _insert_audit(session_factory, action="login.success", source=None)
    r = authed_client.get("/auditoria?action_filter=login.success")
    assert r.status_code == 200
    body = r.text
    assert "📍 Producción" not in body
    assert "✍️ Manual" not in body


def test_auditoria_no_chip_when_source_absent(authed_client, session_factory):
    """write.merma.create with no source key renders no chip."""
    _insert_audit(session_factory, action="write.merma.create", source=None)
    r = authed_client.get("/auditoria?action_filter=write.merma.create")
    assert r.status_code == 200
    body = r.text
    assert "📍 Producción" not in body
    assert "✍️ Manual" not in body
