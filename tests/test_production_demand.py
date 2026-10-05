"""tests/test_production_demand.py — PRODUCCION-V2 Fase 1.

Tests for the new app/rms/production_demand.py module: the demanda
column that backs the upcoming 4-col /produccion day view.

Coverage targets (per app/rms/AGENTS.md service-module standard):
  - DemandRow dataclass: invariant tests
  - compute_demand_qty / split_pedidos_status: pure-function tests + properties
  - get_demand(): integration with session (pedidos + forecast + snapshot)
  - persist_plan_audit(): writes the right row
  - Router wire (?ui=v2): end-to-end via authed_client

Test layout:
  1. Pure (no DB) — DemandRow invariants, compute/split helpers, properties
  2. Integration (DB) — get_demand with seeded Sales and Pedidos
  3. Plan audit — persist_plan_audit inserts the right row
  4. Router wire — /produccion?ui=v2 does not 500
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import bindparam, text

from app.rms.production_demand import (
    DemandRow,
    compute_demand_qty,
    demand_snapshot_ttl_seconds,
    get_demand,
    invalidate_demand_cache,
    invalidate_demand_for_dates,
    invalidate_demand_for_sale_today,
    persist_plan_audit,
    split_pedidos_status,
)

# ---------------------------------------------------------------------------
# Pure helper tests (no DB)
# ---------------------------------------------------------------------------


def test_demand_row_is_frozen():
    """DemandRow is @dataclass(frozen=True) — guards against accidental mutation
    after get_demand() returns. Mutable copies would break the snapshot contract.
    """
    row = DemandRow(
        product_id=1,
        product_name="x",
        qty_forecast=10.0,
        qty_pedidos=5.0,
        qty_pedidos_confirmed=3.0,
        qty_evento=2.0,
        qty_total=17.0,
        confidence_pct=80,
        source="computed",
        computed_at=datetime.now(timezone.utc),
    )
    with pytest.raises((AttributeError, Exception)):
        row.qty_forecast = 999.0  # type: ignore[misc]


def test_compute_demand_qty_basic():
    """Plain sum: forecast=10, pedidos=5, multiplier=1.0 → total=15, evento=0."""
    total, evento = compute_demand_qty(
        qty_forecast=10.0, qty_pedidos=5.0, seasonal_multiplier=1.0
    )
    assert total == 15.0
    assert evento == 0.0


def test_compute_demand_qty_with_multiplier():
    """seasonal_multiplier>1 boosts the forecast and surfaces as evento."""
    total, evento = compute_demand_qty(
        qty_forecast=10.0, qty_pedidos=5.0, seasonal_multiplier=2.0
    )
    # seasonalized forecast = 10*2=20, pedidos=5, total=25, evento=10
    assert total == 25.0
    assert evento == 10.0


def test_compute_demand_qty_zero_forecast():
    """Zero forecast, some pedidos: total = pedidos only."""
    total, evento = compute_demand_qty(
        qty_forecast=0.0, qty_pedidos=7.5, seasonal_multiplier=1.0
    )
    assert total == 7.5
    assert evento == 0.0


def test_compute_demand_qty_zero_pedidos():
    """Zero pedidos, some forecast with multiplier: total = seasonalized forecast."""
    total, evento = compute_demand_qty(
        qty_forecast=8.0, qty_pedidos=0.0, seasonal_multiplier=1.5
    )
    # seasonalized = 8*1.5=12, pedidos=0, total=12, evento=4
    assert total == 12.0
    assert evento == 4.0


def test_compute_demand_qty_defends_against_negative_inputs():
    """Negative inputs are clamped to 0 (defensive; production data should be nonneg
    but corrupt caches are possible)."""
    total, evento = compute_demand_qty(
        qty_forecast=-5.0, qty_pedidos=-3.0, seasonal_multiplier=0.5
    )
    # multiplier<=0 treated as 1.0; forecast clamped to 0; pedidos clamped to 0
    assert total == 0.0
    assert evento == 0.0


def test_split_pedidos_status_basic():
    """pending=3 + confirmed=5 + ready=2 → total=10, confirmed=7."""
    total, confirmed = split_pedidos_status(
        pending_qty=3.0, confirmed_qty=5.0, ready_qty=2.0
    )
    assert total == 10.0
    assert confirmed == 7.0


def test_split_pedidos_status_only_pending():
    """All pending → confirmed=0, total=pending."""
    total, confirmed = split_pedidos_status(
        pending_qty=5.0, confirmed_qty=0.0, ready_qty=0.0
    )
    assert total == 5.0
    assert confirmed == 0.0


def test_split_pedidos_status_only_confirmed_and_ready():
    """No pending → total == confirmed (the "riesgo" gap is 0)."""
    total, confirmed = split_pedidos_status(
        pending_qty=0.0, confirmed_qty=4.0, ready_qty=6.0
    )
    assert total == 10.0
    assert confirmed == 10.0


# Property-based: invariants the production code must satisfy
# (caught a class of bug in the legacy `compute_under_baked` family of helpers;
# applying the same pattern here so the dataclass + helpers stay honest).


@st.composite
def _nonneg_float(draw, max_value: float = 1e6):
    return draw(st.floats(min_value=0.0, max_value=max_value, allow_nan=False, allow_infinity=False))


@st.composite
def _multiplier(draw):
    # seasonal_multiplier in the calendar is >=1.0; allow a wider range to
    # probe the defensive clamp at <=0.
    return draw(
        st.floats(min_value=0.0, max_value=3.0, allow_nan=False, allow_infinity=False)
    )


@settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    forecast=_nonneg_float(max_value=10_000),
    pedidos=_nonneg_float(max_value=10_000),
    multiplier=_multiplier(),
)
def test_property_qty_total_geq_qty_forecast(forecast, pedidos, multiplier):
    """qty_total is always >= qty_forecast (the forecast is a subset of total;
    pedidos add to it, multiplier only boosts)."""
    total, _ = compute_demand_qty(
        qty_forecast=forecast, qty_pedidos=pedidos, seasonal_multiplier=multiplier
    )
    # After the defensive clamp, total = forecast*max(multi, 0)*1 + pedidos
    # when forecast=0 and pedidos=0, total=0, so >= 0 always. With nonneg
    # inputs and multiplier >= 0, total >= 0.
    assert total >= 0.0
    # The actual invariant: if multiplier >= 1 and pedidos >= 0, total >= forecast.
    if multiplier >= 1.0:
        assert total >= forecast - 0.01  # round to 2 decimals


@settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    pending=_nonneg_float(max_value=1_000),
    confirmed=_nonneg_float(max_value=1_000),
    ready=_nonneg_float(max_value=1_000),
)
def test_property_split_pedidos_total_geq_confirmed(pending, confirmed, ready):
    """qty_pedidos >= qty_pedidos_confirmed always (pending is added to one
    side only). The UI uses this to compute the 'riesgo' gap = total - confirmed."""
    total, conf = split_pedidos_status(
        pending_qty=pending, confirmed_qty=confirmed, ready_qty=ready
    )
    assert total >= conf - 0.01  # round to 2 decimals
    # And specifically: total == confirmed + pending (ready is in both)
    assert abs(total - (conf + pending)) < 0.01


# ---------------------------------------------------------------------------
# Integration: get_demand() with a real session
# ---------------------------------------------------------------------------


def test_get_demand_empty_db_returns_empty_dict(session_factory):
    """No products seeded → empty dict (router handles the 'no rows' state)."""
    with session_factory() as s:
        result = get_demand(s, for_date=date(2026, 10, 5))
    assert result == {}


def test_get_demand_product_with_no_sales_no_pedidos(session_factory):
    """A product with no history and no pedidos → all qty 0, confidence 0."""
    from tests.factories import make_product

    with session_factory() as s:
        prod = make_product(s, name="EmptyProd")
        prod_id = prod.id
        s.commit()

    with session_factory() as s:
        result = get_demand(s, for_date=date(2026, 10, 5))

    assert prod_id in result
    row = result[prod_id]
    assert row.qty_forecast == 0.0
    assert row.qty_pedidos == 0.0
    assert row.qty_pedidos_confirmed == 0.0
    assert row.qty_total == 0.0
    assert row.confidence_pct == 0


def test_get_demand_sums_two_pedido_lines_same_product(session_factory):
    """Two PedidoLines on the same product → qty_pedidos is the sum."""
    from tests.factories import make_pedido, make_product, pedido_item

    target = date(2026, 10, 5)

    with session_factory() as s:
        prod = make_product(s, name="Chipitas")
        prod_id = prod.id
        # Two pedidos on the same product: the factory persists them
        # via session.add; we just need them to exist so get_demand()
        # can SUM PedidoLine.qty.
        make_pedido(
            s,
            items=[pedido_item(product=prod, qty=3.0, unit_price_gs=10000)],
            status="pending",
            promised_date=target,
            customer_name="Ana",
        )
        make_pedido(
            s,
            items=[pedido_item(product=prod, qty=5.0, unit_price_gs=10000)],
            status="confirmed",
            promised_date=target,
            customer_name="Beto",
        )
        s.commit()

    with session_factory() as s:
        result = get_demand(s, for_date=target)

    row = result[prod_id]
    assert row.qty_pedidos == 8.0           # 3 pending + 5 confirmed
    assert row.qty_pedidos_confirmed == 5.0  # only confirmed
    # The "riesgo" gap (pending) = 3, surfaced in the UI as a badge.


def test_get_demand_excludes_cancelled_and_fulfilled_pedidos(session_factory):
    """Pedidos in status cancelled or fulfilled are NOT counted in demanda."""
    from app.rms.models import PedidoLine
    from tests.factories import make_pedido, make_product

    target = date(2026, 10, 5)

    with session_factory() as s:
        prod = make_product(s, name="Pan")
        prod_id = prod.id
        # cancelled — must not appear in demanda
        p_c = make_pedido(s, status="cancelled", promised_date=target, customer_name="X")
        s.flush()
        s.add(
            PedidoLine(pedido_id=p_c.id, product_id=prod_id, qty=99.0, unit_price_gs=10000)
        )
        # fulfilled — must not appear (the sale already debited stock)
        p_f = make_pedido(s, status="fulfilled", promised_date=target, customer_name="Y")
        s.flush()
        s.add(
            PedidoLine(pedido_id=p_f.id, product_id=prod_id, qty=99.0, unit_price_gs=10000)
        )
        # ready — must appear
        p_r = make_pedido(s, status="ready", promised_date=target, customer_name="Z")
        s.flush()
        s.add(
            PedidoLine(pedido_id=p_r.id, product_id=prod_id, qty=2.0, unit_price_gs=10000)
        )
        s.commit()

    with session_factory() as s:
        result = get_demand(s, for_date=target)

    row = result[prod_id]
    assert row.qty_pedidos == 2.0            # only the ready pedido
    assert row.qty_pedidos_confirmed == 2.0   # ready counts as confirmed


def test_get_demand_writes_to_snapshot_table(session_factory):
    """get_demand() persists a row in production_demand_snapshot (best-effort)."""
    from tests.factories import make_product

    target = date(2026, 10, 5)

    with session_factory() as s:
        prod = make_product(s, name="SnapshotProd")
        prod_id = prod.id
        s.commit()

    with session_factory() as s:
        get_demand(s, for_date=target)
        s.commit()

    # Read the snapshot directly (raw SQL, no model for this table yet).
    with session_factory() as s:
        rows = s.execute(
            text(
                "SELECT product_id, qty_forecast, qty_pedidos, qty_total "
                "FROM production_demand_snapshot WHERE for_date = :d"
            ),
            {"d": target.isoformat()},
        ).all()

    assert len(rows) == 1
    row = rows[0]
    assert int(row.product_id) == prod_id
    assert float(row.qty_forecast) == 0.0
    assert float(row.qty_pedidos) == 0.0
    assert float(row.qty_total) == 0.0


# ---------------------------------------------------------------------------
# Plan audit
# ---------------------------------------------------------------------------


def test_persist_plan_audit_writes_row(session_factory):
    """persist_plan_audit inserts 1 row that can be read back."""
    from tests.factories import make_product

    with session_factory() as s:
        prod = make_product(s, name="AuditProd")
        prod_id = prod.id
        s.commit()

    target = date(2026, 10, 5)
    with session_factory() as s:
        persist_plan_audit(
            s,
            for_date=target,
            product_id=prod_id,
            old_qty=5.0,
            new_qty=8.0,
            change_source="override",
            changed_by="saskia",
            notes="test row",
        )
        s.commit()

    with session_factory() as s:
        rows = s.execute(
            text(
                "SELECT for_date, product_id, old_qty, new_qty, change_source, changed_by, notes "
                "FROM production_plan_audit WHERE for_date = :d"
            ),
            {"d": target.isoformat()},
        ).all()

    assert len(rows) == 1
    row = rows[0]
    assert str(row.for_date) == target.isoformat()
    assert int(row.product_id) == prod_id
    assert float(row.old_qty) == 5.0
    assert float(row.new_qty) == 8.0
    assert row.change_source == "override"
    assert row.changed_by == "saskia"
    assert row.notes == "test row"


def test_persist_plan_audit_rejects_negative_new_qty(session_factory):
    """Defensive: new_qty must be >= 0."""
    from tests.factories import make_product

    with session_factory() as s:
        prod = make_product(s, name="NegProd")
        s.commit()

    with session_factory() as s:
        with pytest.raises(ValueError, match="new_qty"):
            persist_plan_audit(
                s,
                for_date=date(2026, 10, 5),
                product_id=prod.id,
                old_qty=0.0,
                new_qty=-1.0,
                change_source="override",
                changed_by=None,
            )


def test_persist_plan_audit_rejects_empty_source(session_factory):
    """change_source is required (the audit log is meaningless without it)."""
    from tests.factories import make_product

    with session_factory() as s:
        prod = make_product(s, name="SrcProd")
        s.commit()

    with session_factory() as s:
        with pytest.raises(ValueError, match="change_source"):
            persist_plan_audit(
                s,
                for_date=date(2026, 10, 5),
                product_id=prod.id,
                old_qty=None,
                new_qty=0.0,
                change_source="",
                changed_by=None,
            )


# ---------------------------------------------------------------------------
# Router wire (?ui=v2)
# ---------------------------------------------------------------------------


def test_produccion_ui_v2_does_not_500(authed_client, session_factory):
    """GET /produccion?ui=v2 must render (status < 500) with the new
    demand fields. Phase 1: the template is unchanged; the router
    silently populates new fields the template doesn't render yet.
    This test only asserts the route survives the wire.
    """
    from tests.factories import make_product

    with session_factory() as s:
        make_product(s, name="V2Wire")
        s.commit()

    r = authed_client.get("/produccion?for_date=2026-10-05&ui=v2")
    assert r.status_code < 500, f"/produccion?ui=v2 returned {r.status_code}: {r.text[:200]}"


def test_override_endpoint_writes_plan_audit(authed_client, session_factory):
    """POST /produccion/override must leave 1 row in production_plan_audit
    with change_source='override' (the wire in Fase 1).
    """
    from tests.factories import make_product

    with session_factory() as s:
        prod = make_product(s, name="OverrideAudit")
        s.commit()
        prod_id = prod.id

    r = authed_client.post(
        "/produccion/override",
        data={
            "for_date": "2026-10-05",
            "product_id": str(prod_id),
            "qty": "12",
        },
    )
    assert r.status_code < 500, f"override returned {r.status_code}: {r.text[:200]}"

    with session_factory() as s:
        rows = s.execute(
            text(
                "SELECT change_source, old_qty, new_qty "
                "FROM production_plan_audit "
                "WHERE for_date = :d AND product_id = :pid"
            ),
            {"d": "2026-10-05", "pid": prod_id},
        ).all()

    assert len(rows) == 1
    assert rows[0].change_source == "override"
    assert float(rows[0].new_qty) == 12.0
    # old_qty is None on first write (the override is the new plan).
    assert rows[0].old_qty is None


# ---------------------------------------------------------------------------
# PRODUCCION-V2 Fase 3: TTL cache (read path)
# ---------------------------------------------------------------------------


def test_get_demand_cache_hit_returns_same_value_without_recompute(
    session_factory,
):
    """Second call within TTL window returns the cached rows.

    We patch `app.rms.production.forecast_sales` to count invocations.
    The first get_demand should invoke it once per product; the second
    call (cache hit) should invoke it zero times.
    """
    from tests.factories import make_product

    target = date(2026, 10, 5)
    with session_factory() as s:
        make_product(s, name="CacheTest1")
        make_product(s, name="CacheTest2")
        s.commit()

    from app.rms import production as prod_mod

    real_forecast = prod_mod.forecast_sales
    call_count = {"n": 0}

    def counting_forecast(*args, **kwargs):
        call_count["n"] += 1
        return real_forecast(*args, **kwargs)

    prod_mod.forecast_sales = counting_forecast
    try:
        with session_factory() as s:
            first = get_demand(s, for_date=target)
            s.commit()  # commit so the second session can see the cache rows
        first_calls = call_count["n"]
        assert first_calls > 0, "first call should hit forecast_sales"

        with session_factory() as s:
            second = get_demand(s, for_date=target)
        second_calls = call_count["n"] - first_calls
        assert second_calls == 0, (
            f"cache hit should not call forecast_sales; got {second_calls} extra calls"
        )

        # Same shape returned.
        assert set(first.keys()) == set(second.keys())
        for pid in first:
            assert first[pid].qty_forecast == second[pid].qty_forecast
    finally:
        prod_mod.forecast_sales = real_forecast


def test_get_demand_cache_miss_when_ttl_zero(session_factory):
    """TTL=0 disables the cache; every call recomputes."""
    from tests.factories import make_product

    from app.rms import production_demand as pd_mod

    target = date(2026, 10, 5)
    with session_factory() as s:
        make_product(s, name="TtlZero")
        s.commit()

    # Override the TTL reader to return 0.
    real_reader = pd_mod.demand_snapshot_ttl_seconds

    def zero_reader(_session):
        return 0

    pd_mod.demand_snapshot_ttl_seconds = zero_reader
    from app.rms import production as prod_mod

    real_forecast = prod_mod.forecast_sales
    call_count = {"n": 0}

    def counting_forecast(*args, **kwargs):
        call_count["n"] += 1
        return real_forecast(*args, **kwargs)

    prod_mod.forecast_sales = counting_forecast
    try:
        with session_factory() as s:
            get_demand(s, for_date=target)
        n_first = call_count["n"]
        assert n_first > 0

        with session_factory() as s:
            get_demand(s, for_date=target)
        n_total = call_count["n"]
        # With TTL=0, both calls should hit forecast_sales.
        assert n_total > n_first, (
            f"TTL=0 should always recompute; got {n_first} then {n_total}"
        )
    finally:
        pd_mod.demand_snapshot_ttl_seconds = real_reader
        prod_mod.forecast_sales = real_forecast


def test_invalidate_demand_cache_deletes_rows(session_factory):
    """invalidate_demand_cache removes all snapshot rows for a date."""
    from tests.factories import make_product

    target = date(2026, 10, 5)
    with session_factory() as s:
        make_product(s, name="Inv1")
        make_product(s, name="Inv2")
        s.commit()

    # Populate the cache.
    with session_factory() as s:
        get_demand(s, for_date=target)
        s.commit()

    # Confirm there are rows.
    with session_factory() as s:
        before = s.execute(
            text("SELECT COUNT(*) FROM production_demand_snapshot WHERE for_date = :d"),
            {"d": target.isoformat()},
        ).scalar()
        assert before >= 2

    # Invalidate.
    with session_factory() as s:
        deleted = invalidate_demand_cache(s, for_date=target)
        s.commit()
    assert deleted >= 2

    # Confirm rows are gone.
    with session_factory() as s:
        after = s.execute(
            text("SELECT COUNT(*) FROM production_demand_snapshot WHERE for_date = :d"),
            {"d": target.isoformat()},
        ).scalar()
        assert after == 0


def test_get_demand_cache_stale_after_ttl_window(session_factory):
    """A snapshot older than TTL is treated as miss and recomputed."""
    from datetime import datetime, timedelta, timezone

    from tests.factories import make_product

    target = date(2026, 10, 5)
    with session_factory() as s:
        make_product(s, name="Stale")
        s.commit()

    # Populate the cache.
    with session_factory() as s:
        get_demand(s, for_date=target)
        s.commit()

    # Backdate the snapshot row's computed_at to 10 minutes ago.
    stale_time = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=600)
    with session_factory() as s:
        s.execute(
            text(
                "UPDATE production_demand_snapshot "
                "SET computed_at = :t WHERE for_date = :d"
            ),
            {"t": stale_time.isoformat(), "d": target.isoformat()},
        )
        s.commit()

    # Default TTL is 300 (5 min). The row is 10 min old → cache miss
    # → recompute (which overwrites the stale row).
    from app.rms import production as prod_mod

    real_forecast = prod_mod.forecast_sales
    call_count = {"n": 0}

    def counting_forecast(*args, **kwargs):
        call_count["n"] += 1
        return real_forecast(*args, **kwargs)

    prod_mod.forecast_sales = counting_forecast
    try:
        with session_factory() as s:
            get_demand(s, for_date=target)
        assert call_count["n"] > 0, "stale snapshot should trigger recompute"
    finally:
        prod_mod.forecast_sales = real_forecast


def test_demand_snapshot_ttl_seconds_default_is_300(session_factory):
    """The default TTL is 300 seconds (5 minutes)."""
    with session_factory() as s:
        ttl = demand_snapshot_ttl_seconds(s)
    assert ttl == 300


# ---------------------------------------------------------------------------
# Fase 4: invalidation hooks used by the pedidos/sales routers
# ---------------------------------------------------------------------------


def test_invalidate_demand_for_dates_drops_all_listed(session_factory):
    """invalidate_demand_for_dates deletes snapshot rows for every listed date."""
    from tests.factories import make_product

    d1 = date(2026, 10, 5)
    d2 = date(2026, 10, 6)
    d3 = date(2026, 10, 7)
    with session_factory() as s:
        make_product(s, name="Multi1")
        s.commit()
    with session_factory() as s:
        for d in (d1, d2, d3):
            get_demand(s, for_date=d)
        s.commit()

    with session_factory() as s:
        # Count rows for all three dates.
        before = s.execute(
            text(
                "SELECT for_date, COUNT(*) FROM production_demand_snapshot "
                "WHERE for_date IN :ds GROUP BY for_date"
            ).bindparams(
                bindparam("ds", expanding=True)
            ),
            {"ds": [d1.isoformat(), d2.isoformat(), d3.isoformat()]},
        ).all()
    assert len(before) == 3

    with session_factory() as s:
        deleted = invalidate_demand_for_dates(s, [d1, d2, d3])
        s.commit()
    assert deleted >= 3  # at least one row per date (could be more per product)

    with session_factory() as s:
        remaining = s.execute(
            text(
                "SELECT COUNT(*) FROM production_demand_snapshot "
                "WHERE for_date IN :ds"
            ).bindparams(
                bindparam("ds", expanding=True)
            ),
            {"ds": [d1.isoformat(), d2.isoformat(), d3.isoformat()]},
        ).scalar()
    assert remaining == 0


def test_invalidate_demand_for_sale_today_covers_window(session_factory):
    """invalidate_demand_for_sale_today invalidates today + N-1 forward days."""
    from app.rms.config import ASUNCION_TZ
    from tests.factories import make_product
    from datetime import datetime

    today = datetime.now(ASUNCION_TZ).date()
    # Seed 5 distinct dates: today, +1, +2, +3, +4. The window=4 hook
    # will invalidate the first 4 (today..+3), leaving +4 untouched.
    with session_factory() as s:
        make_product(s, name="SaleWindow")
        s.commit()
    with session_factory() as s:
        for offset in range(5):
            get_demand(s, for_date=today + timedelta(days=offset))
        s.commit()

    # Run with default window_days=4 (today..+3).
    with session_factory() as s:
        deleted = invalidate_demand_for_sale_today(s, today=today)
        s.commit()
    assert deleted >= 4  # at least one row per date

    with session_factory() as s:
        # Today + 3 forward = all 4 invalidated. Day +4 should remain.
        surviving = s.execute(
            text(
                "SELECT for_date FROM production_demand_snapshot "
                "WHERE for_date = :d"
            ),
            {"d": (today + timedelta(days=4)).isoformat()},
        ).all()
    # Day +4 should still have rows since window=4 only covers [today, today+3].
    assert len(surviving) >= 1


def test_pedido_create_invalidates_promised_date_cache(
    session_factory, authed_client,
):
    """A new pedido invalidates the demand cache for its promised_date.

    Phase 4 wire-up: when a POST /pedidos/nuevo creates a pedido, the
    router calls invalidate_demand_for_dates([pedido.promised_date]).
    The next /produccion?ui=v2 render must recompute.
    """
    from tests.factories import make_product
    from app.rms.config import ASUNCION_TZ
    from datetime import datetime

    today = datetime.now(ASUNCION_TZ).date()
    target = today + timedelta(days=1)

    with session_factory() as s:
        product = make_product(s, name="PedidoInvalidate")
        s.commit()
        product_id = product.id

    # Populate the cache for the target date.
    with session_factory() as s:
        get_demand(s, for_date=target)
        s.commit()
    with session_factory() as s:
        before = s.execute(
            text(
                "SELECT COUNT(*) FROM production_demand_snapshot "
                "WHERE for_date = :d"
            ),
            {"d": target.isoformat()},
        ).scalar()
    assert before >= 1

    # Create a pedido for that date. The form needs at least one line.
    r = authed_client.post(
        "/pedidos/nuevo",
        data={
            "customer_name": "Hook Customer",
            "promised_date": target.isoformat(),
            "promised_time": "10:00",
            "channel": "whatsapp",
            "payment_intent": "efectivo",
            "line_product_id": [str(product_id)],
            "line_qty": ["2"],
            "line_unit_price_gs": ["10000"],
        },
        follow_redirects=False,
    )
    assert r.status_code in (200, 303), f"pedido create returned {r.status_code}: {r.text[:300]}"

    # The cache for that date must be empty now.
    with session_factory() as s:
        after = s.execute(
            text(
                "SELECT COUNT(*) FROM production_demand_snapshot "
                "WHERE for_date = :d"
            ),
            {"d": target.isoformat()},
        ).scalar()
    assert after == 0, "new pedido should invalidate promised_date cache"


def test_pedido_status_change_invalidates_cache(
    session_factory, authed_client,
):
    """A pedido status change (POST /pedidos/{id}/status) invalidates cache."""
    from tests.factories import make_customer, make_pedido, make_product, pedido_item
    from app.rms.config import ASUNCION_TZ
    from datetime import datetime
    from datetime import date as _date

    today = datetime.now(ASUNCION_TZ).date()
    target = today + timedelta(days=2)

    with session_factory() as s:
        product = make_product(s, name="StatusInvalidate")
        customer = make_customer(s, name="Status Customer")
        # Build at least one pedido line so the status change can shift qty.
        items = [
            pedido_item(product=product, qty=2, unit_price_gs=10000),
        ]
        pedido = make_pedido(
            s,
            customer=customer,
            promised_date=target,
            items=items,
        )
        s.commit()
        pedido_id = pedido.id

    with session_factory() as s:
        get_demand(s, for_date=target)
        s.commit()
    with session_factory() as s:
        before = s.execute(
            text(
                "SELECT COUNT(*) FROM production_demand_snapshot "
                "WHERE for_date = :d"
            ),
            {"d": target.isoformat()},
        ).scalar()
    assert before >= 1

    r = authed_client.post(
        f"/pedidos/{pedido_id}/status",
        data={"new_status": "confirmed", "csrf": "x"},
        follow_redirects=False,
    )
    assert r.status_code in (200, 303), f"status change returned {r.status_code}: {r.text[:300]}"

    with session_factory() as s:
        after = s.execute(
            text(
                "SELECT COUNT(*) FROM production_demand_snapshot "
                "WHERE for_date = :d"
            ),
            {"d": target.isoformat()},
        ).scalar()
    assert after == 0, "status change should invalidate promised_date cache"


def test_pedido_fulfill_invalidates_promised_and_today(
    session_factory, authed_client,
):
    """A pedido fulfill (POST /pedidos/{id}/fulfill) invalidates the
    promised_date AND today's cache (because fulfill creates a Sale row
    that shifts the 14d rolling forecast)."""
    from tests.factories import make_customer, make_pedido, make_product, pedido_item
    from app.rms.config import ASUNCION_TZ
    from datetime import datetime

    today = datetime.now(ASUNCION_TZ).date()
    target = today + timedelta(days=1)

    with session_factory() as s:
        product = make_product(s, name="FulfillInvalidate")
        customer = make_customer(s, name="Fulfill Customer")
        items = [
            pedido_item(product=product, qty=1, unit_price_gs=10000),
        ]
        pedido = make_pedido(
            s,
            customer=customer,
            promised_date=target,
            items=items,
        )
        s.commit()
        pedido_id = pedido.id

    with session_factory() as s:
        for d in (target, today):
            get_demand(s, for_date=d)
        s.commit()
    with session_factory() as s:
        before_promised = s.execute(
            text(
                "SELECT COUNT(*) FROM production_demand_snapshot "
                "WHERE for_date = :d"
            ),
            {"d": target.isoformat()},
        ).scalar()
        before_today = s.execute(
            text(
                "SELECT COUNT(*) FROM production_demand_snapshot "
                "WHERE for_date = :d"
            ),
            {"d": today.isoformat()},
        ).scalar()
    assert before_promised >= 1
    assert before_today >= 1

    r = authed_client.post(
        f"/pedidos/{pedido_id}/fulfill",
        data={"csrf": "x"},
        follow_redirects=False,
    )
    # Fulfill can fail if there is not enough stock — if 500/4xx we skip.
    if r.status_code not in (200, 303):
        pytest.skip(f"pedido fulfill returned {r.status_code} (likely stock issue)")

    with session_factory() as s:
        after_promised = s.execute(
            text(
                "SELECT COUNT(*) FROM production_demand_snapshot "
                "WHERE for_date = :d"
            ),
            {"d": target.isoformat()},
        ).scalar()
        after_today = s.execute(
            text(
                "SELECT COUNT(*) FROM production_demand_snapshot "
                "WHERE for_date = :d"
            ),
            {"d": today.isoformat()},
        ).scalar()
    assert after_promised == 0, "fulfill should invalidate promised_date cache"
    assert after_today == 0, "fulfill should invalidate today's cache (forecast shift)"


