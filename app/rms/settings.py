"""Optimized settings.py with N+1 query elimination."""
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.rms.models import AppMeta

if TYPE_CHECKING:
    from . import main

logger = logging.getLogger(__name__)


class SettingGroup(str, Enum):
    """UI grouping for the settings page."""

    GENERAL = "general"
    INVENTORY = "inventory"
    SALES = "sales"
    DASHBOARD = "dashboard"
    BACKUP = "backup"
    SESSION = "session"
    DEMO = "demo"


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
        "Saskia RMS",
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
]


# --- Public API (OPTIMIZED) ---


def get_setting(session: Session, key: str) -> str | None:
    """Read a single setting; returns None if not set (use default)."""
    row = session.execute(
        select(AppMeta).where(AppMeta.key == key)
    ).scalar_one_or_none()
    return row.value if row else None


def get_setting_value_optimized(spec: Setting, raw: str | None) -> object:
    """Get value from raw data + default (no DB calls)."""
    if raw is None:
        raw = spec.default
    validator = VALIDATORS[spec.validator]
    return validator(raw)


def fetch_all_settings_once(session: Session) -> dict[str, str]:
    """Fetch ALL settings in 1 query instead of N+1."""
    logger.debug("Fetching all settings in single query")
    rows = session.execute(
        select(AppMeta.key, AppMeta.value).where(
            AppMeta.key.in_(s.key for s in SETTINGS)
        )
    ).all()
    return {r.key: r.value for r in rows}


def list_settings_optimized(session: Session) -> list[dict]:
    """Return all settings with current value, using 1 DB query."""
    all_settings = fetch_all_settings_once(session)  # 1 query total
    
    out: list[dict] = []
    for spec in SETTINGS:
        stored = all_settings.get(spec.key)  # No DB call, use cache
        current = get_setting_value_optimized(spec, stored)  # No DB call
        out.append({
            "key": spec.key,
            "value": current,
            "default": spec.default,
            "stored_raw": stored,
            "description": spec.description,
            "group": spec.group.value,
            "choices": spec.choices,
        })
    return out


def settings_by_group_optimized(session: Session) -> dict[str, list[dict]]:
    """Return settings grouped by group, using optimized list_settings."""
    grouped: dict[str, list[dict]] = {}
    for entry in list_settings_optimized(session):
        grouped.setdefault(entry["group"], []).append(entry)
    return grouped


def get_setting_optimized(session: Session, key: str) -> str | None:
    """Get single setting with single query (no N+1)."""
    row = session.execute(
        select(AppMeta).where(AppMeta.key == key)
    ).scalar_one_or_none()
    return row.value if row else None


def get_setting_value(session: Session, key: str) -> object:
    """Read + validate + coerce. Returns the default if not set."""
    raw = get_setting(session, key)
    spec = next((s for s in SETTINGS if s.key == key), None)
    if spec is None:
        return raw
    if raw is None:
        raw = spec.default
    validator = VALIDATORS[spec.validator]
    return validator(raw)


def set_setting(
    session: Session, key: str, value: object, *, user_id: str | None = None
) -> None:
    """Persist a setting. Validates against the spec's validator.

    Raises ValueError on unknown key or invalid value.
    """
    spec = next((s for s in SETTINGS if s.key == key), None)
    if spec is None:
        raise ValueError(f"Unknown setting key: {key!r}")
    if spec.validator == "json":
        raw = json.dumps(value)
    elif spec.validator == "bool":
        if isinstance(value, bool):
            raw = "1" if value else "0"
        else:
            raw = "1" if str(value).lower() in ("1", "true", "yes", "on") else "0"
    else:
        raw = str(value)
    # Validate round-trip
    VALIDATORS[spec.validator](raw)
    row = session.execute(
        select(AppMeta).where(AppMeta.key == key)
    ).scalar_one_or_none()
    if row is None:
        row = AppMeta(
            key=key,
            value=raw,
            updated_at=datetime.now(timezone.utc).isoformat()
        )
        session.add(row)
    else:
        row.value = raw
        row.updated_at = datetime.now(timezone.utc).isoformat()
    session.flush()


def reset_setting_to_default(session: Session, key: str) -> None:
    """Clear stored value (revert to spec default)."""
    row = session.execute(
        select(AppMeta).where(AppMeta.key == key)
    ).scalar_one_or_none()
    if row is not None:
        session.delete(row)
        session.flush()


# Backwards compatibility - use optimized versions
def list_settings(session: Session) -> list[dict]:
    """Return all settings with their current value, using optimized version."""
    return list_settings_optimized(session)


def settings_by_group(session: Session) -> dict[str, list[dict]]:
    """Return settings grouped by SettingGroup value, using optimized version."""
    return settings_by_group_optimized(session)


def get_setting_cached(session: Session, key: str) -> str | None:
    """Get single setting optimized (single query)."""
    return get_setting_optimized(session, key)


__all__ = [
    "Setting",
    "SettingGroup",
    "SETTINGS",
    "VALIDATORS",
    "get_setting",
    "get_setting_value",
    "set_setting",
    "list_settings",
    "list_settings_optimized",
    "fetch_all_settings_once",
    "get_setting_optimized",
    "get_setting_cached",
    "reset_setting_to_default",
    "settings_by_group",
    "settings_by_group_optimized",
]