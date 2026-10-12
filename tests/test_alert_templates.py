"""tests/test_alert_templates.py — Test app/rms/alert_templates.py (Phase 4.5).

The module exposes:
  - AlertTemplate (frozen dataclass with .render(**kwargs) helper)
  - get_eod_alert_template(session, key) — DB lookup with hardcoded fallback

The fallback path is critical: if the message_template row is missing
or the migration hasn't run, the EOD alert emails still need to go
out. A regression here would either blank out emails or crash the
EOD cron (the latter triggers a Tier-8 anomaly alert).
"""

from __future__ import annotations

import pytest

from app.rms.alert_templates import AlertTemplate, get_eod_alert_template
from app.rms.models import MessageTemplate


def _clear_templates(session):
    """Wipe message_template so each test starts from a known state."""
    from sqlalchemy import text
    session.execute(text("DELETE FROM message_template"))
    session.commit()


def _insert_template(session, channel, key, subject, body, locale="es-PY", is_active=True):
    session.add(
        MessageTemplate(
            channel=channel,
            key=key,
            subject=subject,
            body=body,
            locale=locale,
            is_active=is_active,
        )
    )
    session.commit()


class TestAlertTemplate:
    """AlertTemplate is a value object — pin its dataclass + format() semantics."""

    def test_attributes_set(self):
        tmpl = AlertTemplate(
            key="k", subject="s", body="b {x}", locale="es-PY"
        )
        assert tmpl.key == "k"
        assert tmpl.subject == "s"
        assert tmpl.body == "b {x}"
        assert tmpl.locale == "es-PY"

    def test_default_locale(self):
        tmpl = AlertTemplate(key="k", subject="s", body="b")
        assert tmpl.locale == "es-PY"

    def test_render_substitutes_kwargs(self):
        tmpl = AlertTemplate(
            key="k", subject="s", body="hola {name}, tenés {n} ventas"
        )
        assert tmpl.render(name="Ana", n=3) == "hola Ana, tenés 3 ventas"

    def test_render_missing_key_raises(self):
        # Mirrors str.format(**) — typos should surface loudly.
        tmpl = AlertTemplate(key="k", subject="s", body="hola {name}")
        with pytest.raises(KeyError):
            tmpl.render(nope="x")

    def test_frozen(self):
        # The dataclass is frozen — assignment raises.
        tmpl = AlertTemplate(key="k", subject="s", body="b")
        with pytest.raises(Exception):  # FrozenInstanceError subclass
            tmpl.key = "other"  # type: ignore[misc]


class TestGetEodAlertTemplate:
    def test_returns_db_row_when_present(self, session_factory):
        _clear_templates_factory(session_factory)
        with session_factory() as s:
            _insert_template(
                s,
                channel="email",
                key="eod.voided_rate",
                subject="Custom subject",
                body="Custom body with {voided}",
            )
        with session_factory() as s:
            tmpl = get_eod_alert_template(s, "eod.voided_rate")
        assert tmpl.subject == "Custom subject"
        assert tmpl.body == "Custom body with {voided}"
        assert tmpl.key == "eod.voided_rate"

    def test_ignores_non_email_channel(self, session_factory):
        _clear_templates_factory(session_factory)
        with session_factory() as s:
            _insert_template(
                s,
                channel="whatsapp",  # not email
                key="eod.voided_rate",
                subject="WA subject",
                body="WA body",
            )
        with session_factory() as s:
            tmpl = get_eod_alert_template(s, "eod.voided_rate")
        # Should fall through to the hardcoded fallback (not pick the WA row).
        assert tmpl.body != "WA body"
        assert "voided" in tmpl.body  # fallback uses {voided} placeholder

    def test_ignores_inactive_rows(self, session_factory):
        _clear_templates_factory(session_factory)
        with session_factory() as s:
            _insert_template(
                s,
                channel="email",
                key="eod.voided_rate",
                subject="Inactive",
                body="Inactive body",
                is_active=False,
            )
        with session_factory() as s:
            tmpl = get_eod_alert_template(s, "eod.voided_rate")
        # Inactive row is ignored; fall through to fallback.
        assert tmpl.body != "Inactive body"

    def test_fallback_for_known_key(self, session_factory):
        _clear_templates_factory(session_factory)
        with session_factory() as s:
            tmpl = get_eod_alert_template(s, "eod.voided_rate")
        # No DB row → fallback copy from the hardcoded dict
        assert "voided" in tmpl.body
        assert "tasa" in tmpl.subject.lower() or "anulaciones" in tmpl.subject.lower()

    def test_fallback_for_known_cash_zero_key(self, session_factory):
        _clear_templates_factory(session_factory)
        with session_factory() as s:
            tmpl = get_eod_alert_template(s, "eod.cash_zero_with_active_sales")
        assert "efectivo" in tmpl.body.lower()
        assert "ventas activas" in tmpl.body.lower()

    def test_fallback_for_unknown_key_returns_generic(self, session_factory):
        _clear_templates_factory(session_factory)
        with session_factory() as s:
            tmpl = get_eod_alert_template(s, "eod.never_heard_of_this")
        # Not in fallback dict, not in DB → generic "(Alerta)" template
        assert tmpl.subject == "(Alerta)"
        assert tmpl.body == "{message}"
        assert tmpl.key == "eod.never_heard_of_this"

    def test_fallback_locale_default(self, session_factory):
        _clear_templates_factory(session_factory)
        with session_factory() as s:
            tmpl = get_eod_alert_template(s, "eod.voided_rate")
        assert tmpl.locale == "es-PY"

    def test_db_row_locale_handles_null(self, session_factory):
        _clear_templates_factory(session_factory)
        with session_factory() as s:
            _insert_template(
                s,
                channel="email",
                key="eod.voided_rate",
                subject="S",
                body="B",
                locale="",  # null in DB
            )
        with session_factory() as s:
            tmpl = get_eod_alert_template(s, "eod.voided_rate")
        # Empty/null locale falls back to default
        assert tmpl.locale == "es-PY"


def _clear_templates_factory(session_factory):
    """Helper: clear message_template via a session."""
    with session_factory() as s:
        _clear_templates(s)
