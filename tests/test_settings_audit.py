"""Tests for audit log coverage on settings mutations (Phase 14, mid-tier)."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import text


def test_business_settings_change_is_audited(client, session_factory):
    """POST /settings/business must record an audit row with the bakery RUC."""
    r = client.post(
        "/settings/business",
        data={
            "business_name": "Panadería Test",
            "business_ruc": "80012345-6",
            "razon_social": "Test SRL",
            "business_address": "Av. Test 123",
            "business_phone": "+595981000000",
            "business_email": "test@example.com",
            "nombre_fantasia": "Test",
            "tax_regime": "general",
            "iva_default_rate": "10",
            "timbrado_number": "12345678",
            "timbrado_expiry": "2027-12-31",
            "inan_re_number": "12345",
            "inan_re_expiry": "2027-12-31",
            "director_tecnico": "Juan Pérez",
            "director_tecnico_registro": "REG-123",
            "municipal_habilitacion": "HAB-1",
            "municipal_habilitacion_expiry": "2027-12-31",
            "labor_cost_per_hour_gs": "25000",
            "overhead_multiplier_pct": "10",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303

    with session_factory() as s:
        rows = s.execute(
            text("SELECT detail FROM audit_log WHERE action = 'settings.business.change' ORDER BY id DESC LIMIT 1")
        ).all()
        assert rows, "No audit row recorded for settings.business.change"
        detail_text = str(rows[0][0])
        assert "80012345-6" in detail_text or "12345678" in detail_text


def test_seed_demo_is_audited(client, session_factory):
    """POST /settings/seed-demo must record an audit row."""
    r = client.post(
        "/settings/seed-demo",
        data={"overwrite": "0"},
        follow_redirects=False,
    )
    assert r.status_code == 303

    with session_factory() as s:
        rows = s.execute(
            text("SELECT detail FROM audit_log WHERE action = 'settings.seed_demo' ORDER BY id DESC LIMIT 1")
        ).all()
        assert rows, "No audit row recorded for settings.seed_demo"
        assert "overwrite" in str(rows[0][0])


def test_fiscal_settings_change_still_audited(client, session_factory):
    """Regression: existing /fiscal audit must not have been broken."""
    r = client.post(
        "/settings/fiscal",
        data={"timbrado": "11111", "punto_expedicion": "001", "invoice_sequence": "1"},
        follow_redirects=False,
    )
    assert r.status_code == 303

    with session_factory() as s:
        rows = s.execute(
            text("SELECT detail FROM audit_log WHERE action IN ('settings.change', 'settings.create') ORDER BY id DESC LIMIT 5")
        ).all()
        assert rows


def test_theme_settings_change_still_audited(client, session_factory):
    """Regression: existing /theme audit must not have been broken."""
    r = client.post(
        "/settings/theme",
        data={"theme": "dark"},
        follow_redirects=False,
    )
    assert r.status_code == 303

    with session_factory() as s:
        rows = s.execute(
            text("SELECT detail FROM audit_log WHERE action IN ('settings.change', 'settings.create') ORDER BY id DESC LIMIT 5")
        ).all()
        assert rows