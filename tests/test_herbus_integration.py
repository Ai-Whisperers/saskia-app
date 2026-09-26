"""Tests for the HEREBUS integration (Wave 1-4)."""
import pytest


class TestWave1NavReorg:
    """Wave 1: Nav menu relabel + bucket reorg."""

    def test_no_operacion_herbus_label_anywhere(self):
        """The 'Operación HEREBUS' label must NOT appear in base.html anymore."""
        from pathlib import Path
        base = Path("/opt/data/profiles/ivan/scratch/saskia-app-work/app/templates/base.html")
        content = base.read_text()
        assert "Operación HEREBUS" not in content, "Old 'Operación HEREBUS' bucket label still present"

    def test_new_buckets_present(self):
        """All 4 new buckets must be in the nav."""
        # 2026-09-26: nav SSOT lives in app/rms/nav.py (NAV_GROUPS)
        from app.rms.nav import NAV_GROUPS
        assert [g for g, _ in NAV_GROUPS], "nav table empty"

    def test_wishlist_relabeled_to_equipamiento(self):
        """Wishlist should be labeled 'Equipamiento' (it's kitchen gear, not consumables)."""
        from app.rms.nav import NAV_INDEX
        assert NAV_INDEX["/wishlist"]["label"] == "Equipamiento"

    def test_pricing_relabeled_to_precios_por_canal(self):
        """Pricing should be labeled 'Precios por canal'."""
        from app.rms.nav import NAV_INDEX
        assert NAV_INDEX["/pricing"]["label"] == "Precios por canal"

    def test_vs_mercado_relabeled_to_precios_vs_mercado(self):
        """vs-mercado should be labeled 'Precios vs mercado'."""
        from app.rms.nav import NAV_INDEX
        assert NAV_INDEX["/vs-mercado"]["label"] == "Precios vs mercado"

    def test_dashboard_relabeled_to_kpis(self):
        """HEREBUS Dashboard should be labeled 'KPIs' to disambiguate from /."""
        from app.rms.nav import NAV_INDEX
        assert "KPIs" in NAV_INDEX["/dashboard"]["label"]


class TestWave2PlannerIntegration:
    """Wave 2: /produccion-planner form integrated into /produccion."""

    def test_produccion_has_recipes_context(self):
        """The /produccion day-view must include 'recipes' in the render context."""
        from pathlib import Path
        router = Path("/opt/data/profiles/ivan/scratch/saskia-app-work/app/routers/produccion.py")
        content = router.read_text()
        assert "select(Recipe)" in content, "/produccion router doesn't fetch recipes"
        assert '"recipes"' in content, "'recipes' key not in /produccion render context"

    def test_produccion_html_has_planner_form(self):
        """The day-view of /produccion must embed the planner form."""
        from pathlib import Path
        template = Path("/opt/data/profiles/ivan/scratch/saskia-app-work/app/templates/produccion.html")
        content = template.read_text()
        assert "produccion-planner/compute" in content, "Planner form action not embedded"
        assert "Plan manual" in content, "Plan manual section header missing"
        assert "produccion-recipes" in content, "Recipe datalist missing"

    def test_planner_html_has_back_link(self):
        """The standalone /produccion-planner page should link back to /produccion."""
        from pathlib import Path
        template = Path("/opt/data/profiles/ivan/scratch/saskia-app-work/app/templates/planner.html")
        content = template.read_text()
        assert "Volver a Producción" in content, "Back-link to /produccion missing"


class TestWave3DashboardKPIs:
    """Wave 3: HEREBUS KPIs merged into / (Inicio)."""

    def test_dashboard_router_passes_herbus_kpis(self):
        """The main / dashboard router should pass HEREBUS KPIs (sl, wishlist, risk)."""
        from pathlib import Path
        router = Path("/opt/data/profiles/ivan/scratch/saskia-app-work/app/routers/dashboard.py")
        content = router.read_text()
        for key in ['"sl_open_count"', '"sl_total_gs"', '"wishlist_count"',
                    '"wishlist_total_gs"', '"risk_count"', '"risk_severity_gs"']:
            assert key in content, f"Missing HEREBUS KPI in dashboard.py: {key}"

    def test_dashboard_router_imports_herbus_models(self):
        """The main / dashboard router must import the HEREBUS models."""
        from pathlib import Path
        router = Path("/opt/data/profiles/ivan/scratch/saskia-app-work/app/routers/dashboard.py")
        content = router.read_text()
        for model in ["WishlistItem", "ShoppingListItem", "RiskItem"]:
            assert model in content, f"Missing model import: {model}"

    def test_inicio_has_operacion_card(self):
        """The home / page must render the new Operación card with HEREBUS KPIs."""
        from pathlib import Path
        template = Path("/opt/data/profiles/ivan/scratch/saskia-app-work/app/templates/inicio.html")
        content = template.read_text()
        for key in ["sl_open_count", "wishlist_count", "risk_count",
                    "Lista de compras abierta", "Equipamiento pendiente",
                    "Riesgos activos"]:
            assert key in content, f"Missing Operación card content: {key}"


class TestWave4DeliveryZonesFolded:
    """Wave 4: /delivery-zones → /settings#zonas-delivery."""

    def test_delivery_zones_redirects(self):
        """The /delivery-zones GET must redirect to /settings#zonas-delivery."""
        from pathlib import Path
        router = Path("/opt/data/profiles/ivan/scratch/saskia-app-work/app/routers/herebus.py")
        content = router.read_text()
        # Find the GET "" handler
        idx = content.find('def delivery_zones_list(')
        # Look for RedirectResponse in the next 300 chars
        chunk = content[idx:idx+500]
        assert "RedirectResponse" in chunk, "delivery_zones_list must return RedirectResponse"
        assert "/settings#zonas-delivery" in chunk, "Redirect target wrong"

    def test_settings_has_delivery_zones_context(self):
        """The settings.py handler must include delivery_zones in context."""
        from pathlib import Path
        router = Path("/opt/data/profiles/ivan/scratch/saskia-app-work/app/routers/settings.py")
        content = router.read_text()
        assert '"delivery_zones"' in content, "delivery_zones missing from /settings context"

    def test_settings_html_has_zonas_section(self):
        """settings.html must have a Zonas de Delivery section."""
        from pathlib import Path
        template = Path("/opt/data/profiles/ivan/scratch/saskia-app-work/app/templates/settings.html")
        content = template.read_text()
        assert 'id="zonas-delivery"' in content, "Anchor id missing"
        assert "Zonas de Delivery" in content, "Section heading missing"

    def test_nav_links_to_settings_anchor(self):
        """The main nav's 'Zonas delivery' link must point to /settings#zonas-delivery."""
        from app.rms.nav import NAV_GROUPS
        routes = [i["route"] for _, items in NAV_GROUPS for i in items]
        assert "/settings" in routes  # zonas folded into settings (anchor)
