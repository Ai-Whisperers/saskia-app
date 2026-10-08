"""Migration 116 — EOD alert templates (Batch C, 2026-10-08).

Seeds ``message_template`` rows for the 4 hardcoded EOD alert titles
and bodies in ``app/services/eod_anomaly.py``:

  - eod.cash_zero_with_active_sales
  - eod.voided_rate
  - eod.uninvoiced_factura
  - eod.negative_grand_total

The hardcoded Spanish copy gets moved into the MessageTemplate table
(already created in migration 044) so operators can edit the body
without a code deploy. The same ``{placeholder}`` substitution format
as the pedidos templates applies.

Idempotent: INSERT OR IGNORE on the (channel='email', key=..., locale='es-PY')
unique triple — re-running this migration does NOT clobber operator edits.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text


# (key, subject, body) — matches the prior hardcoded copy exactly.
# Placeholders use the same {name} format() syntax as the pedidos
# templates. The ``detector`` substitutes these at dispatch time.
_ALERT_TEMPLATES = [
    (
        "eod.cash_zero_with_active_sales",
        "Cierre sin ventas en efectivo",
        (
            "Hay {active_count} ventas activas hoy pero ninguna en "
            "efectivo. Si la panadería estuvo abierta al público, "
            "revisá que el método de pago se esté registrando bien."
        ),
    ),
    (
        "eod.voided_rate",
        "Tasa de anulaciones alta",
        (
            "Hoy se anularon {voided} de {total} ventas "
            "({rate_pct}). Normal es 1-3%. Si fue error de operador, "
            "no hay problema. Si fue sistemático, revisá el flujo de "
            "cobro."
        ),
    ),
    (
        "eod.uninvoiced_factura",
        "Ventas con factura sin número",
        (
            "{bad_count} ventas marcadas como 'factura' no tienen número "
            "de timbrado. DNIT puede multar. IDs: {ids}"
        ),
    ),
    (
        "eod.negative_grand_total",
        "Total de ventas del día NEGATIVO",
        (
            "El total de hoy (sin anuladas) es Gs. {total:,}. No debería "
            "ser negativo. Probable bug en la migración o en la "
            "lógica de descuento. IDs: {ids}"
        ),
    ),
]


def _migration_116_eod_alert_templates(conn: Any) -> None:
    """Seed the 4 EOD anomaly alert templates into ``message_template``.

    Channel is ``email`` because the alerts are sent via
    ``app/observability/email.send_alert``. Locale is ``es-PY`` to match
    the rest of the operator-facing copy.

    Uses ``INSERT OR IGNORE`` (SQLite) so re-running the migration is
    idempotent and never clobbers an operator edit.

    Local import to avoid circular dependency: this migration file is
    imported by ``app.rms.db`` at module load time.
    """
    from app.rms.db import _bump_schema_version

    # Sanity check: message_template table should exist from migration 044.
    exists = conn.execute(
        text(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='message_template'"
        )
    ).fetchone()
    if not exists:
        # Migration 044 hasn't run yet — fall through. Migration ordering
        # guarantees 044 runs first; this is a defensive guard only.
        return

    for key, subject, body in _ALERT_TEMPLATES:
        conn.execute(
            text(
                """
                INSERT OR IGNORE INTO message_template
                    (channel, key, subject, body, locale, is_active, version, updated_at)
                VALUES
                    ('email', :key, :subject, :body, 'es-PY', 1, 1, CURRENT_TIMESTAMP)
                """
            ),
            {"key": key, "subject": subject, "body": body},
        )

    # Bump schema version per convention — each migration owns its bump.
    _bump_schema_version(conn, 116)