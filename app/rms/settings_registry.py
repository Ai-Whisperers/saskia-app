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
from app.rms.settings_runtime import settings_get, settings_set


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

# All 30 settings (data, not code)
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
