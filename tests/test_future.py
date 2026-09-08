"""tests/test_future.py — verify app/rms/future.py (E25).

Per docs/plans/2026-09-07-saskia-complete-epic-plan-v3.md E25.

Covers:
- Role enum has admin/cashier/viewer
- ROLE_PERMISSIONS covers all 3 roles
- user_has_permission: admin gets everything, cashier can't edit,
  unknown → admin (legacy)
- ReportSpec + register_report + list_reports + get_report
- register_report raises on duplicate key
- Built-in reports are pre-registered (>= 5)
- FeatureFlag defaults: is_flag_enabled reads app_meta override
- set_flag persists to app_meta
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.rms.future import (
    BUILTIN_FLAGS,
    ROLE_PERMISSIONS,
    ReportSpec,
    Role,
    get_report,
    is_flag_enabled,
    list_reports,
    register_report,
    set_flag,
    user_has_permission,
)
from app.rms.models import AppMeta


def test_role_enum_has_three_values():
    assert {r.value for r in Role} == {"admin", "cashier", "viewer"}


def test_role_permissions_keys_present():
    for r in Role:
        assert r in ROLE_PERMISSIONS
        assert isinstance(ROLE_PERMISSIONS[r], set)


def test_user_has_permission_admin_gets_all():
    for perm in ["sales.create", "products.edit", "backups.run", "users.manage"]:
        assert user_has_permission(Role.ADMIN, perm), f"admin missing {perm}"


def test_user_has_permission_cashier_cannot_edit():
    assert user_has_permission(Role.CASHIER, "sales.create") is True
    assert user_has_permission(Role.CASHIER, "products.edit") is False
    assert user_has_permission(Role.CASHIER, "backups.run") is False


def test_user_has_permission_viewer_readonly():
    assert user_has_permission(Role.VIEWER, "reports.view") is True
    assert user_has_permission(Role.VIEWER, "sales.create") is False


def test_user_has_permission_unknown_role_is_admin():
    """Legacy / unknown roles granted admin (avoids lockout)."""
    assert user_has_permission("root", "anything") is True
    assert user_has_permission("weirdo", "backups.run") is True


def test_user_has_permission_accepts_string_and_enum():
    """Both Role enum and string accepted."""
    assert user_has_permission("cashier", "sales.create") is True
    assert user_has_permission(Role.CASHIER, "sales.create") is True


def test_register_and_list_reports():
    register_report(ReportSpec(
        "test.foo", "Test", "Test report", group="test",
    ))
    reports = list_reports(group="test")
    keys = {r.key for r in reports}
    assert "test.foo" in keys


def test_register_raises_on_duplicate():
    register_report(ReportSpec("dup.k", "K", "x", group="dup"))
    with pytest.raises(ValueError, match="already registered"):
        register_report(ReportSpec("dup.k", "K", "x", group="dup"))


def test_get_report_raises_on_missing():
    with pytest.raises(KeyError):
        get_report("nope.never.registered")


def test_builtin_reports_pre_registered():
    reports = list_reports()
    keys = {r.key for r in reports}
    assert len(reports) >= 5
    assert "monthly_iva" in keys
    assert "libro_ventas" in keys
    assert "daily_summary" in keys
    assert "product_margin" in keys


def test_list_reports_by_group():
    accounting = {r.key for r in list_reports(group="accounting")}
    assert "monthly_iva" in accounting
    assert "libro_ventas" in accounting
    ops = {r.key for r in list_reports(group="operations")}
    assert "daily_summary" in ops


def test_builtin_flags_count():
    assert len(BUILTIN_FLAGS) >= 4


def test_is_flag_enabled_default_true_when_unset(session_factory):
    """When no app_meta override, return the FeatureFlag default."""
    s = session_factory()
    try:
        # Don't override; should read the default
        # "experiments.seasonal_hint" default is True
        assert is_flag_enabled(s, "experiments.seasonal_hint") is True
        # "ui.dark_mode" default is False
        assert is_flag_enabled(s, "ui.dark_mode") is False
    finally:
        s.close()


def test_is_flag_enabled_unknown_key_defaults_to_false(session_factory):
    s = session_factory()
    try:
        assert is_flag_enabled(s, "nonexistent.flag") is False
    finally:
        s.close()


def test_set_flag_creates_app_meta_row(session_factory):
    s = session_factory()
    try:
        set_flag(s, "test.my_flag", True)
        s.commit()
        row = s.execute(
            select(AppMeta).where(AppMeta.key == "flag.test.my_flag")
        ).scalar_one()
        assert row.value in ("true", "True")
    finally:
        s.close()


def test_set_flag_updates_existing_row(session_factory):
    s = session_factory()
    try:
        set_flag(s, "test.toggle", False)
        s.commit()
        # Now flip it
        set_flag(s, "test.toggle", True)
        s.commit()
        # Verify toggle is now true
        assert is_flag_enabled(s, "test.toggle") is True
    finally:
        s.close()


def test_is_flag_enabled_reads_override(session_factory):
    s = session_factory()
    try:
        set_flag(s, "ui.dark_mode", True)
        s.commit()
        # Now reads "true"
        assert is_flag_enabled(s, "ui.dark_mode") is True
    finally:
        s.close()
