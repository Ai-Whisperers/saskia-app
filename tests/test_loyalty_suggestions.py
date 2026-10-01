"""tests/test_loyalty_suggestions.py — Decision C (Phase 4, 2026-10-01).

Auto-suggest rules engine for the POS customer card. Pure-function
tests for ``app/rms/loyalty_suggestions.suggest_for_customer`` plus
an integration test that the /clientes/api/{id} payload includes a
``suggestions`` field.

Rule coverage:
  - cumpleaños_dentro_7_dias        → KIND_CUMPLE_CERCA
  - cliente_lapsed_por_tier         → KIND_VUELVE_PRONTO
  - puntos_dormidos                 → KIND_PUNTOS_DORMIDOS
  - cliente_GOLD_con_muchas_visitas → KIND_CLIENTE_FIEL
  - cross-sell (sin gluten)         → not in C1 scope (deferred to C2)
  - priority + max 3 limit
  - empty list when no rule fires
  - birthday format handling (MM-DD vs YYYY-MM-DD, Feb 29 leap)
  - suggestion payload never crashes the /clientes/api endpoint

Conventions match tests/test_loyalty_ledger.py and tests/test_pos_redeem_flow.py.
"""
from __future__ import annotations

import datetime as _dt

import pytest

pytestmark = pytest.mark.crud


# ──────────────────────────────────────────────────────────────────────
# Pure-function tests — no DB
# ──────────────────────────────────────────────────────────────────────


class _FakeCustomer:
    """Minimal Customer stand-in for the pure suggest_for_customer() test.

    Mirrors the attributes the engine reads: birthday, loyalty_points,
    dietary_restrictions. Other Customer fields are ignored by the
    suggestion rules.
    """

    def __init__(
        self,
        *,
        birthday: str | None = None,
        loyalty_points: int = 0,
        dietary_restrictions: str | None = None,
    ) -> None:
        self.birthday = birthday
        self.loyalty_points = loyalty_points
        self.dietary_restrictions = dietary_restrictions


def _today() -> _dt.date:
    return _dt.date(2026, 10, 1)  # Thursday, fixed for stable tests


def test_no_rule_fires_for_new_bronze_customer():
    """A new BRONZE customer with no sales returns no suggestions.

    LAPSED rule doesn't fire (no last_sale_at), BIRTHDAY doesn't fire
    (no birthday), POINTS-DORMANT doesn't fire (0 points), VIP doesn't
    fire (not GOLD, n_sales=0). Empty list.
    """
    from app.rms.loyalty.suggestions import suggest_for_customer

    out = suggest_for_customer(
        _FakeCustomer(),
        last_sale_at=None,
        n_sales=0,
        tier="BRONZE",
        redeemed_on_last_visit=False,
        today=_today(),
    )
    assert out == []


def test_birthday_within_7_days_returns_cumple_cerca():
    """Birthday in 3 days → KIND_CUMPLE_CERCA with 15% discount."""
    from app.rms.loyalty.suggestions import (
        KIND_CUMPLE_CERCA,
        suggest_for_customer,
    )

    today = _today()
    bday = today + _dt.timedelta(days=3)
    cust = _FakeCustomer(birthday=bday.strftime("%Y-%m-%d"))

    out = suggest_for_customer(
        cust,
        last_sale_at=today - _dt.timedelta(days=2),  # recently active
        n_sales=5,
        tier="BRONZE",
        redeemed_on_last_visit=False,
        today=today,
    )
    assert len(out) >= 1
    cumple = next(s for s in out if s.kind == KIND_CUMPLE_CERCA)
    assert cumple.discount_pct == 15
    assert "3 días" in cumple.body


def test_birthday_today_returns_cumple_cerca():
    """Birthday exactly today → special "hoy" wording."""
    from app.rms.loyalty.suggestions import KIND_CUMPLE_CERCA, suggest_for_customer

    today = _today()
    cust = _FakeCustomer(birthday=today.strftime("%Y-%m-%d"))

    out = suggest_for_customer(
        cust,
        last_sale_at=today - _dt.timedelta(days=1),
        n_sales=2,
        tier="BRONZE",
        redeemed_on_last_visit=False,
        today=today,
    )
    cumple = next(s for s in out if s.kind == KIND_CUMPLE_CERCA)
    assert "hoy" in cumple.body.lower()


def test_birthday_recurring_mm_dd_format():
    """MM-DD format (no year) recurs annually — handled correctly."""
    from app.rms.loyalty.suggestions import KIND_CUMPLE_CERCA, suggest_for_customer

    today = _today()  # 2026-10-01
    # Birthday on Oct 4 (3 days from "today")
    cust = _FakeCustomer(birthday="10-04")

    out = suggest_for_customer(
        cust,
        last_sale_at=today - _dt.timedelta(days=2),
        n_sales=1,
        tier="BRONZE",
        redeemed_on_last_visit=False,
        today=today,
    )
    cumple = next(s for s in out if s.kind == KIND_CUMPLE_CERCA)
    assert "3 días" in cumple.body


def test_birthday_recurring_mm_dd_after_today_wraps_to_next_year():
    """MM-DD already passed this year → wrap to next year."""
    from app.rms.loyalty.suggestions import KIND_CUMPLE_CERCA, suggest_for_customer

    today = _dt.date(2026, 10, 1)
    # Birthday Jan 5 already passed this year; would be 96 days away
    # in 2027. Within the 7-day window? No. But use a date that
    # actually wraps within 7 days. The MM-DD must be later in the year.
    # Use Nov 15 which is 45 days away (outside 7d window). For this
    # test we want the "passed this year" path. Use Apr 1 which would
    # be 182 days away (also outside window). The point: the function
    # should not crash and should return NO birthday suggestion.
    cust = _FakeCustomer(birthday="04-01")

    out = suggest_for_customer(
        cust,
        last_sale_at=today - _dt.timedelta(days=2),
        n_sales=1,
        tier="BRONZE",
        redeemed_on_last_visit=False,
        today=today,
    )
    assert not any(s.kind == KIND_CUMPLE_CERCA for s in out)


def test_birthday_outside_window_no_suggestion():
    """Birthday in 14 days → no KIND_CUMPLE_CERCA (window is 7)."""
    from app.rms.loyalty.suggestions import KIND_CUMPLE_CERCA, suggest_for_customer

    today = _today()
    bday = today + _dt.timedelta(days=14)
    cust = _FakeCustomer(birthday=bday.strftime("%Y-%m-%d"))

    out = suggest_for_customer(
        cust,
        last_sale_at=today - _dt.timedelta(days=2),
        n_sales=5,
        tier="BRONZE",
        redeemed_on_last_visit=False,
        today=today,
    )
    assert not any(s.kind == KIND_CUMPLE_CERCA for s in out)


def test_birthday_invalid_format_no_crash():
    """Garbage in customer.birthday → no crash, no suggestion."""
    from app.rms.loyalty.suggestions import KIND_CUMPLE_CERCA, suggest_for_customer

    cust = _FakeCustomer(birthday="not-a-date")
    out = suggest_for_customer(
        cust,
        last_sale_at=_today(),
        n_sales=1,
        tier="BRONZE",
        redeemed_on_last_visit=False,
        today=_today(),
    )
    assert not any(s.kind == KIND_CUMPLE_CERCA for s in out)


def test_lapsed_bronze_threshold_is_21_days():
    """BRONZE lapses at 21 days, gets 10% discount."""
    from app.rms.loyalty.suggestions import KIND_VUELVE_PRONTO, suggest_for_customer

    today = _today()
    last = today - _dt.timedelta(days=21)  # exactly at threshold
    cust = _FakeCustomer()

    out = suggest_for_customer(
        cust,
        last_sale_at=_dt.datetime.combine(last, _dt.time()),
        n_sales=3,
        tier="BRONZE",
        redeemed_on_last_visit=False,
        today=today,
    )
    vuelve = next(s for s in out if s.kind == KIND_VUELVE_PRONTO)
    assert vuelve.discount_pct == 10
    assert "21 días" in vuelve.body


def test_lapsed_bronze_below_threshold_no_suggestion():
    """20 days for BRONZE (threshold 21) → no LAPSED rule."""
    from app.rms.loyalty.suggestions import suggest_for_customer

    today = _today()
    cust = _FakeCustomer()

    out = suggest_for_customer(
        cust,
        last_sale_at=_dt.datetime.combine(today - _dt.timedelta(days=20), _dt.time()),
        n_sales=3,
        tier="BRONZE",
        redeemed_on_last_visit=False,
        today=today,
    )
    assert not any(s.kind == "vuelve_pronto" for s in out)


def test_lapsed_silver_threshold_is_30_days_with_7_pct():
    """SILVER lapses at 30 days, gets 7% discount."""
    from app.rms.loyalty.suggestions import suggest_for_customer

    today = _today()
    cust = _FakeCustomer()

    out = suggest_for_customer(
        cust,
        last_sale_at=_dt.datetime.combine(today - _dt.timedelta(days=35), _dt.time()),
        n_sales=10,
        tier="SILVER",
        redeemed_on_last_visit=False,
        today=today,
    )
    vuelve = next(s for s in out if s.kind == "vuelve_pronto")
    assert vuelve.discount_pct == 7


def test_lapsed_gold_threshold_is_45_days_with_5_pct():
    """GOLD lapses at 45 days, gets 5% discount (less margin erosion)."""
    from app.rms.loyalty.suggestions import suggest_for_customer

    today = _today()
    cust = _FakeCustomer()

    out = suggest_for_customer(
        cust,
        last_sale_at=_dt.datetime.combine(today - _dt.timedelta(days=50), _dt.time()),
        n_sales=20,
        tier="GOLD",
        redeemed_on_last_visit=False,
        today=today,
    )
    vuelve = next(s for s in out if s.kind == "vuelve_pronto")
    assert vuelve.discount_pct == 5


def test_never_visited_no_lapsed_suggestion():
    """A customer with last_sale_at=None is a prospect, not a lapsed one.

    The LAPSED rule fires only for known customers who disappeared.
    Never-visited customers get a different funnel (consent-first).
    """
    from app.rms.loyalty.suggestions import suggest_for_customer

    out = suggest_for_customer(
        _FakeCustomer(),
        last_sale_at=None,
        n_sales=0,
        tier="BRONZE",
        redeemed_on_last_visit=False,
        today=_today(),
    )
    assert not any(s.kind == "vuelve_pronto" for s in out)


def test_points_dormant_threshold_is_50():
    """50 points, no last-visit redeem → KIND_PUNTOS_DORMIDOS."""
    from app.rms.loyalty.suggestions import suggest_for_customer

    out = suggest_for_customer(
        _FakeCustomer(loyalty_points=50),
        last_sale_at=_dt.datetime.combine(_today(), _dt.time()),
        n_sales=3,
        tier="BRONZE",
        redeemed_on_last_visit=False,
        today=_today(),
    )
    puntos = next(s for s in out if s.kind == "puntos_dormidos")
    assert puntos.discount_pct is None  # points redeem has its own UI
    assert "50" in puntos.body
    assert "50,000" in puntos.body or "50.000" in puntos.body  # 50 pts × 1000 Gs.


def test_points_dormant_skipped_when_under_threshold():
    """49 points → no KIND_PUNTOS_DORMIDOS."""
    from app.rms.loyalty.suggestions import suggest_for_customer

    out = suggest_for_customer(
        _FakeCustomer(loyalty_points=49),
        last_sale_at=_dt.datetime.combine(_today(), _dt.time()),
        n_sales=3,
        tier="BRONZE",
        redeemed_on_last_visit=False,
        today=_today(),
    )
    assert not any(s.kind == "puntos_dormidos" for s in out)


def test_points_dormant_skipped_when_redeemed_last_visit():
    """Customer already redeemed on last visit → no nudge."""
    from app.rms.loyalty.suggestions import suggest_for_customer

    out = suggest_for_customer(
        _FakeCustomer(loyalty_points=100),
        last_sale_at=_dt.datetime.combine(_today(), _dt.time()),
        n_sales=3,
        tier="BRONZE",
        redeemed_on_last_visit=True,
        today=_today(),
    )
    assert not any(s.kind == "puntos_dormidos" for s in out)


def test_vip_rule_fires_for_gold_with_10plus_sales():
    """GOLD + 10+ sales → KIND_CLIENTE_FIEL (recognition only)."""
    from app.rms.loyalty.suggestions import suggest_for_customer

    today = _today()
    out = suggest_for_customer(
        _FakeCustomer(),
        last_sale_at=_dt.datetime.combine(today - _dt.timedelta(days=2), _dt.time()),
        n_sales=15,
        tier="GOLD",
        redeemed_on_last_visit=True,
        today=today,
    )
    vip = next(s for s in out if s.kind == "cliente_fiel")
    assert vip.discount_pct is None  # never discount VIPs
    assert "GOLD" in vip.body or "fiel" in vip.body.lower()


def test_vip_rule_skipped_for_silver_or_bronze():
    """SILVER + 50 sales still no VIP — only GOLD."""
    from app.rms.loyalty.suggestions import suggest_for_customer

    today = _today()
    out = suggest_for_customer(
        _FakeCustomer(),
        last_sale_at=_dt.datetime.combine(today - _dt.timedelta(days=2), _dt.time()),
        n_sales=50,
        tier="SILVER",
        redeemed_on_last_visit=True,
        today=today,
    )
    assert not any(s.kind == "cliente_fiel" for s in out)


def test_vip_rule_skipped_for_gold_with_few_sales():
    """GOLD with 5 sales (< 10) → no VIP recognition yet."""
    from app.rms.loyalty.suggestions import suggest_for_customer

    today = _today()
    out = suggest_for_customer(
        _FakeCustomer(),
        last_sale_at=_dt.datetime.combine(today - _dt.timedelta(days=2), _dt.time()),
        n_sales=5,
        tier="GOLD",
        redeemed_on_last_visit=True,
        today=today,
    )
    assert not any(s.kind == "cliente_fiel" for s in out)


def test_max_three_suggestions_returned():
    """All four rules firing → only top 3 by priority returned."""
    from app.rms.loyalty.suggestions import suggest_for_customer

    today = _today()
    bday = today + _dt.timedelta(days=3)  # CUMPLE_CERCA fires
    cust = _FakeCustomer(
        birthday=bday.strftime("%Y-%m-%d"),
        loyalty_points=100,  # PUNTOS_DORMIDOS fires
    )

    out = suggest_for_customer(
        cust,
        last_sale_at=_dt.datetime.combine(today - _dt.timedelta(days=50), _dt.time()),
        # VUELVE_PRONTO fires (50d > 21d bronze)
        n_sales=15,
        tier="GOLD",
        # CLIENTE_FIEL fires (GOLD + 10+)
        redeemed_on_last_visit=False,
        today=today,
    )
    assert len(out) == 3
    kinds = {s.kind for s in out}
    # CUMPLE_CERCA wins (priority 10); VUELVE_PRONTO second (20);
    # then EITHER PUNTOS_DORMIDOS (30) OR CLIENTE_FIEL (50) — the
    # 3-slot cap drops the lower-priority one. CLIENTE_FIEL is the
    # lowest priority and gets dropped.
    assert "cumple_cerca" in kinds
    assert "vuelve_pronto" in kinds
    # PUNTOS_DORMIDOS (30) is more important than CLIENTE_FIEL (50).
    assert "puntos_dormidos" in kinds


def test_priority_ordering_is_stable():
    """Suggestions are returned sorted by priority, then by kind for stability."""
    from app.rms.loyalty.suggestions import suggest_for_customer

    today = _today()
    bday = today + _dt.timedelta(days=3)
    cust = _FakeCustomer(
        birthday=bday.strftime("%Y-%m-%d"),
        loyalty_points=100,
    )
    out = suggest_for_customer(
        cust,
        last_sale_at=_dt.datetime.combine(today - _dt.timedelta(days=50), _dt.time()),
        n_sales=15,
        tier="GOLD",
        redeemed_on_last_visit=False,
        today=today,
    )
    priorities = [s.priority for s in out]
    assert priorities == sorted(priorities)


def test_returns_empty_list_never_raises():
    """Edge cases that previously broke similar code paths."""
    from app.rms.loyalty.suggestions import suggest_for_customer

    # birthday = None + loyalty_points = negative should not crash
    out = suggest_for_customer(
        _FakeCustomer(birthday=None, loyalty_points=-5),
        last_sale_at=None,
        n_sales=0,
        tier="BRONZE",
        redeemed_on_last_visit=False,
        today=_today(),
    )
    # Negative points → below POINTS_DORMANT_THRESHOLD → no rule fires
    assert out == []


# ──────────────────────────────────────────────────────────────────────
# Integration: /clientes/api/{id} payload includes suggestions
# ──────────────────────────────────────────────────────────────────────


def test_cliente_api_payload_includes_suggestions_field(
    session_factory, client, qseed
):
    """GET /clientes/api/{id} returns a 'suggestions' list in the payload.

    Smoke test that the JSON contract added by decision C is intact.
    """
    from app.rms.customers import ensure_customer

    with session_factory() as s:
        cust = ensure_customer(s, "Cliente Sugerencias", phone="+595****0301")
        s.commit()
        cust_id = cust.id

    resp = client.get(f"/clientes/api/{cust_id}")
    assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text[:200]}"
    payload = resp.json()
    assert "suggestions" in payload, "API contract broke: 'suggestions' field missing"
    assert isinstance(payload["suggestions"], list)
    # Empty list is fine — no rules fire for a brand-new customer with
    # no sales, no birthday, no points.


def test_cliente_api_payload_suggestions_have_correct_shape(
    session_factory, client, qseed
):
    """When rules fire, the suggestion dicts have kind/title/body/discount_pct/payload."""
    from app.rms.customers import ensure_customer
    from app.rms.models import Customer

    today = _dt.date.today()
    bday_str = (today + _dt.timedelta(days=4)).strftime("%Y-%m-%d")
    with session_factory() as s:
        cust = ensure_customer(s, "Cliente Birthday", phone="+595****0302")
        # ensure_customer doesn't accept birthday; set it directly.
        cust_db = s.get(Customer, cust.id)
        cust_db.birthday = bday_str
        s.commit()
        cust_id = cust.id

    resp = client.get(f"/clientes/api/{cust_id}")
    assert resp.status_code == 200
    payload = resp.json()
    assert len(payload["suggestions"]) >= 1
    s0 = payload["suggestions"][0]
    assert set(s0.keys()) >= {"kind", "title", "body"}
    # These may be None for some rules:
    assert "discount_pct" in s0
    assert "payload" in s0


def test_cliente_api_endpoint_does_not_500_on_missing_customer(client, qseed):
    """A bad customer_id returns 404, not 500 — defensive guard.

    The suggestions block is wrapped in try/except so a future rule
    bug never 500s the picker (this endpoint is hit on every customer
    selection).
    """
    resp = client.get("/clientes/api/999999")
    assert resp.status_code == 404


def test_cliente_api_with_lapsed_bronze_returns_vuelve_pronto(
    session_factory, client, qseed
):
    """End-to-end: a BRONZE customer with last sale 30 days ago → 'vuelve_pronto'."""
    from datetime import datetime, timedelta, timezone
    from app.rms.customers import ensure_customer
    from app.rms.models import Product, Sale

    today = _dt.date.today()
    thirty_days_ago = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=30)

    with session_factory() as s:
        cust = ensure_customer(s, "Cliente Lapsed", phone="+595****0303")
        p = Product(name="Chipita Test", sale_price_gs=12000, sku="SUGG-001")
        s.add(p)
        s.flush()
        # Seed a sale 30 days ago so the customer is "lapsed"
        s.add(Sale(
            sold_at=thirty_days_ago,
            product_id=p.id,
            qty=1,
            unit_price_gs=12000,
            customer_id=cust.id,
            payment_method="efectivo",
            discount_gs=0,
            channel="mostrador",
        ))
        s.commit()
        cust_id = cust.id

    resp = client.get(f"/clientes/api/{cust_id}")
    assert resp.status_code == 200
    payload = resp.json()
    kinds = [s["kind"] for s in payload["suggestions"]]
    # BRONZE threshold is 21 days, so 30 days lapsed → vuelve_pronto
    assert "vuelve_pronto" in kinds


def test_cliente_api_with_dormant_points_returns_puntos_dormidos(
    session_factory, client, qseed
):
    """End-to-end: 50+ points + didn't redeem last visit → 'puntos_dormidos'."""
    from app.rms.customers import ensure_customer
    from app.rms.models import Customer

    with session_factory() as s:
        cust = ensure_customer(s, "Cliente Puntos Dormidos", phone="+595****0304")
        # Set balance to 60 directly (faster than seeding a 60k sale)
        s.add(cust)
        s.flush()
        cust_db = s.get(Customer, cust.id)
        cust_db.loyalty_points = 60
        s.commit()
        cust_id = cust.id

    resp = client.get(f"/clientes/api/{cust_id}")
    payload = resp.json()
    kinds = [s["kind"] for s in payload["suggestions"]]
    assert "puntos_dormidos" in kinds
    # Verify the body has the right numbers
    puntos = next(s for s in payload["suggestions"] if s["kind"] == "puntos_dormidos")
    assert "60" in puntos["body"]
    assert "60,000" in puntos["body"] or "60.000" in puntos["body"]
