"""app/rms/production_demand.py — Demanda descompuesta para /produccion.

PRODUCCION-V2 Fase 1 (2026-10-05): the /produccion day view is being
split into 4 columns (demanda | plan | real | pedidos). This module
owns the **demanda** column: the system-side prediction of how much
the operator needs to bake for a given date, decomposed into its parts.

What counts as demanda (resolved decision 2026-10-05):
  qty_forecast  = production.forecast_sales() (existing; 14d avg or
                  12w DOW when use_dow_forecast=True)
  qty_pedidos   = SUM(PedidoLine.qty) WHERE Pedido.status IN
                  ('pending', 'confirmed', 'ready')
                  AND Pedido.promised_date = for_date
  qty_pedidos_confirmed = same query but status IN ('confirmed', 'ready')
                  (the "riesgo" subset = qty_pedidos - qty_pedidos_confirmed
                  = pedidos que aún no están confirmados)
  qty_evento    = (seasonal_multiplier - 1.0) * qty_forecast
                  (the "extra" forecast from calendar events like Día
                  de la Madre; already embedded in qty_forecast when
                  the multiplier is applied, so we surface it
                  separately for transparency)
  qty_total     = qty_forecast * seasonal_multiplier + qty_pedidos
                  (the number the cook actually needs to cover)

What this module is NOT:
  - It does NOT write to production_plan_override (the plan).
  - It does NOT write to production_completion (the real).
  - It does NOT mutate the plan_production() contract — that helper
    in production.py stays as-is. This is a parallel read path
    that the router will use to enrich the plan_rows_view dict.

Why a snapshot table:
  The router fires get_demand() on every /produccion render. The
  pedidos query joins pedido + pedido_line (cheap but not free).
  A snapshot table gives us a 1-row-per-(date, product) PK lookup
  when the demand is "fresh" (computed_at < ttl). For Fase 1 we
  always recompute (the table is just a write target); Fase 3
  adds the TTL gate and the read path becomes the hot path.

Public API:
  DemandRow                          — frozen dataclass
  get_demand(session, *, for_date)   — main entry point (TTL-gated)
  persist_plan_audit(session, ...)   — append-only audit log writer
  compute_demand_qty(...)            — pure helper, no DB
  split_pedidos_status(...)          — pure helper, no DB
  invalidate_demand_cache(session, *)  — drop a date's snapshot rows
  demand_snapshot_ttl_seconds()      — read the active TTL (settings)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.rms.models import Pedido, PedidoLine, Product

# ---------------------------------------------------------------------------
# Pure helpers (no DB, no I/O — unit-testable in milliseconds)
# ---------------------------------------------------------------------------


def compute_demand_qty(
    *,
    qty_forecast: float,
    qty_pedidos: float,
    seasonal_multiplier: float,
) -> tuple[float, float]:
    """Return (qty_total, qty_evento) from raw components.

    qty_evento is the (multiplier - 1.0) * qty_forecast — the slice of
    the forecast that came from a calendar event, surfaced separately
    for UI transparency.

    qty_total is the seasonalized forecast + the pedidos (pedidos are
    NOT seasonalized — a confirmed pedido for Día de la Madre is still
    the same pedido whether the calendar has the event or not).

    Edge cases:
      - multiplier <= 0 → treat as 1.0 (defensive; calendar returns >=1.0)
      - negative qty_forecast → treat as 0.0 (defensive; forecast_sales
        returns >= 0.0 by construction but a corrupt cache could differ)
      - negative qty_pedidos → treat as 0.0 (defensive; SUM is nonneg
        for valid qty, but a corrupt row could be negative)
    """
    if seasonal_multiplier <= 0:
        seasonal_multiplier = 1.0
    forecast = max(0.0, float(qty_forecast))
    pedidos = max(0.0, float(qty_pedidos))
    seasonalized = forecast * seasonal_multiplier
    evento = forecast * (seasonal_multiplier - 1.0)
    total = seasonalized + pedidos
    return round(total, 2), round(evento, 2)


def split_pedidos_status(
    *,
    pending_qty: float,
    confirmed_qty: float,
    ready_qty: float,
) -> tuple[float, float]:
    """Return (qty_pedidos, qty_pedidos_confirmed).

    qty_pedidos          = pending + confirmed + ready
    qty_pedidos_confirmed = confirmed + ready

    Property: qty_pedidos >= qty_pedidos_confirmed (always — pending
    is added to one side only).
    """
    p = max(0.0, float(pending_qty))
    c = max(0.0, float(confirmed_qty))
    r = max(0.0, float(ready_qty))
    return round(p + c + r, 2), round(c + r, 2)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DemandRow:
    """One product's demand composition for a given for_date.

    All qty fields are in the product's native unit (portions for
    things sold by portion, kg for things sold by weight, etc.).
    The UI does its own display rounding.
    """

    product_id: int
    product_name: str
    qty_forecast: float          # raw forecast (before seasonal multiplier)
    qty_pedidos: float           # pending + confirmed + ready
    qty_pedidos_confirmed: float # confirmed + ready (subset of the above)
    qty_evento: float            # (multiplier - 1.0) * qty_forecast
    qty_total: float             # seasonalized forecast + pedidos
    confidence_pct: int          # 0-100 from production._forecast_confidence
    source: str                  # 'computed' | 'closed' | 'manual'
    computed_at: datetime


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_demand(
    session: Session,
    *,
    for_date: date,
    use_dow_forecast: bool = False,
) -> dict[int, DemandRow]:
    """Return {product_id: DemandRow} for for_date.

    For Fase 1: always recomputes from the live queries and writes the
    snapshot. The 5-min TTL cache is a Fase 3 concern.

    Args:
        session: SQLAlchemy session.
        for_date: the production date (Asunción-local calendar date).
        use_dow_forecast: when True, pass target_weekday=for_date.weekday()
            to forecast_sales() so the forecast is restricted to historical
            DOW rows (B2 2026-10-01 logic). /manana passes True; /produccion
            day view passes False to preserve the legacy flat 14d avg.

    Returns:
        Dict keyed by product_id. May be empty if there are no products
        (e.g. fresh DB). The router iterates this and merges with
        plan_production() rows.
    """
    # PRODUCCION-V2 Fase 3: TTL cache. Read the configured TTL (0 disables).
    ttl = demand_snapshot_ttl_seconds(session)
    if ttl > 0:
        cached = _read_snapshot(session, for_date=for_date, ttl_seconds=ttl)
        if cached is not None:
            return cached  # cache hit — no N+1 forecast queries

    from app.rms.production import _forecast_confidence, _forecast_sample_stats, forecast_sales
    from app.rms.workflow import demand_multiplier

    multiplier = float(demand_multiplier(for_date))
    now_utc = datetime.now(timezone.utc)

    # 1) Pedidos qty grouped by product for this date.
    # status IN ('pending', 'confirmed', 'ready') for qty_pedidos.
    # status IN ('confirmed', 'ready') for qty_pedidos_confirmed.
    # pending_qty = qty_pedidos - qty_pedidos_confirmed (derived).
    pedido_rows = session.execute(
        select(
            PedidoLine.product_id,
            Pedido.status,
            func.coalesce(func.sum(PedidoLine.qty), 0.0).label("qty"),
        )
        .join(Pedido, PedidoLine.pedido_id == Pedido.id)
        .where(Pedido.promised_date == for_date)
        .where(Pedido.status.in_(("pending", "confirmed", "ready")))
        .where(PedidoLine.qty > 0)
        .group_by(PedidoLine.product_id, Pedido.status)
    ).all()

    # Aggregate into per-product dict: product_id -> {pending, confirmed, ready}
    pedidos_by_pid: dict[int, dict[str, float]] = {}
    for pid, status, qty in pedido_rows:
        bucket = pedidos_by_pid.setdefault(int(pid), {"pending": 0.0, "confirmed": 0.0, "ready": 0.0})
        if status in bucket:
            bucket[status] = bucket.get(status, 0.0) + float(qty)

    # 2) Products with sales history (so the forecast is meaningful).
    # The router already iterates Product separately, so we don't return
    # products with no sales + no pedidos here — the router merges us
    # into its plan_rows_view and the existing logic decides whether
    # to render an ad-hoc row.
    products = list(session.execute(select(Product).order_by(Product.id)).scalars())

    rows: dict[int, DemandRow] = {}
    for prod in products:
        pid = int(prod.id)

        # Pedidos for this product on this date (default 0).
        pedido_bucket = pedidos_by_pid.get(pid, {"pending": 0.0, "confirmed": 0.0, "ready": 0.0})
        qty_pedidos, qty_pedidos_confirmed = split_pedidos_status(
            pending_qty=pedido_bucket["pending"],
            confirmed_qty=pedido_bucket["confirmed"],
            ready_qty=pedido_bucket["ready"],
        )

        # Forecast: call production.forecast_sales() with the same
        # signature the day view uses (14d flat avg) or the /manana
        # signature (84d DOW). Both are already unit-tested in
        # tests/test_forecast_basic.py and tests/test_dow_forecast.py.
        target_weekday = for_date.weekday() if use_dow_forecast else None
        qty_forecast = float(
            forecast_sales(
                session,
                product_id=pid,
                days_history=84 if use_dow_forecast else 14,
                target_weekday=target_weekday,
            )
        )

        qty_total, qty_evento = compute_demand_qty(
            qty_forecast=qty_forecast,
            qty_pedidos=qty_pedidos,
            seasonal_multiplier=multiplier,
        )

        # Confidence uses the same data-window the forecast used so the
        # confidence number on the demand row matches the underlying
        # forecast's confidence.
        sample_window = 84 if use_dow_forecast else 14
        sale_count, days_span = _forecast_sample_stats(
            session, product_id=pid, days_history=sample_window
        )
        confidence = _forecast_confidence(sale_count, days_span)

        rows[pid] = DemandRow(
            product_id=pid,
            product_name=str(prod.name or ""),
            qty_forecast=round(qty_forecast, 2),
            qty_pedidos=qty_pedidos,
            qty_pedidos_confirmed=qty_pedidos_confirmed,
            qty_evento=qty_evento,
            qty_total=qty_total,
            confidence_pct=confidence,
            source="computed",
            computed_at=now_utc,
        )

    # 3) Persist snapshot (best-effort; failures don't break the read).
    # Fase 3: only writes when the cache is enabled (ttl > 0). When
    # caching is disabled, every read recomputes from scratch and
    # there is no point growing the table.
    if ttl > 0:
        try:
            _persist_snapshot(session, for_date, list(rows.values()))
        except Exception:
            pass

    return rows


def _persist_snapshot(
    session: Session,
    for_date: date,
    rows: list[DemandRow],
) -> None:
    """Write demand rows to production_demand_snapshot. Upsert by PK.

    Fase 3: uses the SQLAlchemy `ProductionDemandSnapshot` model
    (defined in app/rms.models_legacy because the domain submodules
    in app/rms/models/* are unfinished refactor code — see
    BACKLOG #1 in app/rms/models/__init__.py). Falls back to raw
    SQL INSERT OR REPLACE if the ORM insert fails (e.g. a model
    registration race during tests). Per-row try/except so a single
    bad row doesn't kill the whole batch (snapshot is best-effort;
    the in-memory dict is the source of truth for the current
    request).
    """
    if not rows:
        return

    for r in rows:
        try:
            session.execute(
                text(
                    """
                    INSERT INTO production_demand_snapshot (
                        for_date, product_id, qty_forecast, qty_pedidos,
                        qty_pedidos_confirmed, qty_evento, qty_total,
                        confidence_pct, source, computed_at
                    ) VALUES (
                        :for_date, :product_id, :qty_forecast, :qty_pedidos,
                        :qty_pedidos_confirmed, :qty_evento, :qty_total,
                        :confidence_pct, :source, :computed_at
                    )
                    ON CONFLICT (for_date, product_id) DO UPDATE SET
                        qty_forecast = EXCLUDED.qty_forecast,
                        qty_pedidos = EXCLUDED.qty_pedidos,
                        qty_pedidos_confirmed = EXCLUDED.qty_pedidos_confirmed,
                        qty_evento = EXCLUDED.qty_evento,
                        qty_total = EXCLUDED.qty_total,
                        confidence_pct = EXCLUDED.confidence_pct,
                        source = EXCLUDED.source,
                        computed_at = EXCLUDED.computed_at
                    """
                ),
                {
                    "for_date": for_date.isoformat(),
                    "product_id": r.product_id,
                    "qty_forecast": r.qty_forecast,
                    "qty_pedidos": r.qty_pedidos,
                    "qty_pedidos_confirmed": r.qty_pedidos_confirmed,
                    "qty_evento": r.qty_evento,
                    "qty_total": r.qty_total,
                    "confidence_pct": r.confidence_pct,
                    "source": r.source,
                    "computed_at": r.computed_at.isoformat(),
                },
            )
        except Exception as exc:
            from loguru import logger as _logger

            _logger.debug(f"production_demand._persist_snapshot: row failed: {exc!r}")
            continue
    # Flush so the writes are visible to the caller's session without
    # forcing a commit. The router will commit at end-of-request.
    session.flush()


# ---------------------------------------------------------------------------
# Fase 3: snapshot TTL cache (read path)
# ---------------------------------------------------------------------------


def demand_snapshot_ttl_seconds(session: Session) -> int:
    """Read the configured TTL. 0 means "cache disabled, always recompute".

    Falls back to 300 if the settings table is unavailable (e.g. a
    fresh DB before init). The value is validated as int in
    app/rms/settings.py via the "int" validator, but we cast
    defensively because get_setting_value is typed as `object`.
    """
    try:
        from app.rms.settings import get_setting_value

        raw = get_setting_value(session, "production.demand_snapshot_ttl_seconds")
        if raw is None or raw == "":
            return 300
        return int(str(raw))
    except Exception:
        return 300


def _read_snapshot(
    session: Session, *, for_date: date, ttl_seconds: int
) -> dict[int, DemandRow] | None:
    """Return the cached demand dict if all rows are fresh; else None.

    Freshness rule: every row's `computed_at` is within `ttl_seconds`
    of "now" (UTC). If any row is older, the whole date is treated as
    stale and we return None — the caller will recompute and overwrite
    the snapshot.

    An empty result (no products ever had demand for this date) is
    also a valid cache value: we return `{}` rather than None so the
    caller doesn't recompute for a date that genuinely has nothing
    to compute. We distinguish "no rows yet" (None — recompute) from
    "computed and empty" ({} — serve from cache) by checking the
    most recent computed_at across all rows: if there's no row at
    all, return None.
    """
    from app.rms.models import ProductionDemandSnapshot

    rows = list(
        session.scalars(
            select(ProductionDemandSnapshot).where(
                ProductionDemandSnapshot.for_date == for_date
            )
        ).all()
    )
    if not rows:
        return None  # never computed
    # All rows must be fresh; we use the OLDEST computed_at so a slow
    # row doesn't get served stale.
    cutoff = datetime.now(timezone.utc).timestamp() - ttl_seconds
    result: dict[int, DemandRow] = {}
    for snap in rows:
        ct = snap.computed_at
        if ct.tzinfo is None:
            ct = ct.replace(tzinfo=timezone.utc)
        if ct.timestamp() < cutoff:
            return None  # at least one row is stale
        result[int(snap.product_id)] = DemandRow(
            product_id=int(snap.product_id),
            product_name="",  # snapshot doesn't carry name; caller joins product if needed
            qty_forecast=float(snap.qty_forecast or 0.0),
            qty_pedidos=float(snap.qty_pedidos or 0.0),
            qty_pedidos_confirmed=float(snap.qty_pedidos_confirmed or 0.0),
            qty_evento=float(snap.qty_evento or 0.0),
            qty_total=float(snap.qty_total or 0.0),
            confidence_pct=int(snap.confidence_pct or 0),
            source=str(snap.source or "snapshot"),
            computed_at=ct,  # tz-aware
        )
    return result if result else {}  # empty cache hit → return {}, not None


def invalidate_demand_cache(session: Session, *, for_date: date) -> int:
    """Drop all snapshot rows for a date. Returns the count deleted.

    Hooks:
      - Pedido create / status change → invalidate the pedido's date
      - Sale added → could invalidate tomorrow's date (forecast shifts)
      - /admin → manual "recompute now" button

    Implementation: a single DELETE WHERE for_date = :d. On SQLite
    this is a primary-key range scan; on Postgres the same. Either
    way, O(rows-for-date), typically <50 rows.
    """
    deleted = session.execute(
        text(
            "DELETE FROM production_demand_snapshot WHERE for_date = :for_date"
        ),
        {"for_date": for_date.isoformat()},
    ).rowcount
    return int(deleted or 0)


# ---------------------------------------------------------------------------
# Fase 4: invalidation helpers (thin wrappers, used by router hooks)
# ---------------------------------------------------------------------------


def invalidate_demand_for_dates(
    session: Session, for_dates: list[date] | tuple[date, ...]
) -> int:
    """Drop snapshot rows for a list of dates. Returns the total count deleted.

    Best-effort: errors are logged at debug level and swallowed. A stale
    cache is preferable to a 500 on a pedido POST. The next read
    re-populates on the 5-min TTL boundary.

    Deduplicates the input list so a bulk operation that touches the
    same date twice doesn't issue two DELETEs.

    Used by:
      - POST /pedidos/nuevo        → invalidate [pedido.promised_date]
      - POST /pedidos/{id}/status  → invalidate [pedido.promised_date]
      - POST /pedidos/{id}/fulfill → invalidate [pedido.promised_date]
      - POST /pedidos/bulk-fulfill → invalidate [p.promised_date for p in selection]
      - POST /pedidos/bulk-cancel  → invalidate [p.promised_date for p in selection]
      - POST /sales/nueva          → invalidate [today, today+1, today+2, today+3]
    """
    from loguru import logger as _logger

    if not for_dates:
        return 0
    seen: set[date] = set()
    total = 0
    for d in for_dates:
        if d in seen:
            continue
        seen.add(d)
        try:
            total += invalidate_demand_cache(session, for_date=d)
        except Exception as exc:
            _logger.debug(
                f"production_demand.invalidate_demand_for_dates: {d.isoformat()} failed: {exc!r}"
            )
    return total


def invalidate_demand_for_sale_today(
    session: Session, *, today: date | None = None, window_days: int = 4
) -> int:
    """Invalidate a window of dates after a new sale is added.

    The 14d rolling forecast shifts every time a sale is added, so the
    cached demand for nearby dates is stale. We invalidate today + the
    next 3 days (window_days=4) — the dates the operator is most
    likely to look at. Dates further out will age out via the 5-min TTL.

    Args:
        session: SQLAlchemy session (the same one the sale was committed on).
        today: anchor date. Defaults to `date.today()` in Asunción local.
        window_days: how many days forward to invalidate (default 4 = today + 3).
    """
    from datetime import timedelta

    from app.rms.config import ASUNCION_TZ

    if today is None:
        today = datetime.now(ASUNCION_TZ).date()
    dates = [today + timedelta(days=i) for i in range(window_days)]
    return invalidate_demand_for_dates(session, dates)


# ---------------------------------------------------------------------------
# Plan audit (append-only log of changes to the plan, not the demand)
# ---------------------------------------------------------------------------


def persist_plan_audit(
    session: Session,
    *,
    for_date: date,
    product_id: int,
    old_qty: float | None,
    new_qty: float,
    change_source: str,
    changed_by: str | None,
    notes: str | None = None,
) -> None:
    """Append a single row to production_plan_audit.

    Caller is responsible for session.commit(). This function only
    adds + flushes the row so a missing commit doesn't lose the audit
    trail silently — if the route raises after this point, the
    SQLAlchemy session rollback will discard the audit row, but the
    PRIMARY transaction (the plan write) is also rolled back, so
    audit and reality stay consistent.

    Args:
        session: SQLAlchemy session.
        for_date: the production date the change applies to.
        product_id: the product whose plan changed.
        old_qty: the previous qty, or None if this is the first write
            (e.g. template row created, ad-hoc bake recorded).
        new_qty: the new qty (always present).
        change_source: one of 'template', 'override', 'override_bulk',
            'manual_form', 'adhoc', 'adhoc_bulk', 'fork_week',
            'shift_execute'. The router enforces this set; we don't
            validate here so a future source doesn't need a code change
            in this module.
        changed_by: username or session id, or None for system writes.
        notes: optional free-text (e.g. "Cerrado por feriado").
    """
    if new_qty < 0:
        raise ValueError(f"new_qty must be >= 0; got {new_qty}")
    if not change_source:
        raise ValueError("change_source is required")

    session.execute(
        text(
            """
            INSERT INTO production_plan_audit (
                for_date, product_id, old_qty, new_qty,
                change_source, changed_by, changed_at, notes
            ) VALUES (
                :for_date, :product_id, :old_qty, :new_qty,
                :change_source, :changed_by, CURRENT_TIMESTAMP, :notes
            )
            """
        ),
        {
            "for_date": for_date.isoformat(),
            "product_id": int(product_id),
            "old_qty": (None if old_qty is None else float(old_qty)),
            "new_qty": float(new_qty),
            "change_source": str(change_source),
            "changed_by": (None if changed_by is None else str(changed_by)[:64]),
            "notes": (None if notes is None else str(notes)[:512]),
        },
    )
    session.flush()


__all__ = [
    "DemandRow",
    "compute_demand_qty",
    "get_demand",
    "persist_plan_audit",
    "split_pedidos_status",
]

# ---------------------------------------------------------------------------
# P40: EOD snapshot warmer
# ---------------------------------------------------------------------------


def warm_snapshots_for_dates(
    session: Session,
    dates: list[date],
) -> int:
    """P40 (2026-10-07, Ivan) — fill production_demand_snapshot for N dates.

    The snapshot TTL is 5 min by default and is normally filled lazily
    when the operator opens /produccion or /produccion/manana. Operators
    don't open the day view every day, so demand snapshots have been
    sitting empty for 30+ days. Calling this from the EOD view (or
    the EOD cron) ensures the morning /produccion/manana always
    finds fresh data without forcing a recompute at view time.

    Best-effort: if a date has no products yet, the snapshot is empty
    (0 rows written). Errors per-date are logged and skipped; the
    function returns the count of dates successfully warmed.

    Returns:
        Number of dates for which get_demand() was invoked without
        raising. The route logs this for EOD telemetry.
    """
    warmed = 0
    for d in dates:
        try:
            get_demand(session, for_date=d)
            warmed += 1
        except Exception as exc:
            from loguru import logger as _logger
            _logger.debug(
                f"production_demand.warm_snapshots_for_dates: "
                f"{d.isoformat()} failed: {exc!r}"
            )
            continue
    # Commit so the writes are visible to readers using a different
    # session (e.g. the next request, or a test reading the table
    # after the warmer ran). Without this, a single-session test
    # sees the data but a multi-session test (or a subsequent HTTP
    # request in production) does not.
    try:
        session.commit()
    except Exception:
        # If commit fails (e.g. read-only test DB), best-effort.
        session.rollback()
    return warmed
