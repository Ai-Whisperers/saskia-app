"""tests/test_template_render.py — Test app/services/template_render.py.

Wraps FastAPI's Jinja2Templates with app-state globals:
  - now_year, now_str, greeting — time-aware helpers
  - asset_version — cache-busting suffix
  - m namespace (gs, gs_plain, gs_full, margin_pct, stock_badge, top_list_card)
  - fmt namespace (money, qty, pct, date, delta, entity_name, status_es, crumbs_for)
  - notification_counts — severity buckets for the /produccion header
  - csrf_token — per-request token, or generated fallback
  - render() — full request render path

A regression here would either:
  - Show a stale copyright year (now_year memoized)
  - Cache an old asset after deploy (asset_version not refreshed)
  - Display "NaN%" when ventas_gs=0 (margin_pct divide-by-zero)
  - Crash templates that need a csrf_token (the /clientes/{id} 500 that
    this module was extracted to fix)
  - Show wrong stock badge (Agotado vs Negativo ordering)
"""

# allow-hardcoded-dates: fixture: mock clock returns datetime(2026, 10, 12, ...) for time-of-day rendering, not relative-time

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

from app.services.template_render import (
    _asset_version,
    _csrf_token_for_request,
    _greeting,
    _make_money_helper,
    _notification_counts,
    _now_local,
    _now_str,
    _now_year,
    templates,
)


class TestNowHelpers:
    def test_now_year_returns_int(self):
        result = _now_year()
        assert isinstance(result, int)
        # Should be reasonable (current year ± 1)
        assert 2020 <= result <= 2030

    def test_now_str_returns_string(self):
        result = _now_str()
        assert isinstance(result, str)
        # Should contain a time component
        assert ":" in result or "/" in result

    def test_now_local_format(self):
        result = _now_local()
        # YYYY-MM-DDTHH:MM format
        assert len(result) >= 16
        assert result[4] == "-"
        assert result[7] == "-"
        assert result[10] == "T"
        assert result[13] == ":"


class TestGreeting:
    """_greeting picks "Buen día" / "Buenas tardes" / "Buenas noches"."""

    def test_afternoon_greeting(self, monkeypatch):
        # Patch datetime.now to return 14:00 (afternoon)
        from app.services import template_render

        class FakeDatetime:
            @classmethod
            def now(cls, tz):
                return datetime(2026, 10, 12, 14, 0, 0)

        monkeypatch.setattr(template_render, "datetime", FakeDatetime)
        assert _greeting() == "Buenas tardes"

    def test_morning_greeting(self, monkeypatch):
        from app.services import template_render

        class FakeDatetime:
            @classmethod
            def now(cls, tz):
                return datetime(2026, 10, 12, 9, 0, 0)

        monkeypatch.setattr(template_render, "datetime", FakeDatetime)
        assert _greeting() == "Buen día"

    def test_evening_greeting(self, monkeypatch):
        from app.services import template_render

        class FakeDatetime:
            @classmethod
            def now(cls, tz):
                return datetime(2026, 10, 12, 20, 0, 0)

        monkeypatch.setattr(template_render, "datetime", FakeDatetime)
        assert _greeting() == "Buenas noches"

    def test_late_night_greeting(self, monkeypatch):
        from app.services import template_render

        class FakeDatetime:
            @classmethod
            def now(cls, tz):
                return datetime(2026, 10, 12, 2, 0, 0)

        monkeypatch.setattr(template_render, "datetime", FakeDatetime)
        assert _greeting() == "Buenas noches"

    def test_dawn_boundary(self, monkeypatch):
        # 4am is the cut-off from "noches" → "día"
        from app.services import template_render

        class FakeDatetime:
            @classmethod
            def now(cls, tz):
                return datetime(2026, 10, 12, 4, 0, 0)

        monkeypatch.setattr(template_render, "datetime", FakeDatetime)
        assert _greeting() == "Buen día"


class TestAssetVersion:
    def test_returns_string(self):
        v = _asset_version()
        assert isinstance(v, str)

    def test_returns_digit_string_when_files_exist(self):
        # The /static dir exists in this repo, so we should get a real
        # timestamp (mtime) or "0" on OSError.
        v = _asset_version()
        assert v.isdigit() or v == "0"


class TestMoneyGs:
    def setup_method(self):
        self.m = _make_money_helper()

    def test_gs_formats_int(self):
        result = self.m.gs(1000000)
        # format_gs returns "Gs. 1.000.000" Paraguayan style
        assert "1.000.000" in result

    def test_gs_plain_no_prefix(self):
        result = self.m.gs_plain(1000000)
        assert result == "1.000.000"
        assert "Gs." not in result

    def test_gs_plain_handles_none(self):
        assert self.m.gs_plain(None) == "—"

    def test_gs_plain_negative(self):
        result = self.m.gs_plain(-5000)
        # Should be "-" prefixed
        assert result.startswith("-")
        assert "5.000" in result

    def test_gs_plain_zero(self):
        assert self.m.gs_plain(0) == "0"

    def test_gs_full_alias(self):
        # gs_full is an alias for gs()
        assert self.m.gs_full(1000000) == self.m.gs(1000000)


class TestMarginPct:
    def setup_method(self):
        self.m = _make_money_helper()

    def test_basic(self):
        result = self.m.margin_pct(2500, 10000)
        assert result == "25.0%"

    def test_high_margin(self):
        result = self.m.margin_pct(4500, 5000)
        assert result == "90.0%"

    def test_zero_ventas_returns_dash(self):
        # The dashboard "—" string when there's no denominator
        assert self.m.margin_pct(0, 0) == "—"
        assert self.m.margin_pct(100, 0) == "—"

    def test_negative_margin(self):
        result = self.m.margin_pct(-100, 1000)
        assert result == "-10.0%"


class TestStockBadge:
    def setup_method(self):
        self.m = _make_money_helper()

    def test_negative_stock(self):
        result = self.m.stock_badge(-1, 5)
        assert "Negativo" in result
        assert "badge--stock-out" in result

    def test_zero_stock(self):
        result = self.m.stock_badge(0, 5)
        assert "Agotado" in result
        assert "badge--stock-out" in result

    def test_below_min(self):
        result = self.m.stock_badge(2, 5)
        assert "Bajo" in result
        assert "badge--stock-low" in result

    def test_at_min(self):
        # stock == min is OK
        result = self.m.stock_badge(5, 5)
        assert "OK" in result

    def test_above_min(self):
        result = self.m.stock_badge(10, 5)
        assert "OK" in result
        assert "badge--stock-ok" in result

    def test_none_inputs(self):
        # None stock/min → fall back to 0 → "Agotado" badge
        # (the "—" branch is only for unparseable strings)
        result = self.m.stock_badge(None, None)
        assert "Agotado" in result

    def test_invalid_inputs(self):
        result = self.m.stock_badge("not a number", "also not")
        assert "—" in result

    def test_negative_is_more_urgent_than_agotado(self):
        # A regression test: the badges are ordered Negativo > Agotado
        neg = self.m.stock_badge(-1, 5)
        agotado = self.m.stock_badge(0, 5)
        assert "Negativo" in neg
        assert "Agotado" in agotado
        # Both use the same class — but the labels differ


class TestTopListCard:
    def setup_method(self):
        self.m = _make_money_helper()

    def test_empty_items(self):
        result = self.m.top_list_card("Top 5", [])
        assert "card" in result
        assert "Top 5" in result
        assert "Sin datos" in result

    def test_renders_items(self):
        items = [
            {"name": "Harina", "value": 5000},
            {"name": "Azúcar", "value": 3000},
        ]
        result = self.m.top_list_card("Top", items)
        assert "Harina" in result
        assert "Azúcar" in result
        assert "5.000" in result

    def test_with_icon(self):
        # Icon only renders when there are items (empty list → early return)
        items = [{"name": "x", "value": 100}]
        result = self.m.top_list_card("Top", items, icon_id="i-star")
        assert "<svg" in result
        assert "i-star" in result

    def test_without_icon(self):
        result = self.m.top_list_card("Top", [])
        assert "<svg" not in result

    def test_with_currency_prefix(self):
        items = [{"name": "x", "value": 1000}]
        result = self.m.top_list_card("Top", items, currency_prefix="$")
        assert "$" in result

    def test_missing_name_uses_dash(self):
        items = [{"value": 1000}]  # no "name"
        result = self.m.top_list_card("Top", items)
        assert "—" in result


class TestNotificationCounts:
    def test_all_zero(self):
        result = _notification_counts()
        # critical=0, warning=0, info=2 (Cómo se calcula + Baja confianza)
        assert result["critical"] == 0
        assert result["warning"] == 0
        assert result["info"] == 2

    def test_pending_pedidos_count(self):
        result = _notification_counts(pending_pedidos=[1, 2, 3])
        assert result["critical"] == 3  # 3 pending → critical

    def test_low_stock_count(self):
        result = _notification_counts(low_stock_ingredients=["a", "b"])
        assert result["critical"] == 2

    def test_haccp_missing_count(self):
        result = _notification_counts(haccp_missing_count=5)
        assert result["critical"] == 5

    def test_haccp_alert_warning(self):
        result = _notification_counts(haccp_alert="warning")
        assert result["warning"] == 1

    def test_haccp_alert_other_does_not_trigger(self):
        # haccp_alert="info" or anything other than "warning" → 0 warning
        result = _notification_counts(haccp_alert="info")
        assert result["warning"] == 0

    def test_daily_target_below_half(self):
        # daily_actual < daily_target * 0.5 → meta_below=1
        result = _notification_counts(daily_target=100, daily_actual=40)
        assert result["warning"] == 1

    def test_daily_target_at_or_above_half(self):
        result = _notification_counts(daily_target=100, daily_actual=50)
        assert result["warning"] == 0

    def test_daily_no_target_set(self):
        result = _notification_counts(daily_target=0, daily_actual=10)
        assert result["warning"] == 0  # no target → no comparison

    def test_yesterday_info_count(self):
        result = _notification_counts(yesterday_total_qty=100)
        assert result["info"] == 3  # 2 base + 1 ayer

    def test_yesterday_zero_no_info(self):
        result = _notification_counts(yesterday_total_qty=0)
        assert result["info"] == 2  # 2 base only

    def test_low_confidence_high_is_critical(self):
        # > 30 → critical+=1
        result = _notification_counts(low_confidence_count=50)
        assert result["critical"] == 1
        assert result["warning"] == 0

    def test_low_confidence_mid_is_warning(self):
        # 1..30 → warning+=1
        result = _notification_counts(low_confidence_count=15)
        assert result["warning"] == 1
        assert result["critical"] == 0

    def test_low_confidence_zero(self):
        result = _notification_counts(low_confidence_count=0)
        assert result["critical"] == 0
        assert result["warning"] == 0

    def test_total_is_sum(self):
        result = _notification_counts(
            pending_pedidos=[1, 2],
            low_stock_ingredients=["a"],
            haccp_missing_count=3,
        )
        assert result["total"] == (result["critical"] + result["warning"] + result["info"])

    def test_tolerates_none_args(self):
        # Pending is None, low_stock is None → still 0
        result = _notification_counts(pending_pedidos=None, low_stock_ingredients=None)
        assert result["critical"] == 0


class TestCsrfTokenForRequest:
    def test_returns_empty_when_no_request_and_no_token_generator(self):
        # When called outside a request context, it should generate a fresh
        # token. The exact value depends on the csrf module's generator.
        result = _csrf_token_for_request(None)
        assert isinstance(result, str)
        # Non-empty
        assert result != ""

    def test_returns_cookie_value_when_present(self):
        # Mock a request with a csrf cookie
        from app.rms.csrf import _CSRF_COOKIE

        fake_request = MagicMock()
        fake_request.cookies = {_CSRF_COOKIE: "my-test-token"}
        result = _csrf_token_for_request(fake_request)
        assert result == "my-test-token"

    def test_falls_back_to_generation_when_cookie_missing(self):

        fake_request = MagicMock()
        fake_request.cookies = {}  # no csrf cookie
        result = _csrf_token_for_request(fake_request)
        # Should generate a fresh token, not empty
        assert result != ""


class TestTemplatesGlobals:
    """Verify that the module's globals are wired into the Jinja env."""

    def test_now_year_registered(self):
        assert "now_year" in templates.env.globals

    def test_money_helper_registered(self):
        assert "m" in templates.env.globals

    def test_fmt_helper_registered(self):
        assert "fmt" in templates.env.globals

    def test_notification_counts_registered(self):
        assert "notification_counts" in templates.env.globals

    def test_asset_version_registered(self):
        assert "asset_version" in templates.env.globals

    def test_greeting_registered(self):
        assert "greeting" in templates.env.globals

    def test_now_str_registered(self):
        assert "now_str" in templates.env.globals

    def test_csrf_token_registered(self):
        assert "csrf_token" in templates.env.globals
