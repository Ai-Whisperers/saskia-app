"""app/rms/settings_registry.py — the operator-facing settings registry.

Sprint 2.1 (2026-10-07 completion): the 42-key registry MOVED here
verbatim from the deleted app/rms/settings.py, re-backed onto
SettingsKV (JSON values via settings_runtime) instead of AppMeta
string rows. One persistence layer: settings_kv.

Compatibility notes:
- get_setting_value(key) keeps its signature and validator semantics
  (production.demand_snapshot_ttl_seconds consumer in production_demand).
- set_setting(key, value) validates via the spec's validator, stores
  JSON in settings_kv.
- reset_setting_to_default deletes the KV row (default wins again).
- Data migration 114 copied any pre-existing AppMeta values for these
  keys into settings_kv at upgrade time.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.rms.models import SettingsKV


# ---------------------------------------------------------------------
# Low-level KV accessors. These were historically in settings_runtime.py,
# but they belong here because settings_registry is the SettingsKV layer.
# settings_runtime now re-imports them from this module (one direction),
# breaking the historical bidirectional cycle.
# ---------------------------------------------------------------------
def settings_get(session: Session, key: str, default: Any = None) -> Any:
    """Read one key from settings_kv (parsed JSON). Returns default if missing."""
    row = session.execute(select(SettingsKV).where(SettingsKV.key == key)).scalar_one_or_none()
    if row is None:
        return default
    try:
        return json.loads(row.value_json)
    except (TypeError, ValueError):
        return default


def settings_set(session: Session, key: str, value: Any) -> None:
    """Upsert one key into settings_kv (serialized as JSON)."""
    import json as _json

    payload = _json.dumps(value)
    row = session.execute(select(SettingsKV).where(SettingsKV.key == key)).scalar_one_or_none()
    if row is None:
        row = SettingsKV(key=key, value_json=payload)
        session.add(row)
    else:
        row.value_json = payload
    session.flush()


class SettingGroup(str, Enum):
    """UI grouping for the settings page."""

    GENERAL = "general"
    BRANDING = "branding"  # logo, favicon, hero, accent color — preview in admin
    INVENTORY = "inventory"
    SALES = "sales"
    DASHBOARD = "dashboard"
    BACKUP = "backup"
    SESSION = "session"
    DEMO = "demo"
    PRODUCTION = "production"  # PRODUCCION-V2 Fase 3: demand cache TTL
    LOYALTY = "loyalty"  # Batch B1 (2026-10-07) — POS suggestion thresholds
    EOD = "eod"  # Batch B2 (2026-10-07) — end-of-day anomaly detector thresholds
    ALERTS = "alerts"  # Batch B3 (2026-10-07) — alert dispatch rate limit
    RATE_LIMIT = "rate_limit"  # Batch B5 (2026-10-07) — login + write + read throttles


@dataclass
class Setting:
    """A single operator-facing setting."""

    key: str
    default: str
    validator: str  # name of validator fn in VALIDATORS
    description: str
    group: SettingGroup
    choices: list[str] = field(default_factory=list)  # for enum-style settings


def _bool_validator(value: str) -> bool:
    return value.lower() in ("1", "true", "yes", "on")


def _int_validator(value: str) -> int:
    return int(value)


def _float_validator(value: str) -> float:
    return float(value)


def _str_validator(value: str) -> str:
    return str(value)


def _json_validator(value: str) -> object:
    return json.loads(value)


VALIDATORS = {
    "bool": _bool_validator,
    "int": _int_validator,
    "float": _float_validator,
    "str": _str_validator,
    "json": _json_validator,
}

# All 60 settings (data, not code)
SETTINGS: list[Setting] = [
    # GENERAL (6)
    Setting(
        "general.business_name",
        "Sazón",
        "str",
        "Nombre del negocio (aparece en tickets y PDF)",
        SettingGroup.GENERAL,
    ),
    Setting(
        "general.currency_symbol",
        "Gs.",
        "str",
        "Símbolo de moneda (Gs. o ₲)",
        SettingGroup.GENERAL,
        choices=["Gs.", "₲", "Pyg"],
    ),
    Setting(
        "general.decimal_places",
        "0",
        "int",
        "Decimales para montos (0 para guaraníes enteros)",
        SettingGroup.GENERAL,
        choices=["0", "2"],
    ),
    Setting(
        "general.tax_mode",
        "included",
        "str",
        "Si los precios incluyen IVA o no",
        SettingGroup.GENERAL,
        choices=["included", "excluded"],
    ),
    Setting(
        "general.locale",
        "es_PY",
        "str",
        "Locale para formateo de fechas y números",
        SettingGroup.GENERAL,
        choices=["es_PY", "es_ES", "en_US"],
    ),
    Setting(
        "general.timezone",
        "America/Asuncion",
        "str",
        "Zona horaria para agrupación de ventas",
        SettingGroup.GENERAL,
        choices=["America/Asuncion", "UTC"],
    ),
    Setting(
        "ui.theme",
        "system",
        "str",
        "Tema de color (claro, oscuro o sistema)",
        SettingGroup.GENERAL,
        choices=["system", "light", "dark"],
    ),
    # BRANDING (8) — business-specific visual identity
    Setting(
        "branding.business_name",
        "Sazón",
        "str",
        "Nombre comercial — aparece en login, sidebar, tickets, PDF",
        SettingGroup.BRANDING,
    ),
    Setting(
        "branding.tagline",
        "",
        "str",
        "Eslogan corto debajo del nombre (opcional)",
        SettingGroup.BRANDING,
    ),
    Setting(
        "branding.business_type",
        "restaurant",
        "str",
        "Tipo de negocio (define defaults e iconos)",
        SettingGroup.BRANDING,
        choices=["restaurant", "panaderia", "cafeteria", "bar", "heladeria", "food_truck", "otro"],
    ),
    Setting(
        "branding.logo_filename",
        "",
        "str",
        "Logo principal (PNG/JPG/SVG). Subir desde /admin/branding",
        SettingGroup.BRANDING,
    ),
    Setting(
        "branding.favicon_filename",
        "",
        "str",
        "Icono del navegador (ICO/PNG 32×32 o 192×192)",
        SettingGroup.BRANDING,
    ),
    Setting(
        "branding.hero_filename",
        "",
        "str",
        "Imagen principal de /login (opcional, 1200×600 ideal)",
        SettingGroup.BRANDING,
    ),
    Setting(
        "branding.primary_color",
        "#6B4423",
        "str",
        "Color primario (botones, acentos). Formato hex #RRGGBB",
        SettingGroup.BRANDING,
    ),
    Setting(
        "branding.contact_email",
        "",
        "str",
        "Email de contacto — aparece en PDF y tickets",
        SettingGroup.BRANDING,
    ),
    Setting(
        "branding.contact_phone",
        "",
        "str",
        "Teléfono de contacto — aparece en tickets",
        SettingGroup.BRANDING,
    ),
    Setting(
        "branding.address",
        "",
        "str",
        "Dirección del local — aparece en tickets y PDF",
        SettingGroup.BRANDING,
    ),
    # INVENTORY (6)
    Setting(
        "inventory.default_min_stock",
        "0",
        "float",
        "Stock mínimo por defecto para ingredientes nuevos",
        SettingGroup.INVENTORY,
    ),
    Setting(
        "inventory.alert_lead_time_days",
        "7",
        "int",
        "Días de margen para alertas de stock bajo",
        SettingGroup.INVENTORY,
    ),
    Setting(
        "inventory.stale_days",
        "30",
        "int",
        "Días sin movimiento para marcar 'stock muerto'",
        SettingGroup.INVENTORY,
    ),
    Setting(
        "inventory.default_unit",
        "kg",
        "str",
        "Unidad por defecto para ingredientes nuevos",
        SettingGroup.INVENTORY,
        choices=["kg", "g", "l", "ml", "und"],
    ),
    Setting(
        "inventory.auto_deduct_on_sale",
        "1",
        "bool",
        "Descontar stock automáticamente al vender",
        SettingGroup.INVENTORY,
    ),
    Setting(
        "inventory.warn_negative_stock",
        "1",
        "bool",
        "Advertir si el stock queda negativo al vender",
        SettingGroup.INVENTORY,
    ),
    # SALES (5)
    Setting(
        "sales.default_payment_method",
        "efectivo",
        "str",
        "Método de pago por defecto",
        SettingGroup.SALES,
        choices=["efectivo", "transferencia", "SIPAP"],
    ),
    Setting(
        "sales.require_customer_for_evento",
        "0",
        "bool",
        "Pedir cliente para ventas tipo 'evento'",
        SettingGroup.SALES,
    ),
    Setting(
        "sales.max_void_hours",
        "24",
        "int",
        "Horas después de venta que se permite anular",
        SettingGroup.SALES,
    ),
    Setting(
        "sales.print_receipt_on_post",
        "0",
        "bool",
        "Imprimir recibo al confirmar venta (E18)",
        SettingGroup.SALES,
    ),
    Setting(
        "sales.low_stock_warning_threshold",
        "5",
        "int",
        "Cantidad mínima de stock para warning visual",
        SettingGroup.SALES,
    ),
    # Pre-sale (B6, 2026-10-07) — operator-tunable thresholds for the
    # /ventas/nueva pre-billing checklist (app/rms/sales/pre_sale_check.py).
    # Legacy module-level MAX_DISCOUNT_PCT_WITHOUT_OVERRIDE,
    # MAX_QTY_PER_SALE, LOW_STOCK_WARN_THRESHOLD_PCT now alias
    # DEFAULT_PRE_SALE_CONFIG (set below) — backward compat.
    Setting(
        "pre_sale.max_qty_per_sale",
        "999",
        "int",
        "Cantidad máxima por línea de venta (blocker si excede)",
        SettingGroup.SALES,
    ),
    Setting(
        "pre_sale.max_discount_pct",
        "20",
        "int",
        "% descuento máximo sin override (warning si excede)",
        SettingGroup.SALES,
    ),
    Setting(
        "pre_sale.low_stock_warn_pct",
        "25",
        "int",
        "% de stock teórico bajo el que se dispara warning",
        SettingGroup.SALES,
    ),
    # DASHBOARD (5)
    Setting(
        "dashboard.default_period",
        "today",
        "str",
        "Período por defecto del dashboard",
        SettingGroup.DASHBOARD,
        choices=["today", "week", "current_month", "last_month"],
    ),
    Setting(
        "dashboard.chart_style",
        "bar",
        "str",
        "Estilo preferido de gráficos",
        SettingGroup.DASHBOARD,
        choices=["bar", "line"],
    ),
    Setting(
        "dashboard.show_margins",
        "1",
        "bool",
        "Mostrar columna de margen en ventas",
        SettingGroup.DASHBOARD,
    ),
    Setting(
        "dashboard.daily_summary_optin",
        "0",
        "bool",
        "Recibir resumen diario por email (E14)",
        SettingGroup.DASHBOARD,
    ),
    Setting(
        "dashboard.top_n_products",
        "10",
        "int",
        "Top N productos en el dashboard",
        SettingGroup.DASHBOARD,
    ),
    # BACKUP (3)
    Setting(
        "backup.daily_backup_enabled",
        "1",
        "bool",
        "Backup automático diario a R2 (E20)",
        SettingGroup.BACKUP,
    ),
    Setting(
        "backup.notification_email",
        "",
        "str",
        "Email para notificaciones de backup",
        SettingGroup.BACKUP,
    ),
    Setting(
        "backup.retention_days",
        "30",
        "int",
        "Días de retención para backups locales",
        SettingGroup.BACKUP,
    ),
    # SESSION (3)
    Setting(
        "session.session_lifetime_hours",
        "12",
        "int",
        "Duración máxima de sesión",
        SettingGroup.SESSION,
    ),
    Setting(
        "session.remember_me_days",
        "30",
        "int",
        "Duración de 'recordarme'",
        SettingGroup.SESSION,
    ),
    Setting(
        "session.max_concurrent_per_user",
        "3",
        "int",
        "Máximo de sesiones concurrentes por usuario",
        SettingGroup.SESSION,
    ),
    # DEMO (2)
    Setting(
        "demo.banner_enabled",
        "1",
        "bool",
        "Mostrar banner de 'demo data' en el dashboard",
        SettingGroup.DEMO,
    ),
    Setting(
        "demo.reset_seed_enabled",
        "0",
        "bool",
        "Permitir resetear datos demo desde la UI",
        SettingGroup.DEMO,
    ),
    # PRODUCCION-V2 Fase 3: cache TTL for production_demand_snapshot.
    # 0 disables the cache (always recompute). Default 300s = 5min.
    Setting(
        "production.demand_snapshot_ttl_seconds",
        "300",
        "int",
        "Segundos antes de recomputar demanda. 0 = deshabilitar cache.",
        SettingGroup.PRODUCTION,
    ),
    # LOYALTY (11) — Batch B1 (2026-10-07)
    # POS auto-suggest thresholds. Operator-tunable from /admin/settings
    # under the "Loyalty" tab. Defaults match the original module-level
    # constants in app/rms/loyalty/suggestions.py before extraction.
    Setting(
        "loyalty.lapsed_days_bronze",
        "21",
        "int",
        "Días sin visita para sugerir descuento (cliente Bronze)",
        SettingGroup.LOYALTY,
    ),
    Setting(
        "loyalty.lapsed_days_silver",
        "30",
        "int",
        "Días sin visita para sugerir descuento (cliente Silver)",
        SettingGroup.LOYALTY,
    ),
    Setting(
        "loyalty.lapsed_days_gold",
        "45",
        "int",
        "Días sin visita para sugerir descuento (cliente Gold)",
        SettingGroup.LOYALTY,
    ),
    Setting(
        "loyalty.lapsed_discount_pct_bronze",
        "10",
        "int",
        "% descuento 'vuelve pronto' (Bronze)",
        SettingGroup.LOYALTY,
    ),
    Setting(
        "loyalty.lapsed_discount_pct_silver",
        "7",
        "int",
        "% descuento 'vuelve pronto' (Silver)",
        SettingGroup.LOYALTY,
    ),
    Setting(
        "loyalty.lapsed_discount_pct_gold",
        "5",
        "int",
        "% descuento 'vuelve pronto' (Gold)",
        SettingGroup.LOYALTY,
    ),
    Setting(
        "loyalty.birthday_window_days",
        "7",
        "int",
        "Días antes del cumple para empezar a sugerir",
        SettingGroup.LOYALTY,
    ),
    Setting(
        "loyalty.birthday_discount_pct",
        "15",
        "int",
        "% descuento sugerido para cumple",
        SettingGroup.LOYALTY,
    ),
    Setting(
        "loyalty.points_dormant_threshold",
        "50",
        "int",
        "Puntos mínimos para activar sugerencia 'puntos dormidos'",
        SettingGroup.LOYALTY,
    ),
    Setting(
        "loyalty.cross_sell_min_sales",
        "3",
        "int",
        "Ventas mínimas para que un producto sea 'cross-sell popular' (definido, sin uso actual)",
        SettingGroup.LOYALTY,
    ),
    Setting(
        "loyalty.max_suggestions",
        "3",
        "int",
        "Máximo de sugerencias por cliente en la tarjeta POS",
        SettingGroup.LOYALTY,
    ),
    # EOD (3) — Batch B2 (2026-10-07)
    # End-of-day anomaly detector thresholds. Operator-tunable from
    # /admin/settings under the "EOD" tab.
    Setting(
        "eod.voided_rate_threshold",
        "0.10",
        "float",
        "Tasa mínima de anulaciones (0.0–1.0) para disparar alerta 'tasa alta'",
        SettingGroup.EOD,
    ),
    Setting(
        "eod.voided_rate_min_sales",
        "3",
        "int",
        "Ventas mínimas del día para evaluar la tasa de anulaciones (evita ruido en días lentos)",
        SettingGroup.EOD,
    ),
    Setting(
        "eod.max_uninvoiced_ids_displayed",
        "10",
        "int",
        "Máximo de IDs de ventas sin facturar a listar en el email de alerta",
        SettingGroup.EOD,
    ),
    # ALERTS (1) — Batch B3 (2026-10-07)
    Setting(
        "alerts.max_per_day",
        "50",
        "int",
        "Máximo de alertas por proceso por día (rate limit de dispatch)",
        SettingGroup.ALERTS,
    ),
    # BACKUP (3) — Batch B4 (2026-10-07)
    # These thresholds previously lived as module-level constants in
    # app/services/auto_backup.py. Now operator-tunable.
    Setting(
        "backup.auto_threshold_hours",
        "24",
        "int",
        "Horas desde último backup para gatillar backup automático al startup",
        SettingGroup.BACKUP,
    ),
    Setting(
        "backup.warn_threshold_days",
        "7",
        "int",
        "Días desde último backup para mostrar warning en la UI",
        SettingGroup.BACKUP,
    ),
    Setting(
        "backup.keep_last_n",
        "30",
        "int",
        "Cantidad de backups locales a mantener antes de podar los más viejos",
        SettingGroup.BACKUP,
    ),
    # RATE_LIMIT (5) — Batch B5 (2026-10-07)
    Setting(
        "rate_limit.login_max_failures",
        "5",
        "int",
        "Máximo de login.failure por ventana antes de bloquear IP (E3.S2)",
        SettingGroup.RATE_LIMIT,
    ),
    Setting(
        "rate_limit.login_window_minutes",
        "5",
        "int",
        "Ventana deslizante para login.failure (minutos)",
        SettingGroup.RATE_LIMIT,
    ),
    Setting(
        "rate_limit.write_max_per_minute",
        "10",
        "int",
        "Máximo de writes por minuto por IP (sale.create, merma.register, etc.)",
        SettingGroup.RATE_LIMIT,
    ),
    Setting(
        "rate_limit.read_max_per_minute",
        "60",
        "int",
        "Máximo de reads pesados por minuto por IP (/api/search, /reportes/*)",
        SettingGroup.RATE_LIMIT,
    ),
    Setting(
        "rate_limit.read_window_seconds",
        "60",
        "int",
        "Ventana deslizante para reads pesados (segundos)",
        SettingGroup.RATE_LIMIT,
    ),
]


# --- Public API (OPTIMIZED) ---


def _kv_get_raw(session: Session, key: str) -> str | None:
    """Stored value as raw string (registry validators parse it)."""
    row = session.execute(select(SettingsKV).where(SettingsKV.key == key)).scalar_one_or_none()
    if row is None:
        return None
    return row.value_json


def get_setting(session: Session, key: str) -> str | None:
    """Read a single setting's raw value; None if not set.

    Contract preserved from the AppMeta era: the returned string is the
    bare value (validators parse it). KV stores JSON, so a stored string
    is unwrapped from its quotes here; non-string JSON passes through as
    its serialized text (json.loads-able, same as before).
    """
    raw = _kv_get_raw(session, key)
    if raw is None:
        return None
    import json as _json

    try:
        unwrapped = _json.loads(raw)
    except (TypeError, ValueError):
        return raw
    if isinstance(unwrapped, str):
        return unwrapped
    return raw


def get_setting_value(session: Session, key: str) -> Any:
    """Read + validate + coerce. Returns the spec default if not set."""
    spec = next((s for s in SETTINGS if s.key == key), None)
    if spec is None:
        # Unknown key: pass through unvalidated (legacy contract)
        raw = _kv_get_raw(session, key)
        if raw is None:
            return None
        import json as _json

        try:
            return _json.loads(raw)
        except (TypeError, ValueError):
            return raw
    if spec.validator == "json":
        return settings_get(session, key, _json_validator(spec.default))
    raw = _kv_get_raw(session, key)
    if raw is None:
        raw = spec.default
    else:
        # KV stores JSON: a bare string is quoted; unwrap for the
        # string-based validators exactly as set_setting wrote it.
        import json as _json

        try:
            unwrapped = _json.loads(raw)
        except (TypeError, ValueError):
            unwrapped = raw
        if not isinstance(unwrapped, str):
            return unwrapped  # already the coerced JSON type
        raw = unwrapped
    return VALIDATORS[spec.validator](raw)


def set_setting(session: Session, key: str, value: Any, *, user_id: str | None = None) -> None:
    """Persist a setting. Validates via the spec; raises ValueError on
    unknown key or invalid value. Stored as JSON in settings_kv."""
    spec = next((s for s in SETTINGS if s.key == key), None)
    if spec is None:
        raise ValueError(f"Unknown setting key: {key!r}")
    if spec.validator == "json":
        settings_set(session, key, value)
        return
    if spec.validator == "bool":
        if isinstance(value, bool):
            raw = "1" if value else "0"
        else:
            raw = "1" if str(value).lower() in ("1", "true", "yes", "on") else "0"
    else:
        raw = str(value)
    VALIDATORS[spec.validator](raw)  # round-trip validation
    settings_set(session, key, raw)


def reset_setting_to_default(session: Session, key: str) -> None:
    """Delete the stored row so the spec default applies again."""
    spec = next((s for s in SETTINGS if s.key == key), None)
    if spec is None:
        raise ValueError(f"Unknown setting key: {key!r}")
    row = session.execute(select(SettingsKV).where(SettingsKV.key == key)).scalar_one_or_none()
    if row is not None:
        session.delete(row)
        session.flush()


def fetch_all_settings_once(session: Session) -> dict[str, str]:
    """All registry keys' stored raw values in 1 query."""
    rows = session.execute(
        select(SettingsKV.key, SettingsKV.value_json).where(
            SettingsKV.key.in_(s.key for s in SETTINGS)
        )
    ).all()
    return {r.key: r.value_json for r in rows}


def list_settings(session: Session) -> list[dict]:
    """All settings with current value (single DB query)."""
    stored_map = fetch_all_settings_once(session)
    out: list[dict] = []
    for spec in SETTINGS:
        stored = stored_map.get(spec.key)
        # current value via the same path as get_setting_value
        if spec.validator == "json":
            current = settings_get(session, spec.key, _json_validator(spec.default))
        elif stored is None:
            current = VALIDATORS[spec.validator](spec.default)
        else:
            import json as _json

            try:
                unwrapped = _json.loads(stored)
            except (TypeError, ValueError):
                unwrapped = stored
            current = (
                unwrapped
                if not isinstance(unwrapped, str)
                else VALIDATORS[spec.validator](unwrapped)
            )
        out.append(
            {
                "key": spec.key,
                "value": current,
                "default": spec.default,
                "stored_raw": stored,
                "description": spec.description,
                "group": spec.group.value,
                "choices": spec.choices,
            }
        )
    return out


def settings_by_group(session: Session) -> dict[str, list[dict]]:
    """Group list_settings() output by SettingGroup."""
    grouped: dict[str, list[dict]] = {}
    for entry in list_settings(session):
        grouped.setdefault(entry["group"], []).append(entry)
    return grouped
