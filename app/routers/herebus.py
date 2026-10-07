"""app/routers/herebus.py — HEREBUS business modules.

Routes:
  - /wishlist      — kitchen equipment wishlist (28 items seeded)
  - /riesgos       — risk register (12 risks seeded)
  - /pricing       — per-channel recipe pricing (7 recipes)
  - /bank          — bank transactions (Dutch EUR TAB imported)
  - /benchmarks    — vs competitor pricing
  - /dashboard     — KPI dashboard (revenue, food cost %, etc.)
  - /produccion-planner — recipe × batches → ingredient shortfall calc

All routes are read-only by default. Mutations guarded by require_login.
"""

from __future__ import annotations

import csv
import io
import json
from collections import defaultdict
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_login_or_disabled as require_login
from app.rms.config import ASUNCION_TZ
from app.rms.dependencies import get_session
from app.rms.errors import (
    BadRequest,
    NotFound,
)
from app.rms.models import (
    BankTransaction,
    CompetitorPriceObservation,
    DeliveryZone,
    Ingredient,
    MarketBenchmark,
    ProductionPlan,
    Recipe,
    RecipeLine,
    RecipePricing,
    RiskItem,
    Sale,
    SettingsKV,
    ShoppingListItem,
    WasteLog,
    WishlistItem,
)
from app.rms.models.channels import Channel
from app.rms.observability import record_audit
from app.services.template_render import render

# Stub routers; each is a real prefix-based router for its module
wishlist_router = APIRouter(prefix="/wishlist", dependencies=[Depends(require_login)])
risks_router = APIRouter(prefix="/riesgos", dependencies=[Depends(require_login)])
pricing_router = APIRouter(prefix="/pricing", dependencies=[Depends(require_login)])
bank_router = APIRouter(prefix="/bank", dependencies=[Depends(require_login)])
benchmarks_router = APIRouter(prefix="/vs-mercado", dependencies=[Depends(require_login)])
dashboard_router = APIRouter(prefix="/dashboard", dependencies=[Depends(require_login)])
planner_router = APIRouter(prefix="/produccion-planner", dependencies=[Depends(require_login)])
delivery_router = APIRouter(prefix="/delivery-zones", dependencies=[Depends(require_login)])

# ──────────────────────────────────────────────────────────────────
# Wishlist
# ──────────────────────────────────────────────────────────────────


@wishlist_router.get("", response_class=HTMLResponse)
def wishlist_list(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    items = (
        session.execute(
            select(WishlistItem).order_by(WishlistItem.purchased, WishlistItem.priority)
        )
        .scalars()
        .all()
    )

    by_priority = defaultdict(list)
    for item in items:
        by_priority[item.priority].append(item)

    total_pending = sum(item.unit_price_gs * item.quantity for item in items if not item.purchased)
    total_all = sum(item.unit_price_gs * item.quantity for item in items)

    return render(
        request,
        "wishlist.html",
        {
            "items": items,
            "by_priority": dict(by_priority),
            "total_pending_gs": total_pending,
            "total_all_gs": total_all,
            "purchased_count": sum(1 for i in items if i.purchased),
            "pending_count": sum(1 for i in items if not i.purchased),
        },
    )


@wishlist_router.post("/{item_id}/mark-purchased")
async def wishlist_mark_purchased(
    request: Request,
    item_id: int,
    session: Session = Depends(get_session),
) -> RedirectResponse:
    item = session.get(WishlistItem, item_id)
    if not item:
        raise NotFound("WishlistItem", id=item_id)
    item.purchased = True
    item.purchased_at = datetime.now(timezone.utc)
    session.commit()
    logger.info(
        "wishlist_marked_purchased item_id={} name={!r} price_gs={}",
        item.id,
        item.name,
        item.unit_price_gs,
    )
    record_audit(
        request,
        session=session,
        action="wishlist.mark_purchased",
        target_type="WishlistItem",
        target_id=item.id,
        detail={"name": item.name},
    )
    return RedirectResponse(url="/wishlist", status_code=303)


@wishlist_router.post("/{item_id}/send-to-shopping-list")
async def wishlist_send_to_shopping_list(
    request: Request,
    item_id: int,
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Send wishlist equipment item to the shopping list (so user can
    buy it through the standard shopping-list flow)."""
    item = session.get(WishlistItem, item_id)
    if not item:
        return RedirectResponse(url="/wishlist", status_code=303)
    if item.purchased:
        return RedirectResponse(
            url="/wishlist?msg=Ya%20comprado",
            status_code=303,
        )
    # Create a shopping list entry for the equipment.
    # Equipment items don't have an Ingredient row, so we create an
    # "[EQUIPMENT] {name}" pseudo-ingredient on the fly.
    from app.rms.models import Ingredient, ShoppingListItem

    eq_ing = (
        session.execute(select(Ingredient).where(Ingredient.name == f"[EQUIPMENT] {item.name}"))
        .scalars()
        .first()
    )
    if not eq_ing:
        eq_ing = Ingredient(
            name=f"[EQUIPMENT] {item.name}",
            unit="und",
            stock_qty=0,
            purchase_price_gs=item.unit_price_gs,
            min_stock_qty=0,
            category="Equipment",
            notes=f"Auto-created from wishlist #{item.id}",
        )
        session.add(eq_ing)
        session.flush()
    # Idempotency: an open (not-yet-purchased) row for this wishlist item
    # must not be duplicated on re-send.
    from app.rms.models import ShoppingListItem as _SLI

    existing = (
        session.execute(
            select(_SLI).where(
                _SLI.ingredient_id == eq_ing.id,
                _SLI.purpose_text.like(f"Wishlist #{item.id}%"),
                _SLI.purchased_at.is_(None) if hasattr(_SLI, "purchased_at") else True,
            )
        )
        .scalars()
        .first()
    )
    if existing is None:
        sl = ShoppingListItem(
            ingredient_id=eq_ing.id,
            production_plan_id=None,
            qty_to_buy=item.quantity,
            unit="und",
            purpose_text=f"Wishlist #{item.id} — {item.buy_location or 'TBD'}",
        )
        session.add(sl)
        session.commit()
    return RedirectResponse(
        url=f"/shopping-list?from_wishlist={item.id}&n_added=1",
        status_code=303,
    )


# ──────────────────────────────────────────────────────────────────
# Risk register
# ──────────────────────────────────────────────────────────────────


PRIORITY_LABELS = {
    "must_have": "🟢 Must",
    "nice_to_have": "🟡 Nice",
    "optional": "⚪ Optional",
}

RISK_CATEGORIES = [
    "Operacional",
    "Externo",
    "Reputacional",
    "Comercial",
    "Legal",
    "Personal",
]


@risks_router.get("", response_class=HTMLResponse)
def risk_list(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    items = (
        session.execute(select(RiskItem).order_by(RiskItem.status, RiskItem.probability.desc()))
        .scalars()
        .all()
    )

    # Compute severity = probability × impact for risk heat
    for item in items:
        item.severity = item.probability * item.impact_gs

    severity_total = sum(
        (item.probability * item.impact_gs) for item in items if item.status == "activo"
    )

    by_category = defaultdict(list)
    for item in items:
        by_category[item.category or "Otros"].append(item)

    return render(
        request,
        "riesgos.html",
        {
            "items": items,
            "by_category": dict(by_category),
            "severity_total_gs": severity_total,
            "active_count": sum(1 for i in items if i.status == "activo"),
            "mitigated_count": sum(1 for i in items if i.status == "mitigated"),
            "closed_count": sum(1 for i in items if i.status == "cerrado"),
            "flash": request.session.pop("flash_risk", None)
            if hasattr(request, "session")
            else None,
        },
    )


@risks_router.post("/new")
def risk_create(
    request: Request,
    description: str = Form(""),
    category: str = Form(""),
    probability: int = Form(2),
    impact_gs: int = Form(0),
    mitigation: str = Form(""),
    owner: str = Form(""),
    notes: str = Form(""),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Create a new risk on the registry (closes Phase-14 #nav:11 TODO).

    The same validation rules as the model CheckConstraints apply:
      - probability BETWEEN 1 AND 5
      - impact_gs >= 0
      - description non-empty (NOT NULL, len 1..255)
    On violation we re-render the list with a flash message.
    """
    from app.rms.validation import optional_text, require_text

    errors: list[str] = []
    try:
        clean_description = require_text(description, field="descripción", max_len=255)
    except HTTPException as e:
        errors.append(str(e.detail))
        # Don't fall back — description is NOT NULL in the schema; reject.
        clean_description = ""

    if not (1 <= int(probability) <= 5):
        errors.append("La probabilidad debe estar entre 1 y 5.")
    if int(impact_gs) < 0:
        errors.append("El impacto Gs. no puede ser negativo.")

    if errors:
        if hasattr(request, "session"):
            request.session["flash_risk"] = {
                "severity": "error",
                "message": "; ".join(errors),
            }
        return RedirectResponse(url="/riesgos", status_code=303)

    item = RiskItem(
        description=clean_description,
        category=optional_text(category, max_len=32) or None,
        probability=int(probability),
        impact_gs=int(impact_gs),
        mitigation=optional_text(mitigation, max_len=2000) or None,
        status="activo",  # default: new risks are active (DB CHECK accepts 'activo')
        owner=optional_text(owner, max_len=64) or None,
        notes=optional_text(notes, max_len=2000) or None,
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    record_audit(
        request,
        session=session,
        action="write.risk.create",
        target_type="risk_item",
        target_id=item.id,
        detail={"description": clean_description, "category": category},
    )
    session.commit()
    if hasattr(request, "session"):
        request.session["flash_risk"] = {
            "severity": "ok",
            "message": f"Riesgo «{clean_description[:30]}» registrado.",
        }
    return RedirectResponse(url="/riesgos", status_code=303)


# ──────────────────────────────────────────────────────────────────
# Pricing (per-channel)
# ──────────────────────────────────────────────────────────────────


@pricing_router.get("", response_class=HTMLResponse)
def pricing_list(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    pricings = session.execute(
        select(RecipePricing, Recipe)
        .join(Recipe, Recipe.id == RecipePricing.recipe_id)
        .order_by(Recipe.name)
    ).all()

    # Inject recipe object for template convenience
    rows = []
    for p, recipe in pricings:
        p.recipe = recipe
        rows.append(p)

    # Load channel margin from settings
    margins_json = session.get(SettingsKV, "channels_margins")
    margins = json.loads(margins_json.value_json) if margins_json else {}

    total_cost = sum(p.cost_total_gs for p, _ in pricings)
    total_retail = sum(p.retail_gs for p, _ in pricings)

    return render(
        request,
        "pricing.html",
        {
            "rows": rows,
            "channels_margins": margins,
            "total_cost_gs": total_cost,
            "total_retail_gs": total_retail,
        },
    )


# ──────────────────────────────────────────────────────────────────
# Bank Transactions
# ──────────────────────────────────────────────────────────────────


@bank_router.post("/add")
async def bank_add(
    request: Request,
    posted_at: str = Form(...),  # YYYY-MM-DD
    currency: str = Form("EUR"),
    amount: float = Form(...),
    counterparty_name: str = Form(""),
    counterparty_iban: str = Form(""),
    description: str = Form(""),
    category: str = Form("manual"),
    source: str = Form("manual_entry"),
    session: Session = Depends(get_session),
) -> dict:
    """Manually add a bank transaction (e.g. for the PY savings statement).

    Parse the date and insert.
    """
    from datetime import datetime as dt

    try:
        posted_at_dt = dt.strptime(posted_at, "%Y-%m-%d").replace(tzinfo=ASUNCION_TZ)
    except ValueError:
        raise BadRequest(
            "Fecha inválida.",
            context={"posted_at": posted_at, "expected_format": "YYYY-MM-DD"},
        ) from None

    tx = BankTransaction(
        posted_at=posted_at_dt,
        currency=currency.upper(),
        amount=amount,
        counterparty_name=counterparty_name,
        counterparty_iban=counterparty_iban or None,
        description=description,
        category=category,
        source=source,
    )
    session.add(tx)
    session.commit()
    logger.info(
        "bank_tx_added id={} amount={} {} category={} description={!r}",
        tx.id,
        amount,
        currency.upper(),
        category,
        description[:60] if description else "",
    )
    record_audit(
        request,
        session=session,
        action="bank.add",
        target_type="BankTransaction",
        target_id=tx.id,
        detail={
            "amount": amount,
            "currency": currency.upper(),
            "category": category,
            "counterparty": counterparty_name,
        },
    )
    return RedirectResponse(url="/bank", status_code=303)


@bank_router.post("/{tx_id}/categorize")
async def bank_categorize(
    request: Request,
    tx_id: int,
    category: str = Form(...),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Auto-categorize a bank transaction."""
    tx = session.get(BankTransaction, tx_id)
    if not tx:
        raise NotFound("BankTransaction", id=tx_id)
    old_category = tx.category
    tx.category = category
    session.commit()
    logger.info(
        "bank_tx_recategorized id={} {} → {} amount={} {}",
        tx.id,
        old_category,
        category,
        tx.amount,
        tx.currency,
    )
    record_audit(
        request,
        session=session,
        action="write.bank.categorize",
        target_type="BankTransaction",
        target_id=tx.id,
        detail={
            "from": old_category,
            "to": category,
            "amount": tx.amount,
        },
    )
    session.commit()
    return RedirectResponse(url="/bank", status_code=303)


@bank_router.get("/export.csv", response_class=Response)
async def bank_export_csv(
    request: Request,
    category: str | None = Query(None),
    start_date: str | None = Query(None, alias="start_date"),
    end_date: str | None = Query(None, alias="end_date"),
    currency: str | None = Query(None),
    session: Session = Depends(get_session),
) -> Response:
    """CSV export of bank transactions."""
    query = select(BankTransaction).order_by(BankTransaction.posted_at.desc())

    # Apply date range filter if provided
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date)
            query = query.where(BankTransaction.posted_at >= start_dt)
        except (ValueError, TypeError) as exc:
            # User-supplied date filter; bad input → just skip the filter.
            logger.debug("herebus start_dt filter dropped: {}", exc)

    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date)
            query = query.where(BankTransaction.posted_at <= end_dt)
        except (ValueError, TypeError) as exc:
            # User-supplied date filter; bad input → just skip the filter.
            logger.debug("herebus start_dt filter dropped: {}", exc)

    if category:
        query = query.where(BankTransaction.category == category)

    if currency:
        query = query.where(BankTransaction.currency == currency)

    transactions = session.execute(query).scalars().all()

    # Create CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Fecha", "Cuenta", "Importe", "Categoría", "Contraparte", "Descripción"])

    for tx in transactions:
        writer.writerow(
            [
                tx.posted_at.strftime("%Y-%m-%d"),
                tx.currency,
                f"{tx.amount:+.2f}",
                tx.category or "",
                tx.counterparty_name or "",
                tx.description or "",
            ]
        )

    # Create response
    response = Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=bank_transactions.csv"},
    )

    return response


@bank_router.post("/{tx_id}/reconcile", response_class=HTMLResponse)
async def bank_reconcile(
    request: Request,
    tx_id: int,
    with_type: str = Form(...),
    with_id: int = Form(...),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Mark a bank transaction as reconciled with an entity (pedido, gasto, ingreso)."""
    # Get the transaction
    tx = session.execute(
        select(BankTransaction).where(BankTransaction.id == tx_id)
    ).scalar_one_or_none()

    if not tx:
        return RedirectResponse(url="/bank", status_code=303)

    # Validate with_type
    if with_type not in ("pedido", "gasto", "ingreso"):
        return RedirectResponse(url="/bank", status_code=303)

    # Mark as reconciled
    tx.reconciled = True
    tx.reconciled_with_type = with_type
    tx.reconciled_with_id = with_id
    tx.reconciled_at = datetime.now(timezone.utc)
    # Phase 14 — populate reconciled_by from the session set by
    # ObservabilityContextMiddleware (request.state.user_id). Falls back
    # to "anonymous" if the middleware hasn't run (e.g. direct unit
    # test) so the field always has a meaningful audit trail.
    tx.reconciled_by = getattr(request.state, "user_id", None) or "anonymous"

    session.commit()

    return RedirectResponse(url="/bank", status_code=303)


@bank_router.post("/{tx_id}/unreconcile", response_class=HTMLResponse)
async def bank_unreconcile(
    request: Request,
    tx_id: int,
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Mark a bank transaction as unreconciled."""
    tx = session.execute(
        select(BankTransaction).where(BankTransaction.id == tx_id)
    ).scalar_one_or_none()

    if not tx:
        return RedirectResponse(url="/bank", status_code=303)

    # Mark as unreconciled
    tx.reconciled = False
    tx.reconciled_with_type = None
    tx.reconciled_with_id = None
    tx.reconciled_at = None
    tx.reconciled_by = None

    session.commit()

    return RedirectResponse(url="/bank", status_code=303)


@bank_router.get("", response_class=HTMLResponse)
def bank_list(
    request: Request,
    category: str = Query(None),
    start_date: str | None = Query(None, alias="start_date"),
    end_date: str | None = Query(None, alias="end_date"),
    currency: str | None = Query(None),
    reconciled: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=10, le=200),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    query = select(BankTransaction).order_by(BankTransaction.posted_at.desc())

    # Apply date range filter if provided
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date)
            query = query.where(BankTransaction.posted_at >= start_dt)
        except (ValueError, TypeError) as exc:
            # User-supplied date filter; bad input → just skip the filter.
            logger.debug("herebus start_dt filter dropped: {}", exc)

    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date)
            query = query.where(BankTransaction.posted_at <= end_dt)
        except (ValueError, TypeError) as exc:
            # User-supplied date filter; bad input → just skip the filter.
            logger.debug("herebus start_dt filter dropped: {}", exc)

    if category:
        query = query.where(BankTransaction.category == category)

    if currency:
        query = query.where(BankTransaction.currency == currency)

    # Apply reconciliation filter
    if reconciled == "yes":
        query = query.where(BankTransaction.reconciled)
    elif reconciled == "no":
        query = query.where(not BankTransaction.reconciled)

    # Get total count for pagination
    from sqlalchemy import func

    total_count = session.execute(select(func.count()).select_from(query.subquery())).scalar() or 0

    # Apply pagination
    offset = (page - 1) * per_page
    transactions = session.execute(query.limit(per_page).offset(offset)).scalars().all()

    # Calculate pagination info
    total_pages = (total_count + per_page - 1) // per_page if total_count > 0 else 1
    has_prev = page > 1
    has_next = page < total_pages

    # Get reconciliation stats
    reconciled_count = (
        session.execute(
            select(func.count()).select_from(BankTransaction).where(BankTransaction.reconciled)
        ).scalar()
        or 0
    )

    unreconciled_count = (
        session.execute(
            select(func.count()).select_from(BankTransaction).where(not BankTransaction.reconciled)
        ).scalar()
        or 0
    )

    # Compute aggregates
    session.execute(
        select(
            BankTransaction.currency,
            BankTransaction.count,
        ).group_by(BankTransaction.currency)
    ).all() if False else None  # Avoid complex aggregate for speed

    # Simpler aggregates
    eur_total = (
        session.execute(select(BankTransaction.amount).where(BankTransaction.currency == "EUR"))
        .scalars()
        .all()
    )

    pyg_total = (
        session.execute(select(BankTransaction.amount).where(BankTransaction.currency == "PYG"))
        .scalars()
        .all()
    )

    income = sum(a for a in eur_total if a > 0)
    spent = abs(sum(a for a in eur_total if a < 0))
    pyg_balance = sum(pyg_total) if pyg_total else 0

    # Get all categories
    categories = list({tx.category for tx in transactions if tx.category})

    return render(
        request,
        "bank.html",
        {
            "transactions": transactions,
            "eur_income": income,
            "eur_spent": spent,
            "eur_net": income - spent,
            "pyg_balance_gs": pyg_balance,
            "categories": sorted(categories),
            "active_category": category,
            "active_currency": currency,
            "active_reconciled": reconciled,
            "page": page,
            "per_page": per_page,
            "total_count": total_count,
            "total_pages": total_pages,
            "has_prev": has_prev,
            "has_next": has_next,
            "reconciled_count": reconciled_count,
            "unreconciled_count": unreconciled_count,
        },
    )


# ──────────────────────────────────────────────────────────────────
# Market Benchmarks
# ──────────────────────────────────────────────────────────────────


@benchmarks_router.get("", response_class=HTMLResponse)
def benchmarks_list(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    from app.rms.market_intel import family_of, stats_by_family

    benchmarks = (
        session.execute(select(MarketBenchmark).order_by(MarketBenchmark.product_label))
        .scalars()
        .all()
    )

    # market-intel: rangos reales por familia desde la evidencia de competencia
    fam_stats = stats_by_family(session, unit="unidad")

    # Compute position (above / below market)
    for b in benchmarks:
        b.family = family_of(b.product_label)
        st = fam_stats.get(b.family or "")
        if st:
            b.intel_median_gs = st.median_gs
            b.intel_n = st.n
        else:
            b.intel_median_gs = None
            b.intel_n = 0
        if not b.market_avg_gs:
            b.position_label = "—"
            b.pct = 0
            continue
        if b.our_retail_gs and b.our_retail_gs > b.market_avg_gs:
            b.pct = round((b.our_retail_gs - b.market_avg_gs) / b.market_avg_gs * 100)
            b.position_label = f"+{b.pct}%"
        elif b.our_retail_gs and b.our_retail_gs < b.market_avg_gs:
            b.pct = round((b.market_avg_gs - b.our_retail_gs) / b.market_avg_gs * 100)
            b.position_label = f"-{b.pct}%"
        else:
            b.pct = 0
            b.position_label = "iguales"

    return render(
        request,
        "benchmarks.html",
        {
            "benchmarks": benchmarks,
        },
    )


@benchmarks_router.get("/evidencia", response_class=HTMLResponse)
def evidencia_view(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    """Rangos por familia desde la evidencia de competencia + observaciones recientes."""
    from app.rms.market_intel import family_stats

    stats = family_stats(session)
    recientes = (
        session.execute(
            select(CompetitorPriceObservation)
            .order_by(CompetitorPriceObservation.as_of.desc(), CompetitorPriceObservation.id.desc())
            .limit(40)
        )
        .scalars()
        .all()
    )
    total = session.query(CompetitorPriceObservation).count()
    return render(
        request,
        "evidencia_mercado.html",
        {"stats": stats, "recientes": recientes, "total": total},
    )


@benchmarks_router.get("/evidencia.csv")
def evidencia_csv(session: Session = Depends(get_session)) -> Response:
    """Export completo de la evidencia (auditoría / re-import al research repo)."""
    rows = (
        session.execute(
            select(CompetitorPriceObservation).order_by(
                CompetitorPriceObservation.family, CompetitorPriceObservation.price_gs
            )
        )
        .scalars()
        .all()
    )
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "competidor",
            "tipo",
            "ciudad",
            "producto",
            "familia",
            "unidad",
            "precio_gs",
            "as_of",
            "fuente",
        ]
    )
    for r in rows:
        writer.writerow(
            [
                r.competitor_name,
                r.competitor_type or "",
                r.city or "",
                r.product_name,
                r.family or "",
                r.unit,
                r.price_gs,
                r.as_of.isoformat(),
                r.source or "",
            ]
        )
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=evidencia-mercado.csv"},
    )


@benchmarks_router.post("/evidencia/importar")
async def evidencia_importar(
    request: Request,
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Import CSV (mismas columnas que el export) — idempotente.

    Confirma en el formulario: regla anti-silent-overwrite del repo.
    Filas sin fuente o con precio fuera de 300–500.000 se rechazan.
    """
    from datetime import date as _date

    form = await request.form()
    if form.get("confirmar") != "si":
        raise BadRequest("Importación sin confirmación explícita")
    raw = form.get("csv")
    if not raw or not getattr(raw, "filename", ""):
        raise BadRequest("Adjuntá un archivo CSV")
    from starlette.datastructures import UploadFile

    if not isinstance(raw, UploadFile):
        raise BadRequest("Adjuntá un archivo CSV")
    from app.rms.upload_limits import CSV_LIMIT_2MB, CSV_MIME_TYPES, validate_upload

    try:
        validate_upload(raw, allowed_types=CSV_MIME_TYPES, max_size=CSV_LIMIT_2MB)
    except HTTPException as exc:
        raise BadRequest(exc.detail) from None
    content = (await raw.read()).decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(content))
    required = {"competidor", "producto", "unidad", "precio_gs", "as_of"}
    if not required.issubset({(c or "").strip().lower() for c in reader.fieldnames or []}):
        raise BadRequest(
            "CSV inválido: columnas requeridas competidor,producto,unidad,precio_gs,as_of"
        )
    existing = set(
        session.execute(
            select(
                CompetitorPriceObservation.competitor_name,
                CompetitorPriceObservation.product_name,
                CompetitorPriceObservation.as_of,
            )
        ).all()
    )
    added = skipped_invalid = dup = 0
    from app.rms.market_intel import family_of

    for row in reader:
        comp = (row.get("competidor") or "").strip()
        prod = (row.get("producto") or "").strip()
        try:
            price = int(float(str(row.get("precio_gs") or 0).replace(".", "").replace(",", "")))
            as_of = _date.fromisoformat((row.get("as_of") or "").strip()[:10])
        except (ValueError, TypeError):
            skipped_invalid += 1
            continue
        if not comp or not prod or not (300 <= price <= 500_000):
            skipped_invalid += 1
            continue
        if not (row.get("fuente") or "").strip():
            skipped_invalid += 1
            continue
        key = (comp[:120], prod[:160], as_of)
        if key in existing:
            dup += 1
            continue
        existing.add(key)
        session.add(
            CompetitorPriceObservation(
                competitor_name=key[0],
                competitor_type=(row.get("tipo") or "").strip()[:32] or None,
                city=(row.get("ciudad") or "").strip()[:64] or None,
                product_name=key[1],
                family=family_of(prod),
                unit=(row.get("unidad") or "unidad").strip()[:16],
                price_gs=price,
                as_of=as_of,
                source=(row.get("fuente") or "").strip(),
            )
        )
        added += 1
    session.commit()
    logger.info(
        f"market-intel: import {added} nuevas, {dup} duplicadas, {skipped_invalid} inválidas"
    )
    return RedirectResponse("/vs-mercado/evidencia", status_code=303)


@benchmarks_router.get("/evidencia/seed-demo", name="evidencia_seed_demo")
def evidencia_seed_demo_route(session: Session = Depends(get_session)) -> RedirectResponse:
    """Idempotente: siembra las 86 observaciones del research repo (2026-09-30)."""
    from app.rms.seed.competitor_prices import seed_competitor_prices

    added, skipped = seed_competitor_prices(session)
    logger.info(f"market-intel seed: {added} nuevas, {skipped} ya presentes")
    return RedirectResponse("/vs-mercado/evidencia", status_code=303)


@benchmarks_router.get("/{bench_id}/edit", response_class=HTMLResponse)
def benchmarks_edit(
    request: Request,
    bench_id: int,
    session: Session = Depends(get_session),
) -> object:
    """Render the edit form for a single benchmark."""
    bench = session.get(MarketBenchmark, bench_id)
    if not bench:
        return RedirectResponse(url="/vs-mercado", status_code=303)
    return render(
        request,
        "benchmark_edit.html",
        {"b": bench, "saved": False},
    )


@benchmarks_router.post("/{bench_id}/save")
def benchmarks_save(
    request: Request,
    bench_id: int,
    our_wholesale_gs: int = Form(0),
    our_retail_gs: int = Form(0),
    comp_min_gs: int = Form(0),
    comp_avg_gs: int = Form(0),
    market_avg_gs: int = Form(0),
    source: str = Form(""),
    session: Session = Depends(get_session),
) -> object:
    """Save edited competitor prices."""
    bench = session.get(MarketBenchmark, bench_id)
    if not bench:
        return RedirectResponse(url="/vs-mercado", status_code=303)
    bench.our_wholesale_gs = our_wholesale_gs or None
    bench.our_retail_gs = our_retail_gs or None
    bench.comp_min_gs = comp_min_gs or None
    bench.comp_avg_gs = comp_avg_gs or None
    bench.market_avg_gs = market_avg_gs or None
    bench.source = source
    session.commit()
    # Re-render with success flag
    return render(
        request,
        "benchmark_edit.html",
        {"b": bench, "saved": True},
    )


# ──────────────────────────────────────────────────────────────────
# KPI Dashboard — derived live from existing data
# ──────────────────────────────────────────────────────────────────


@dashboard_router.get("", response_class=HTMLResponse)
def dashboard_index(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    """HEREBUS KPI dashboard.

    Computes the 12 KPIs from the ANALISIS sheet live from the database.
    No data entry required — the dashboard is purely a query view.
    """
    # Revenue this month
    from datetime import datetime

    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    sales_this_month = (
        session.execute(select(Sale).where(Sale.sold_at >= month_start)).scalars().all()
    )

    revenue_gs = sum(int(s.qty * s.unit_price_gs) for s in sales_this_month)
    portions = sum(s.qty for s in sales_this_month)
    unique_customers = len({s.customer_id for s in sales_this_month if s.customer_id})
    repeat = sum(
        1
        for s in sales_this_month
        if s.customer_id
        and sum(1 for s2 in sales_this_month if s2.customer_id == s.customer_id) > 1
    )

    # Cost of ingredients sold (approximate via recipe pricing)
    total_food_cost_gs = 0
    for s in sales_this_month:
        pricing = (
            session.execute(
                select(RecipePricing).where(
                    RecipePricing.recipe_id == s.product.recipe_id if s.product else None
                )
            )
            .scalars()
            .first()
        )
        if pricing:
            total_food_cost_gs += int(pricing.cost_per_unit_gs * s.qty)

    if revenue_gs > 0 and total_food_cost_gs > 0:
        food_cost_pct = total_food_cost_gs / revenue_gs * 100
        gross_margin_pct = 100 - food_cost_pct
    else:
        # No recipe costing data → reporting a margin would be fiction (e.g. 100%)
        food_cost_pct = None
        gross_margin_pct = None

    # Waste this month
    waste_gs = (
        session.execute(select(WasteLog.cost_gs).where(WasteLog.recorded_at >= month_start))
        .scalars()
        .all()
    )
    waste_total_gs = sum(waste_gs)
    waste_pct = (waste_total_gs / revenue_gs * 100) if revenue_gs > 0 else 0

    # Recipe count
    recipe_count = session.execute(select(Recipe)).scalars().all()
    recipes_cooked = len({s.product.recipe_id for s in sales_this_month if s.product})

    # Avg order value
    avg_order = revenue_gs / len(sales_this_month) if sales_this_month else 0

    # Channels breakdown
    by_channel = defaultdict(int)
    for s in sales_this_month:
        ch = s.channel or Channel.MOSTRADOR.value  # P43: Channel enum fallback
        by_channel[ch] += int(s.qty * s.unit_price_gs)

    # Top recipe by revenue (approximate)
    by_recipe = defaultdict(int)
    for s in sales_this_month:
        if s.product:
            by_recipe[s.product.name] += int(s.qty * s.unit_price_gs)
    top_recipe = max(by_recipe.items(), key=lambda kv: kv[1], default=("—", 0))

    # Shopping list + wishlist + risks KPIs (batched: one query per entity).
    # Total ~6 queries — see test_dashboard_perf.py budget.
    # Shopping list: count + total estimated ₲ in one query
    from sqlalchemy import func as sa_func

    from app.rms.models import (
        Ingredient,
        RiskItem,
        ShoppingListItem,
        WishlistItem,
    )

    sl_agg = session.execute(
        select(
            sa_func.count(ShoppingListItem.id),
            sa_func.coalesce(
                sa_func.sum(ShoppingListItem.qty_to_buy * Ingredient.purchase_price_gs),
                0,
            ),
        )
        .join(Ingredient, ShoppingListItem.ingredient_id == Ingredient.id)
        .where(ShoppingListItem.purchased.is_(False))
    ).one()
    sl_open_count, sl_total_gs = int(sl_agg[0] or 0), int(sl_agg[1] or 0)

    # Wishlist: count + total
    wishlist_agg = session.execute(
        select(
            sa_func.count(WishlistItem.id),
            sa_func.coalesce(
                sa_func.sum(WishlistItem.unit_price_gs * WishlistItem.quantity),
                0,
            ),
        ).where(WishlistItem.purchased.is_(False))
    ).one()
    wishlist_count, wishlist_total_gs = int(wishlist_agg[0] or 0), int(wishlist_agg[1] or 0)

    # Risks: count + total severity (probability × impact)
    risk_agg = session.execute(
        select(
            sa_func.count(RiskItem.id),
            sa_func.coalesce(
                sa_func.sum(RiskItem.probability * RiskItem.impact_gs),
                0,
            ),
        ).where(RiskItem.status == "activo")
    ).one()
    risk_count, risk_severity_gs = int(risk_agg[0] or 0), int(risk_agg[1] or 0)

    # Sazon onboarding guard — show a small welcome banner if seed_sazon
    # has been run (multi-tenant demo data loaded). The AppMeta row is
    # written by app/rms/seed/sazon.py; see is_sazon_seeded() / sazon_meta().
    from app.rms.seed.sazon import is_sazon_seeded, sazon_meta

    sazon_seeded = is_sazon_seeded(session)
    sazon_info = sazon_meta(session) if sazon_seeded else {}

    return render(
        request,
        "dashboard.html",
        {
            "revenue_gs": revenue_gs,
            "portions": portions,
            "unique_customers": unique_customers,
            "repeat_customers": repeat,
            "repeat_pct": (int(repeat / unique_customers * 100) if unique_customers > 0 else 0),
            "food_cost_pct": round(food_cost_pct, 1) if food_cost_pct is not None else None,
            "gross_margin_pct": round(gross_margin_pct, 1)
            if gross_margin_pct is not None
            else None,
            "waste_gs": waste_total_gs,
            "waste_pct": round(waste_pct, 1),
            "recipe_count": len(recipe_count),
            "recipes_cooked": recipes_cooked,
            "avg_order_gs": int(avg_order),
            "by_channel": dict(by_channel),
            "top_recipe_name": top_recipe[0],
            "top_recipe_revenue_gs": top_recipe[1],
            "month_label": month_start.strftime("%B %Y"),
            "tx_count_this_month": len(sales_this_month),
            "sl_open_count": sl_open_count,
            "sl_total_gs": sl_total_gs,
            "wishlist_count": wishlist_count,
            "wishlist_total_gs": wishlist_total_gs,
            "risk_count": risk_count,
            "risk_severity_gs": risk_severity_gs,
            "sazon_seeded": sazon_seeded,
            "sazon_tenant_name": sazon_info.get("sazon_tenant_name", ""),
            "sazon_admin_user": sazon_info.get("sazon_admin_user", ""),
            "sazon_seeded_at": sazon_info.get("sazon_seeded_at", ""),
        },
    )


# ──────────────────────────────────────────────────────────────────
# Production Planner — recipe × batches → ingredient need
# ──────────────────────────────────────────────────────────────────


@planner_router.get("", response_class=HTMLResponse)
def planner_form(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    """Production planner form. Empty on GET."""
    recipes = session.execute(select(Recipe).order_by(Recipe.name)).scalars().all()
    return render(
        request,
        "planner.html",
        {
            "recipes": recipes,
            "results": None,
        },
    )


@planner_router.post("/compute")
def planner_compute(
    request: Request,
    recipe_id: int = Form(...),
    batches: int = Form(...),
    session: Session = Depends(get_session),
) -> object:
    """Compute ingredient needs vs current stock for the given recipe × batches.

    Output: list of {ingredient_name, qty_needed, qty_available, shortage,
    unit, line_unit_price_gs, total_shortage_gs}.
    """
    recipe = session.get(Recipe, recipe_id)
    if not recipe or batches <= 0:
        return RedirectResponse(url="/produccion-planner", status_code=303)

    lines = (
        session.execute(
            select(RecipeLine).where(
                RecipeLine.recipe_id == recipe_id,
                RecipeLine.line_kind == "ingredient",
            )
        )
        .scalars()
        .all()
    )

    # Build ingredient lookup
    ing_ids = [ln.line_ref_id for ln in lines]
    ings = {
        i.id: i
        for i in session.execute(select(Ingredient).where(Ingredient.id.in_(ing_ids)))
        .scalars()
        .all()
    }

    results = []
    total_shortage_gs = 0

    for line in lines:
        ing = ings.get(line.line_ref_id)
        if not ing:
            continue
        # Both `line.qty` and `ing.stock_qty` are Float columns, but SQLAlchemy
        # can return Decimal when the underlying dialect says so (e.g., SQLite
        # NUMERIC type affinity, or when a custom TypeDecorator wraps the
        # column). Cast to float explicitly so the arithmetic is type-safe
        # regardless of which dialect is active.
        qty_needed = float(line.qty or 0) * batches
        qty_available = float(ing.stock_qty or 0)
        shortage = max(0, qty_needed - qty_available)
        unit_price = ing.purchase_price_gs or 0
        total_shortage_gs += shortage * (unit_price / 1.0)  # todo: unit normalization
        results.append(
            {
                "ingredient_id": ing.id,
                "ingredient_name": ing.name,
                "unit": line.line_unit or ing.unit,
                "qty_needed": qty_needed,
                "qty_available": qty_available,
                "shortage": shortage,
                "unit_price_gs": int(unit_price),
                "line_shortage_gs": int(shortage * unit_price),
                "sufficient": shortage <= 0,
            }
        )

    # Optionally save as ProductionPlan + ShoppingListItem rows so that
    # the user can build a real buy list directly from this view.
    plan_id = None
    if results and total_shortage_gs > 0:
        # Persist the plan so shopping list link can find it later
        plan = ProductionPlan(
            recipe_id=recipe_id,
            batches_qty=batches,
            planned_at=datetime.now(timezone.utc),
            notes="Created from /produccion-planner form",
        )
        session.add(plan)
        session.flush()
        plan_id = plan.id

        # Materialize the shortfalls into the shopping list
        for r in results:
            if r["shortage"] > 0:
                item = ShoppingListItem(
                    ingredient_id=r["ingredient_id"],
                    production_plan_id=plan_id,
                    qty_to_buy=r["shortage"],
                    unit=r["unit"],
                    purpose_text=f"Plan #{plan_id} ({batches}× {recipe.name})",
                )
                session.add(item)
        session.commit()
        # Converge with the other flows (plan→list, auto-sync): merge
        # duplicate open items so the list shows one row per ingredient.
        from app.routers.shopping import consolidate_open_items

        consolidate_open_items(session)

    return render(
        request,
        "planner.html",
        {
            "recipes": session.execute(select(Recipe).order_by(Recipe.name)).scalars().all(),
            "results": results,
            "recipe": recipe,
            "batches": batches,
            "total_shortage_gs": int(total_shortage_gs),
            "plan_id": plan_id,
        },
    )


# ──────────────────────────────────────────────────────────────────
# Delivery Zones
# ──────────────────────────────────────────────────────────────────


@delivery_router.get("", response_class=RedirectResponse)
def delivery_zones_list() -> RedirectResponse:
    """Wave 4: redirect /delivery-zones to /settings#zonas-delivery.

    The zones config moved to Settings → "Zonas de delivery" so all
    config lives in one place. This redirect keeps backward-compat for
    bookmarks and the nav link.
    """
    return RedirectResponse(url="/settings#zonas-delivery", status_code=303)


@delivery_router.get("/api", response_class=JSONResponse)
def delivery_zones_api(
    q: str = Query("", description="Search"),
    session: Session = Depends(get_session),
) -> JSONResponse:
    """Search delivery zones for the pedidos form picker."""
    stmt = select(DeliveryZone).where(DeliveryZone.is_active.is_(True))
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(DeliveryZone.coverage_text.ilike(like) | DeliveryZone.name.ilike(like))
    zones = session.execute(stmt.order_by(DeliveryZone.position)).scalars().all()
    payload = [
        {
            "id": z.id,
            "name": z.name,
            "code": z.code,
            "coverage_text": z.coverage_text or "",
            "delivery_cost_gs": z.delivery_cost_gs,
            "min_order_gs": z.min_order_gs,
            "delivery_minutes": z.delivery_minutes,
            "display": f"{z.name} — ₲{z.delivery_cost_gs:,} + mín ₲{z.min_order_gs:,}",
        }
        for z in zones
    ]
    return JSONResponse({"results": payload, "count": len(payload)})


__all__ = [
    "bank_router",
    "benchmarks_router",
    "dashboard_router",
    "delivery_router",
    "planner_router",
    "pricing_router",
    "risks_router",
    "wishlist_router",
]
