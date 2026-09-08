"""app/rms/future.py — Future-facing extensibility seams (E25).

Per docs/plans/2026-09-07-saskia-complete-epic-plan-v3.md E25.

This module provides:
- PermissionStub: read-only role scaffolding (admin/cashier/viewer)
  ready for full RBAC implementation
- ReportNamespace: registry pattern for plugging in additional reports
- FeatureFlag: per-deployment toggle loaded from app_meta
- skill_view(...) stub: list which skills are active

These are SEAMS, not finished features. The intent is to make sure
later feature work (full RBAC, more reports, advanced admin) has a
known shape to plug into, without inflating scope today.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.rms.models import AppMeta

# --- Roles (RBAC stub) ---


class Role(str, Enum):
    """User roles for the future RBAC system.

    Today only Role.ADMIN is granted; Role.CASHIER/VIEWER exist as
    forward-compatible values in the User.role column.
    """

    ADMIN = "admin"
    CASHIER = "cashier"
    VIEWER = "viewer"


# Maps role -> set of permission strings
ROLE_PERMISSIONS: dict[Role, set[str]] = {
    Role.ADMIN: {
        "sales.create", "sales.void",
        "products.edit", "recipes.edit", "ingredients.edit",
        "imports.run", "settings.change",
        "customers.edit", "waste.log",
        "tags.edit",
        "reports.view", "reports.export",
        "backups.run", "users.manage",
    },
    Role.CASHIER: {
        "sales.create", "reports.view",
        "customers.read",
    },
    Role.VIEWER: {
        "reports.view", "customers.read",
    },
}


def user_has_permission(role: str | Role, permission: str) -> bool:
    """Check if a role string grants a permission.

    Today, any role not in {admin,cashier,viewer} is treated as admin
    (legacy: only the admin user exists).
    """
    if isinstance(role, str):
        try:
            r = Role(role)
        except ValueError:
            return True  # legacy / unknown → admin
    else:
        r = role
    return permission in ROLE_PERMISSIONS.get(r, set())


# --- Report registry (extensible namespace) ---


@dataclass
class ReportSpec:
    """Metadata for one registered report."""

    key: str
    label: str
    description: str
    group: str = "reports"
    handler: Callable[..., Any] | None = None


_REPORTS: dict[str, ReportSpec] = {}


def register_report(spec: ReportSpec) -> None:
    """Register a report under a unique key."""
    if spec.key in _REPORTS:
        raise ValueError(f"Report already registered: {spec.key}")
    _REPORTS[spec.key] = spec


def list_reports(group: str | None = None) -> list[ReportSpec]:
    """List registered reports. Optional group filter."""
    out = list(_REPORTS.values())
    if group:
        out = [r for r in out if r.group == group]
    return sorted(out, key=lambda r: r.key)


def get_report(key: str) -> ReportSpec:
    """Look up a registered report by key."""
    if key not in _REPORTS:
        raise KeyError(f"No report registered under key '{key}'")
    return _REPORTS[key]


# Built-in report registrations (lazy; import the handlers here so
# nothing circular).
def _register_builtins() -> None:

    register_report(ReportSpec(
        "monthly_iva",
        "Monthly IVA breakdown",
        "Paraguay 10% IVA by month",
        group="accounting",
    ))
    register_report(ReportSpec(
        "libro_ventas",
        "Libro de Ventas",
        "Chronological sales ledger with IVA extraction",
        group="accounting",
    ))
    register_report(ReportSpec(
        "daily_summary",
        "Daily summary",
        "Revenue + iva + cogs + margin + warnings for one day",
        group="operations",
    ))
    register_report(ReportSpec(
        "daily_summary_full",
        "Daily summary (full)",
        "Extended daily summary including low stock + top products",
        group="operations",
    ))
    register_report(ReportSpec(
        "product_margin",
        "Product margin summary",
        "Per-product revenue + cost + margin in a window",
        group="accounting",
    ))


_register_builtins()


# --- Feature flags ---


@dataclass
class FeatureFlag:
    """A toggleable feature in the app."""

    key: str
    default: bool
    description: str


BUILTIN_FLAGS: dict[str, FeatureFlag] = {
    "ui.dark_mode": FeatureFlag(
        "ui.dark_mode", False, "Operator-toggled dark mode"),
    "sales.show_void_button": FeatureFlag(
        "sales.show_void_button", True,
        "Whether the void-sale button is shown in the sales UI"),
    "imports.drive_shape_only": FeatureFlag(
        "imports.drive_shape_only", False,
        "Restrict xlsx imports to the canonical Drive shape"),
    "experiments.seasonal_hint": FeatureFlag(
        "experiments.seasonal_hint", True,
        "Show the seasonal-hint banner on the dashboard"),
}


def is_flag_enabled(
    session: Session,
    key: str,
) -> bool:
    """Resolve a feature flag: app_meta override > built-in default."""
    spec = BUILTIN_FLAGS.get(key)
    default = spec.default if spec else False
    row = session.execute(
        select(AppMeta).where(AppMeta.key == f"flag.{key}")
    ).scalar_one_or_none()
    if row is None:
        return default
    val = row.value
    if isinstance(val, str):
        return val.lower() in ("1", "true", "yes", "on")
    return bool(val)


def set_flag(
    session: Session,
    key: str,
    enabled: bool,
) -> None:
    """Set a feature flag in app_meta."""
    row = session.execute(
        select(AppMeta).where(AppMeta.key == f"flag.{key}")
    ).scalar_one_or_none()
    if row is None:
        session.add(AppMeta(
            key=f"flag.{key}",
            value="true" if enabled else "false",
            updated_at="",
        ))
    else:
        row.value = "true" if enabled else "false"


__all__ = [
    "Role",
    "ROLE_PERMISSIONS",
    "user_has_permission",
    "ReportSpec",
    "register_report",
    "list_reports",
    "get_report",
    "FeatureFlag",
    "BUILTIN_FLAGS",
    "is_flag_enabled",
    "set_flag",
]
