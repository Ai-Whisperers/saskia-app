"""Tests for app.services.template_render — m helper for templates."""

import pytest

from app.services.template_render import templates


@pytest.fixture
def m():
    """Return the `m` Jinja global."""
    return templates.env.globals["m"]


class TestMoneyGs:
    def test_basic_int(self, m):
        assert m.gs(8_696_000) == "Gs. 8.696.000"

    def test_zero(self, m):
        assert m.gs(0) == "Gs. 0"

    def test_none(self, m):
        assert m.gs(None) == "—"

    def test_negative(self, m):
        assert m.gs(-500) == "-Gs. 500"

    def test_gs_plain_no_prefix(self, m):
        assert m.gs_plain(8_696_000) == "8.696.000"
        assert m.gs_plain(None) == "—"


class TestStockBadge:
    def test_zero_is_agotado(self, m):
        assert (
            m.stock_badge(0, 5) == '<span class="badge--stock-out" title="Sin stock">Agotado</span>'
        )

    def test_negative_is_negativo(self, m):
        assert "Negativo" in m.stock_badge(-1, 5)

    def test_below_min_is_bajo(self, m):
        assert (
            m.stock_badge(2, 5)
            == '<span class="badge--stock-low" title="Stock bajo el mínimo">Bajo</span>'
        )

    def test_at_or_above_min_is_ok(self, m):
        assert "OK" in m.stock_badge(5, 5)
        assert "OK" in m.stock_badge(10, 5)

    def test_none_stock_safe(self, m):
        assert "Agotado" in m.stock_badge(None, 5)

    def test_string_stock_safe(self, m):
        # No exception on bad input — returns the em-dash placeholder badge
        assert "—" in m.stock_badge("not-a-number", 5)


class TestMarginPct:
    def test_basic(self, m):
        assert m.margin_pct(50, 100) == "50.0%"

    def test_zero_ventas(self, m):
        assert m.margin_pct(50, 0) == "—"

    def test_none_ventas(self, m):
        assert m.margin_pct(50, None) == "—"

    def test_decimal_precision(self, m):
        # 33.33%
        assert m.margin_pct(100, 300) == "33.3%"


class TestTopListCard:
    def test_empty(self, m):
        out = m.top_list_card("Top", [], "Gs. ", "icon-up")
        assert "Top" in out
        assert "Sin datos" in out

    def test_with_items(self, m):
        items = [{"name": "Cheesecake", "value": 2_340_000}]
        out = m.top_list_card("Top", items, "Gs. ", "icon-up")
        assert "Cheesecake" in out
        assert "2.340.000" in out
        assert "icon-up" in out
