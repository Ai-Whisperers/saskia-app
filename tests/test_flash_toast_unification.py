"""Tests for the flash_toast macro (BACKLOG Tier 2 unification).

The flash system lives in ``app/templates/_components/atoms.html`` and
exposes a single ``ui.flash_toast(request)`` call. It:

  1. Reads the ``flash`` query param from the request
  2. Looks it up in a static ``messages`` dict (severity, message)
  3. Falls back to a parameterized template dict (key:N:D format) if the
     key is not static
  4. Renders a small <script> that calls window.UIToast.show() — no
     inline HTML escaping needed since tojson is used

These tests exercise the macro directly (no client/server needed) to
lock the contract for the 50+ keys added during the unification pass.
"""

from __future__ import annotations

import glob
import os
import re

import pytest
from jinja2 import Environment, FileSystemLoader

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
os.chdir(REPO_ROOT)


@pytest.fixture(scope="module")
def flash_toast_macro():
    """Extract the flash_toast macro body as a renderable template."""
    with open("app/templates/_components/atoms.html", encoding="utf-8") as f:
        atoms_src = f.read()

    m = re.search(
        r"\{% macro flash_toast\(req, query_name=.flash.\) -%\}(.*?)\{%- endmacro %\}",
        atoms_src,
        re.DOTALL,
    )
    if not m:
        pytest.fail("flash_toast macro not found in atoms.html")
    return m.group(1)


@pytest.fixture(scope="module")
def env():
    return Environment(loader=FileSystemLoader("app/templates"))


@pytest.fixture
def template(env, flash_toast_macro):
    return env.from_string(flash_toast_macro)


def _render(template, flash_value):
    """Render the macro with the given flash value, return the script body."""
    from types import SimpleNamespace

    req = SimpleNamespace()
    req.query_params = {"flash": flash_value}
    return template.render(req=req, query_name="flash")


def _extract_message(rendered):
    """Pull the toast message out of the rendered script.

    The macro uses ``|tojson`` for XSS safety, which JSON-escapes
    non-ASCII characters (e.g. ``ó`` becomes ``\\u00f3``). We
    normalize that so tests can match against raw Spanish copy.
    """
    m = re.search(r"message:\s*'([^']*)'", rendered)
    if m:
        return m.group(1)
    m = re.search(r'message:\s*"([^"]*)"', rendered)
    if m:
        return m.group(1)
    return None


def _normalize(s):
    """Undo JSON ``\\uXXXX`` escapes for substring matching."""
    if s is None:
        return None
    return re.sub(
        r"\\u([0-9a-fA-F]{4})",
        lambda m: chr(int(m.group(1), 16)),
        s,
    )


# ─────────────────────────────────────────────────────────────────────
# Static keys — pre-existing (the refactor must not break these)
# ─────────────────────────────────────────────────────────────────────


class TestExistingStaticKeys:
    """Lock the behavior of keys that existed before the unification."""

    @pytest.mark.parametrize(
        "key,expected_msg",
        [
            ("sale_created", "Venta registrada"),
            ("sale_void_ok", "Venta anulada"),
            ("pedido_created", "Pedido creado"),
            ("pedido_fulfilled", "Pedido cumplido"),
            ("pedido_cancelled", "Pedido cancelado"),
            ("product_created", "Producto creado"),
            ("product_updated", "Producto actualizado"),
            ("product_deleted", "Producto eliminado"),
            ("recipe_created", "Receta creada"),
            ("ingredient_created", "Ingrediente creado"),
            ("customer_created", "Cliente creado"),
            ("supplier_created", "Proveedor creado"),
            ("waste_logged", "Merma registrada"),
            ("settings_saved", "Configuración guardada"),
            ("saved", "Guardado"),
            ("created", "Creado"),
            ("updated", "Actualizado"),
            ("deleted", "Eliminado"),
            ("error", "Hubo un error"),
            ("unauthorized", "No tenés permiso"),
            ("not_found", "No se encontró"),
            ("refund_ok", "Reembolso registrado"),
        ],
    )
    def test_existing_key_renders(self, template, key, expected_msg):
        rendered = _render(template, key)
        assert "UIToast.show" in rendered, f"{key}: no toast script"
        msg = _normalize(_extract_message(rendered))
        assert msg and expected_msg in msg, f"{key}: expected '{expected_msg}' in '{msg}'"


# ─────────────────────────────────────────────────────────────────────
# New static keys added during the unification pass
# ─────────────────────────────────────────────────────────────────────


class TestNewStaticKeys:
    """The ~25 new keys that replaced free-text flash strings."""

    @pytest.mark.parametrize(
        "key,expected_msg",
        [
            # Users
            ("user_created", "Usuario creado"),
            ("user_updated", "Usuario actualizado"),
            ("user_deleted", "Usuario eliminado"),
            ("user_not_found", "Usuario no encontrado"),
            ("user_duplicate", "nombre de usuario ya existe"),
            ("user_password_too_short", "al menos 6 caracteres"),
            ("user_cannot_delete_self", "eliminarte"),
            # EOD
            ("eod_saved", "Cierre guardado"),
            ("eod_duplicate", "Ya hiciste el cierre"),
            # Caja
            ("caja_open", "Caja abierta"),
            ("caja_closed", "Caja cerrada"),
            ("caja_error", "Error en la caja"),
            # Fiado
            ("fiado_charge", "Cargo registrado"),
            ("fiado_payment", "Pago de fiado"),
            ("fiado_status", "Estado de fiado"),
            ("fiado_duplicate", "ya estaba registrado"),
            ("fiado_error", "Error al registrar"),
            # OCR
            ("ocr_ok", "importado por OCR"),
            ("ocr_empty", "No se detect"),
            # Misc
            ("empty", "No hay datos para mostrar"),
            ("sin_plantilla", "No hay plantilla semanal"),
            ("rate_limited", "Demasiados intentos"),
            ("sale_duplicate", "Ya existe una venta"),
            ("pedido_fulfill_duplicate", "ya fue marcado como cumplido"),
            # Customer merge
            ("customer_deleted", "Clientes eliminados"),
            ("customers_merged", "Clientes fusionados"),
            ("customer_invalid_ids", "IDs inv"),
            ("customer_no_duplicates_selected", "No se seleccionaron duplicados"),
            # Settings
            ("settings_info_saved", "Informaci"),
            ("settings_fiscal_saved", "Configuraci"),
            ("settings_theme_saved", "Tema guardado"),
            ("inventory_filled_already", "Todos los ingredientes"),
            # Station guard warnings
            ("eod_wrong_station_gerencia", "Gerencia"),
            ("eod_wrong_station_cocina", "Cocina"),
            # Production template load
            ("plantilla_cargada", "Plantilla semanal"),
            ("ya_existia", "ya existía"),
        ],
    )
    def test_new_key_renders(self, template, key, expected_msg):
        rendered = _render(template, key)
        assert "UIToast.show" in rendered, f"{key}: no toast script"
        msg = _normalize(_extract_message(rendered))
        assert msg and expected_msg in msg, f"{key}: expected '{expected_msg}' in '{msg}'"


# ─────────────────────────────────────────────────────────────────────
# Parameterized templates — "key:N:D" format with format() placeholders
# ─────────────────────────────────────────────────────────────────────


class TestParameterizedTemplates:
    """Keys with format placeholders (mirrors points_redeemed:N:D)."""

    def test_points_redeemed_formats(self, template):
        rendered = _render(template, "points_redeemed:10:10000")
        msg = _normalize(_extract_message(rendered))
        assert msg and "10" in msg and "10,000" in msg

    def test_users_bulk_deleted_zero_skipped(self, template):
        rendered = _render(template, "users_bulk_deleted:5:0")
        msg = _normalize(_extract_message(rendered))
        assert msg and "5 cliente(s) eliminado(s)" in msg
        assert "omitido" not in msg

    def test_users_bulk_deleted_with_skipped(self, template):
        rendered = _render(template, "users_bulk_deleted:5:2")
        msg = _normalize(_extract_message(rendered))
        assert msg and "5 cliente(s) eliminado(s)" in msg
        assert "2 omitido" in msg

    def test_products_bulk_deleted_with_skipped(self, template):
        rendered = _render(template, "products_bulk_deleted:3:1")
        msg = _normalize(_extract_message(rendered))
        assert msg and "3 producto(s) eliminado(s)" in msg
        assert "1 omitido" in msg

    def test_pedidos_bulk_fulfilled(self, template):
        rendered = _render(template, "pedidos_bulk_fulfilled:7")
        msg = _normalize(_extract_message(rendered))
        assert msg and "7 pedido(s)" in msg

    def test_pedidos_bulk_cancelled(self, template):
        rendered = _render(template, "pedidos_bulk_cancelled:4")
        msg = _normalize(_extract_message(rendered))
        assert msg and "4 pedido(s)" in msg

    def test_pedido_stock_insufficient(self, template):
        rendered = _render(template, "pedido_stock_insufficient:3")
        msg = _normalize(_extract_message(rendered))
        assert msg and "Stock insuficiente para 3" in msg

    def test_settings_seed_demo_count(self, template):
        rendered = _render(template, "settings_seed_demo_count:10:5:3")
        msg = _normalize(_extract_message(rendered))
        assert msg
        assert "10" in msg and "5" in msg and "3" in msg
        assert "ingredientes" in msg

    def test_settings_seed_sazon_count(self, template):
        rendered = _render(template, "settings_seed_sazon_count:10:5:3:2:8:1")
        msg = _normalize(_extract_message(rendered))
        assert msg
        for n in ["10", "5", "3", "2", "8", "1"]:
            assert n in msg, f"Expected {n} in {msg!r}"
        assert "ingredientes" in msg
        assert "clientes" in msg
        assert "ventas" in msg
        assert "pedidos" in msg

    def test_settings_theme_saved_p(self, template):
        rendered = _render(template, "settings_theme_saved_p:oscuro")
        msg = _normalize(_extract_message(rendered))
        assert msg and "oscuro" in msg

    def test_settings_demo_error_detail(self, template):
        rendered = _render(template, "settings_demo_error_detail:TypeError")
        msg = _normalize(_extract_message(rendered))
        assert msg and "TypeError" in msg

    def test_inventory_filled_with_skipped(self, template):
        rendered = _render(template, "inventory_filled:5:10.5:2")
        msg = _normalize(_extract_message(rendered))
        assert msg and "5 ingrediente(s)" in msg
        assert "10.5" in msg
        assert "2 sin m" in msg

    def test_inventory_filled_no_skipped(self, template):
        rendered = _render(template, "inventory_filled:5:10.5:0")
        msg = _normalize(_extract_message(rendered))
        assert msg and "5 ingrediente(s)" in msg
        assert "10.5" in msg


# ─────────────────────────────────────────────────────────────────────
# Negative cases — free-text strings should NOT render
# ─────────────────────────────────────────────────────────────────────


class TestFreeTextRejected:
    """Free-text flash values that the refactor replaced should be empty."""

    @pytest.mark.parametrize(
        "free_text",
        [
            "Cierre guardado",
            "Usuario creado",
            "Usuario actualizado",
            "Usuario eliminado",
            "Usuario no encontrado",
            "fake_key_does_not_exist",
            "this is not a real key",
        ],
    )
    def test_free_text_renders_nothing(self, template, free_text):
        rendered = _render(template, free_text)
        assert "UIToast.show" not in rendered, f"Free-text {free_text!r} should not render a toast"


# ─────────────────────────────────────────────────────────────────────
# Structural contract — the macro emits a <script> with the right shape
# ─────────────────────────────────────────────────────────────────────


class TestMacroContract:
    """The macro must emit valid JS and use tojson (not raw string concat)."""

    def test_emits_script_tag(self, template):
        rendered = _render(template, "sale_created")
        assert "<script>" in rendered

    def test_uses_window_UIToast(self, template):
        rendered = _render(template, "sale_created")
        assert "window.UIToast" in rendered

    def test_uses_tojson_in_source(self, template):
        """tojson is the XSS-safe path for embedding Spanish copy.

        Note: we check the *source* atoms.html (not the rendered output)
        because ``|tojson`` is a Jinja filter that runs at render time —
        the rendered string already has the JSON-escaped message.
        """
        with open("app/templates/_components/atoms.html", encoding="utf-8") as f:
            atoms_src = f.read()
        assert "tojson" in atoms_src, "atoms.html must use {{ ... | tojson }} to embed messages"

    def test_handles_empty_flash(self, template):
        """No flash param = no output."""
        from types import SimpleNamespace

        req = SimpleNamespace()
        req.query_params = {}
        rendered = template.render(req=req, query_name="flash")
        assert rendered.strip() == "" or "UIToast" not in rendered

    def test_severity_is_one_of_known_values(self, template):
        """Every key should map to a known severity (success|warn|error|info)."""
        keys = [
            "sale_created",
            "sale_void_ok",
            "saved",
            "error",
            "unauthorized",
            "pedido_cancelled",
            "empty",
            "ocr_empty",
            "rate_limited",
            "inventory_filled_already",
        ]
        for k in keys:
            rendered = _render(template, k)
            m = re.search(r"severity:\s*'([^']*)'", rendered)
            sev = m.group(1) if m else None
            assert sev in {
                "success",
                "warn",
                "error",
                "info",
            }, f"{k}: severity {sev!r} is not in the known set"


# ─────────────────────────────────────────────────────────────────────
# Counts — sanity check we didn't accidentally lose keys
# ─────────────────────────────────────────────────────────────────────


class TestKeyCounts:
    """The refactor expanded the key surface. Lock the floor."""

    def test_at_least_60_static_keys(self):
        """The static messages dict should have grown from ~40 to 60+."""
        with open("app/templates/_components/atoms.html", encoding="utf-8") as f:
            atoms_src = f.read()

        m = re.search(
            r"\{% set messages = \{(.*?)\} %\}",
            atoms_src,
            re.DOTALL,
        )
        if not m:
            pytest.fail("messages dict not found")
        # Count entries by counting lines that look like 'key': ('a', 'b'),
        entries = re.findall(
            r"^\s+'[a-z_][a-z_0-9]*':\s*\(",
            m.group(1),
            re.MULTILINE,
        )
        assert len(entries) >= 60, f"Expected at least 60 static keys, found {len(entries)}"

    def test_at_least_10_parameterized_templates(self):
        """The parameterized templates dict should cover dynamic use cases."""
        with open("app/templates/_components/atoms.html", encoding="utf-8") as f:
            atoms_src = f.read()

        matches = re.findall(
            r"\{% set _templates = \{(.*?)\} %\}",
            atoms_src,
            re.DOTALL,
        )
        if len(matches) < 1:
            pytest.fail("parameterized templates dict not found")
        entries = re.findall(r"^\s*'[a-z_]+':\s*\(", matches[0], re.MULTILINE)
        assert len(entries) >= 10, (
            f"Expected at least 10 parameterized templates, found {len(entries)}"
        )


# ─────────────────────────────────────────────────────────────────────
# Template coverage — all base-extending templates include flash_toast
# ─────────────────────────────────────────────────────────────────────


class TestTemplateCoverage:
    """Every template extending base.html should include flash_toast."""

    def test_all_base_extending_templates_have_flash_toast(self):
        """Walk app/templates and confirm every base-extender has flash_toast."""
        all_files = glob.glob(
            os.path.join(REPO_ROOT, "app/templates/**/*.html"),
            recursive=True,
        )
        templates = []
        for f in all_files:
            with open(f, encoding="utf-8") as fh:
                if 'extends "base.html"' in fh.read():
                    templates.append(f)
        missing = []
        for f in templates:
            with open(f, encoding="utf-8") as fh:
                if "flash_toast" not in fh.read():
                    missing.append(os.path.relpath(f, REPO_ROOT))
        assert len(templates) > 100, f"Expected >100 templates, got {len(templates)}"
        assert not missing, f"Missing flash_toast in: {missing}"
