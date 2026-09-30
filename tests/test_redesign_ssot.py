"""tests/test_redesign_ssot.py — Phase 0 acceptance tests.

Covers: nav tables (SS-1/2/3), display formatters (F-1…F-7), and the
rendered shell (sidebar from NAV_GROUPS, CSS/JS wired).
"""
# allow-hardcoded-dates: SSOT redesign uses a fixed layout date
from __future__ import annotations

from app.rms.display import delta, entity_name, fmt_date, fmt_money, fmt_pct, fmt_qty
from app.rms.nav import (
    CRUMBS,
    NAV_GROUPS,
    NAV_INDEX,
    crumbs_for,
    status_es,
)

# ── SS-1 nav table ────────────────────────────────────────────────────

class TestNavTable:
    def test_groups_exist_and_small(self):
        labels = [g for g, _ in NAV_GROUPS]
        assert labels, "no nav groups"
        assert len(labels) <= 7, "too many sidebar groups"
        for g, items in NAV_GROUPS:
            assert 1 <= len(items) <= 8, f"group {g} out of size budget"

    def test_index_covers_all_items(self):
        flat = [i["route"] for _, items in NAV_GROUPS for i in items]
        assert set(flat) == set(NAV_INDEX.keys())
        assert len(flat) == len(set(flat)), "duplicate routes in nav"

    def test_every_item_has_label_and_icon(self):
        for _g, items in NAV_GROUPS:
            for i in items:
                assert i.get("label"), f"{i} missing label"
                assert i.get("icon"), f"{i['route']} missing icon"

    def test_canonical_names_not_english(self):
        for route, item in NAV_INDEX.items():
            for word in ("Wishlist", "Suppliers", "Reorder", "Shopping"):
                assert word not in item["label"], f"{route} label leaks English: {item['label']}"


# ── SS-2 breadcrumbs ──────────────────────────────────────────────────

class TestCrumbs:
    def test_exact_routes(self):
        assert crumbs_for("/ventas") == [("Inicio", "/"), ("Ventas", None)]
        assert crumbs_for("/suppliers")[-1][0] == "Proveedores"
        assert crumbs_for("/reorder")[-1][0] == "Reponer"
        assert crumbs_for("/wishlist")[-1][0] == "Equipamiento"

    def test_entity_routes_with_name(self):
        c = crumbs_for("/clientes/7", "María López")
        assert [x[0] for x in c] == ["Inicio", "Clientes", "María López"]
        assert c[-1][1] is None  # current page not linked

    def test_entity_edit_action(self):
        c = crumbs_for("/clientes/7/editar", "María López")
        assert [x[0] for x in c] == ["Inicio", "Clientes", "María López", "Editar"]
        assert c[-2][1] == "/clientes"  # entity links to parent list? No — to itself
        # entity crumb links to nothing (page exists at /clientes/7)
        assert c[-1][1] is None

    def test_unknown_falls_back_to_inicio(self):
        assert crumbs_for("/nope") == [("Inicio", "/")]

    def test_all_spanish(self):
        for entries in CRUMBS.values():
            for label, _ in entries:
                assert label == label.strip() and label


# ── SS-3 status map ───────────────────────────────────────────────────

class TestStatusEs:
    def test_loyalty_tiers_spanish(self):
        assert status_es("bronze") == ("Bronce", "neutral")
        assert status_es("silver") == ("Plata", "info")

    def test_pedido_lifecycle(self):
        assert status_es("pending")[0] == "Pendiente"
        assert status_es("ready")[1] == "ok"

    def test_unknown_passthrough_neutral(self):
        label, sev = status_es("weird_state")
        assert sev == "neutral" and label


# ── F-track formatters ────────────────────────────────────────────────

class TestFmtMoney:
    def test_basic(self):
        assert fmt_money(18000) == "Gs. 18.000"
        assert fmt_money(0) == "Gs. 0"
        assert fmt_money(1234567) == "Gs. 1.234.567"

    def test_negative(self):
        assert fmt_money(-500).startswith("-Gs.")

    def test_tolerant(self):
        assert fmt_money(None) == "—"
        assert fmt_money("18000") == "—"
        assert fmt_money(True) == "—"


class TestFmtQty:
    def test_trim_and_comma(self):
        assert fmt_qty(0.4, "kg") == "0,4 kg"
        assert fmt_qty(2.0, "u.") == "2 u."
        assert fmt_qty(0.3, "kg") == "0,3 kg"

    def test_none(self):
        assert fmt_qty(None, "kg") == "— kg"
        assert fmt_qty(None) == "—"


class TestFmtPct:
    def test_decimals(self):
        assert fmt_pct(68) == "68%"
        assert fmt_pct(0.8) == "0,8%"

    def test_none(self):
        assert fmt_pct(None) == "—"


class TestFmtDate:
    def test_modes(self):
        assert fmt_date("2026-09-26", "table") == "26/09/2026"
        assert fmt_date("2026-09-26", "prose") == "sáb 26 sep 2026"
        assert fmt_date("2026-09-26", "iso") == "2026-09-26"


class TestDelta:
    def test_neutral_empty_rule(self):
        d = delta(0, 5000)
        assert d["empty"] is True and d["pct"] is None

    def test_normal(self):
        d = delta(120000, 100000)
        assert d["direction"] == "up" and abs(d["pct"] - 20) < 0.01

    def test_no_base(self):
        assert delta(50, 0)["direction"] == "up"


class TestEntityName:
    def test_hash_guard(self):
        assert entity_name("Producto 99b78b3b") == "Producto sin nombre"
        assert entity_name("Ingrediente d02a8eb4") == "Ingrediente sin nombre"

    def test_real_name_passthrough(self):
        assert entity_name("Café con leche") == "Café con leche"
        assert entity_name(None) == "—"
        assert entity_name("") == "Sin nombre"


# ── Rendered shell uses SSOT ──────────────────────────────────────────

class TestShellRendersNav:
    def test_sidebar_from_nav_table(self, client):
        r = client.get("/ventas")
        assert r.status_code == 200
        for group, _items in NAV_GROUPS:
            assert group in r.text, f"sidebar group {group} missing"
        # canonical labels present
        assert "Equipamiento" in r.text
        assert "KPIs mensuales" in r.text

    def test_components_css_js_wired(self, client):
        r = client.get("/ventas")
        assert "app-components.css" in r.text
        assert "app-components.js" in r.text

    def test_components_assets_serve(self, client):
        for path in ("/static/app-components.css", "/static/app-components.js"):
            assert client.get(path).status_code == 200, path


# ── /produccion/manana must live on the page, not the sidebar ─────────

class TestMananaSidebarAndButtons:
    """`/produccion/manana` was removed from the sidebar (Operación was at 6
    items and the duplicate crowded it). The route is now surfaced as a
    button on `/produccion` and `/inicio`. If a future agent re-adds it to
    the sidebar OR removes the buttons, this test fails."""

    def test_manana_not_in_sidebar_nav(self):
        flat = [i["route"] for _, items in NAV_GROUPS for i in items]
        assert "/produccion/manana" not in flat, (
            "/produccion/manana should not be in the sidebar — "
            "it's a button on /produccion and /"
        )

    def test_manana_button_on_inicio(self, client):
        r = client.get("/")
        assert r.status_code == 200
        assert 'href="/produccion/manana"' in r.text, (
            "inicio.html must link to /produccion/manana (button in hero)"
        )

    def test_manana_button_on_produccion(self, client):
        r = client.get("/produccion")
        assert r.status_code == 200
        assert 'href="/produccion/manana"' in r.text, (
            "produccion.html must link to /produccion/manana "
            "(button next to Día/Semana/Mes tabs)"
        )

    def test_manana_route_still_serves(self, client):
        """Removing the sidebar link must not break the route."""
        r = client.get("/produccion/manana")
        assert r.status_code == 200, (
            "/produccion/manana must still render — only the sidebar entry "
            "was removed"
        )
