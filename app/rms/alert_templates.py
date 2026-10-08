"""app/rms/alert_templates.py — Batch C (2026-10-08) helper for EOD alert templates.

Reads the ``message_template`` rows seeded by migration 116 (one per EOD
anomaly key). Falls back to the prior hardcoded copy if the template row
is missing or the table doesn't exist — preserves operator-observable
behavior even before the migration runs.

Usage::

    from app.rms.alert_templates import get_eod_alert_template
    tmpl = get_eod_alert_template(session, "eod.voided_rate")
    subject = tmpl["subject"]
    body = tmpl["body"].format(voided=voided, total=total, rate_pct=f"{rate:.0%}")

The dataclass returned is a thin wrapper around the ``message_template``
row plus a ``format()`` helper that calls ``body.format(**kwargs)``.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class AlertTemplate:
    """A single alert template fetched from ``message_template``."""

    key: str
    subject: str
    body: str
    locale: str = "es-PY"

    def render(self, **kwargs: object) -> str:
        """Substitute ``{placeholders}`` in the body.

        Mirrors ``str.format(**)`` semantics. Missing keys raise
        ``KeyError`` — that's intentional, a typo'd placeholder should
        surface loudly rather than silently produce broken copy.
        """
        return self.body.format(**kwargs)


def get_eod_alert_template(session: Session, key: str) -> AlertTemplate:
    """Fetch the EOD alert template for ``key`` (e.g. ``"eod.voided_rate"``).

    Falls back to the hardcoded copy in ``app/services/eod_anomaly.py``
    if the table doesn't exist (pre-migration) or the row is missing
    (operator deleted it accidentally). The fallback matches the prior
    copy exactly so behavior is preserved.
    """
    try:
        row = session.execute(
            text(
                """
                SELECT key, subject, body, locale
                FROM message_template
                WHERE channel = 'email' AND key = :key AND is_active = 1
                ORDER BY locale = 'es-PY' DESC
                LIMIT 1
                """
            ),
            {"key": key},
        ).fetchone()
    except Exception:
        row = None

    if row:
        return AlertTemplate(
            key=row[0],
            subject=row[1],
            body=row[2],
            locale=row[3] or "es-PY",
        )

    # Fallback: matches the hardcoded copy in _check_*() functions
    # of app/services/eod_anomaly.py.
    return _FALLBACK_TEMPLATES.get(key) or AlertTemplate(
        key=key, subject="(Alerta)", body="{message}"
    )


# Mirror of _ALERT_TEMPLATES in app/rms/migrations/_116_eod_alert_templates.py.
# Used only when the catalog hasn't been seeded yet (rare; the migration
# is idempotent and safe to run multiple times).
_FALLBACK_TEMPLATES: dict[str, AlertTemplate] = {
    "eod.cash_zero_with_active_sales": AlertTemplate(
        key="eod.cash_zero_with_active_sales",
        subject="Cierre sin ventas en efectivo",
        body=(
            "Hay {active_count} ventas activas hoy pero ninguna en "
            "efectivo. Si la panadería estuvo abierta al público, "
            "revisá que el método de pago se esté registrando bien."
        ),
    ),
    "eod.voided_rate": AlertTemplate(
        key="eod.voided_rate",
        subject="Tasa de anulaciones alta",
        body=(
            "Hoy se anularon {voided} de {total} ventas "
            "({rate_pct}). Normal es 1-3%. Si fue error de operador, "
            "no hay problema. Si fue sistemático, revisá el flujo de "
            "cobro."
        ),
    ),
    "eod.uninvoiced_factura": AlertTemplate(
        key="eod.uninvoiced_factura",
        subject="Ventas con factura sin número",
        body=(
            "{bad_count} ventas marcadas como 'factura' no tienen número "
            "de timbrado. DNIT puede multar. IDs: {ids}"
        ),
    ),
    "eod.negative_grand_total": AlertTemplate(
        key="eod.negative_grand_total",
        subject="Total de ventas del día NEGATIVO",
        body=(
            "El total de hoy (sin anuladas) es Gs. {total:,}. No debería "
            "ser negativo. Probable bug en la migración o en la "
            "lógica de descuento. IDs: {ids}"
        ),
    ),
}


__all__ = [
    "AlertTemplate",
    "get_eod_alert_template",
]
