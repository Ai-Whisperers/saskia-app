"""app/routers/reorder.py — operator reorder suggestions.

GET /reorder                — HTML view
GET /reorder?format=json    — machine-readable for future /scripts integrations
POST /reorder/generate-po   — bulk generate purchase order as WhatsApp text
"""

from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import current_user_id
from app.auth import require_login_or_disabled as require_login
from app.rms.audit import record as audit_record
from app.rms.dependencies import get_session
from app.rms.models import Ingredient, IngredientPriceEvent, Supplier
from app.rms.price_history import (
    batch_cheapest_supplier,
    batch_price_stats,
    record_price_event,
)
from app.rms.rate_limit import is_write_rate_limited
from app.rms.reorder import compute_reorder_list
from app.rms.reorder_supplier_prices import get_supplier_price_options
from app.rms.supplier_history import (
    LOCK_THRESHOLD,
    get_effective_supplier_id,
    lock_supplier,
    record_purchase_supplier,
    unlock_supplier,
)
from app.services.template_render import render

router = APIRouter(prefix="/reorder", dependencies=[Depends(require_login)])


@router.get("", response_class=HTMLResponse, response_model=None)
def reorder_view(
    request: Request,
    format: str = Query("html", pattern="^(html|json)$"),
    session: Session = Depends(get_session),
) -> HTMLResponse | JSONResponse:
    """Show ingredients that need reordering.

    HTML mode: ranked table grouped by urgency.
    JSON mode: structured payload for tooling.
    """
    items = compute_reorder_list(session)
    # INV-03: exclude items without a price from the footer total. Their
    # estimated_cost_gs is already 0 (set in compute_reorder_list), so the
    # sum remains correct, but we keep this comment for clarity.
    total_cost = sum(i.estimated_cost_gs for i in items)

    # Build ingredient_id -> (supplier_name, supplier_phone) map for WhatsApp links.
    # Migration 072 (P2 reorder redesign): the dropdown now defaults to
    # `effective_supplier_id` (locked > last_purchase > parent supplier_id),
    # so the supplier phone/name lookup should mirror that priority.
    supplier_map: dict[int, tuple[str | None, str]] = {}
    effective_supplier_map: dict[int, int | None] = {}
    locked_supplier_map: dict[int, int | None] = {}
    for item in items:
        ing = session.get(Ingredient, item.ingredient_id)
        if ing is None:
            supplier_map[item.ingredient_id] = (None, "")
            effective_supplier_map[item.ingredient_id] = None
            locked_supplier_map[item.ingredient_id] = None
            continue
        eff_id = get_effective_supplier_id(ing)
        effective_supplier_map[item.ingredient_id] = eff_id
        locked_supplier_map[item.ingredient_id] = ing.locked_supplier_id
        # Pick the supplier object to show name + phone from
        eff_supplier = session.get(Supplier, eff_id) if eff_id is not None else None
        if eff_supplier is not None:
            supplier_map[item.ingredient_id] = (eff_supplier.name, eff_supplier.phone or "")
        elif ing.supplier is not None:
            # Fallback to the legacy parent supplier even though it's not
            # the effective one — better than showing "sin proveedor".
            supplier_map[item.ingredient_id] = (ing.supplier.name, ing.supplier.phone or "")
        else:
            supplier_map[item.ingredient_id] = (None, "")

    # Per-supplier price options for every active supplier (used to render
    # the inline prices in the dropdown). One query per ingredient — N+1
    # is acceptable here because N is bounded by the number of ingredients
    # below minimum (typically <30). If this becomes a bottleneck, batch
    # the lookup in a single SQL query.
    supplier_prices_map: dict[int, dict[int, int | None]] = {}
    for item in items:
        supplier_prices_map[item.ingredient_id] = get_supplier_price_options(
            session, item.ingredient_id
        )

    # All active suppliers, ordered by name ASC. The template iterates
    # this list once to render every dropdown identically.
    all_suppliers = session.scalars(
        select(Supplier).where(Supplier.is_active).order_by(Supplier.name)
    ).all()
    supplier_options = [{"id": s.id, "name": s.name, "phone": s.phone or ""} for s in all_suppliers]

    # Price-history stats per ingredient (used for the sparkline on /reorder).
    # Single SQL query covers all items; 90-day window.
    ingredient_ids = [i.ingredient_id for i in items]
    price_stats = batch_price_stats(session, ingredient_ids, days=90)

    # Cheapest supplier per ingredient (Q4 multi-supplier hint). Same query
    # shape as price_stats — one round-trip for the whole reorder view.
    cheapest_suppliers = batch_cheapest_supplier(session, ingredient_ids, days=90)

    # Predictive forecast (BACKLOG #7): avg_daily consumption + days_of_stock.
    # Single batched query for all items (no N+1).
    from app.rms.forecast import batch_forecast_ingredients

    forecast_objs = batch_forecast_ingredients(session, ingredient_ids, days_back=30)
    forecast_map: dict[int, dict] = {
        ing_id: {
            "avg_daily": fc.avg_daily_consumption,
            "days_of_stock": fc.days_of_stock,
            "trend_pct": fc.trend_pct,
            "projected_stockout_at": fc.projected_stockout_at,
            "recommended_restock_qty": fc.recommended_restock_qty,
        }
        for ing_id, fc in forecast_objs.items()
    }

    # Poisson weekday forecast (SASKIA-208 / BACKLOG #5): P95 stockout date
    # + weekend-uplift per ingredient. Replaces the flat average's blind
    # spot (Saturday-heavy demand runs out days earlier than the mean
    # suggests). Only the at-risk set is computed; the template shows the
    # P95 date next to the flat projection when they disagree.
    from app.rms.restock_forecast import forecast_restock_batch

    restock_map: dict[int, dict] = {
        ing_id: {
            "p95_stockout_date": fc.p95_stockout_date,
            "days_to_p95": fc.days_to_p95_stockout,
            "recommended_qty": fc.recommended_restock_qty,
            "weekend_uplift_pct": fc.weekend_uplift_pct,
            "confidence": fc.confidence,
        }
        for ing_id, fc in forecast_restock_batch(
            session, ingredient_ids, only_at_risk=False
        ).items()
    }

    if format == "json":
        return JSONResponse(
            {
                "items": [
                    {
                        "ingredient_id": i.ingredient_id,
                        "name": i.name,
                        "unit": i.unit,
                        "current_stock": i.current_stock,
                        "min_stock": i.min_stock,
                        "max_stock": i.max_stock,
                        "suggested_qty": i.suggested_qty,
                        "estimated_cost_gs": i.estimated_cost_gs,
                        "purchase_price_gs": i.purchase_price_gs,
                        "urgency": i.urgency,
                        "supplier_name": supplier_map.get(i.ingredient_id, (None, ""))[0],
                        "supplier_phone": supplier_map.get(i.ingredient_id, ("", ""))[1],
                        "effective_supplier_id": effective_supplier_map.get(i.ingredient_id),
                        "locked_supplier_id": locked_supplier_map.get(i.ingredient_id),
                    }
                    for i in items
                ],
                "supplier_options": supplier_options,
                "total_estimated_cost_gs": total_cost,
                "count": len(items),
                "lock_threshold": LOCK_THRESHOLD,  # analytics-only; locks are now manual
            }
        )

    return render(
        request,
        "reorder.html",
        {
            "items": items,
            "total_cost_gs": total_cost,
            "count": len(items),
            "supplier_map": supplier_map,
            "effective_supplier_map": effective_supplier_map,
            "locked_supplier_map": locked_supplier_map,
            "supplier_prices_map": supplier_prices_map,
            "supplier_options": supplier_options,
            "lock_threshold": LOCK_THRESHOLD,
            "price_stats": price_stats,
            "cheapest_suppliers": cheapest_suppliers,
            "forecast_map": forecast_map,
            "restock_map": restock_map,
            "page_start": 1,
            "page_end": len(items),
        },
    )


@router.post("/quick-restock")
def reorder_quick_restock(
    request: Request,
    ingredient_id: int = Form(...),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """One-tap 'I bought it' — fill ingredient to 2x minimum with a single click.

    P40 (2026-10-07, Ivan): the previous /reorder page required operators
    to fill qty + price + supplier on every row. With 60+ rows, the
    'Marcar comprado' button was rarely used (0 records in 30 days).
    This endpoint closes the gap: bumps stock to 2x min_stock_qty (or
    max_stock_qty when set) using the effective supplier's last price.
    No form fields, no confirmation — just a click and the row's
    'Sin stock' / 'Bajo minimo' pill flips to 'OK'.

    Idempotent: if the ingredient is already at 2x min, no price event
    is written. Always audits + increments the supplier streak.
    """
    if is_write_rate_limited(session, request):
        raise HTTPException(
            status_code=429,
            detail="Demasiadas acciones en 1 minuto. Espera un momento.",
        )

    ing = session.get(Ingredient, ingredient_id)
    if ing is None:
        raise HTTPException(status_code=404, detail="Ingrediente no encontrado")

    target = float(ing.max_stock_qty or ing.min_stock_qty * 2)
    if target <= 0:
        raise HTTPException(
            status_code=400,
            detail=f"Sin minimo configurado para {ing.name} — usa /reorder/registrar",
        )

    delta = max(0.0, target - float(ing.stock_qty or 0))

    eff_supplier_id = get_effective_supplier_id(ing)
    last_price_gs: int = 0
    if eff_supplier_id is not None:
        from app.rms.models import IngredientPriceEvent

        last_evt = session.scalar(
            select(IngredientPriceEvent)
            .where(
                IngredientPriceEvent.ingredient_id == ingredient_id,
                IngredientPriceEvent.supplier_id == eff_supplier_id,
            )
            .order_by(IngredientPriceEvent.recorded_at.desc())
            .limit(1)
        )
        if last_evt is not None:
            last_price_gs = int(last_evt.price_gs or 0)

    if delta > 0:
        ing.stock_qty = target
        record_price_event(
            session,
            ingredient_id,
            last_price_gs,
            source="restock",
            supplier_id=eff_supplier_id,
        )
    if eff_supplier_id is not None:
        record_purchase_supplier(session, ingredient_id, eff_supplier_id)

    audit_record(
        session,
        user_id=current_user_id(request) or "operator",
        action="write.reorder.quick_restock",
        request=request,
        detail={
            "ingredient_id": ingredient_id,
            "delta": delta,
            "target": target,
            "previous_stock": float(ing.stock_qty or 0) - delta,
            "supplier_id": eff_supplier_id,
            "price_gs": last_price_gs,
        },
    )
    session.commit()
    return RedirectResponse(url="/reorder", status_code=303)


@router.post("/bulk-quick-restock")
def reorder_bulk_quick_restock(
    request: Request,
    ingredient_ids: str = Form(""),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """P40: bulk version of /reorder/quick-restock for the operator
    who just got back from the supplier and wants to mark 10+ rows
    as purchased in one click. ingredient_ids is a comma-separated
    list. Empty input is a no-op (button should be disabled anyway).
    """
    if is_write_rate_limited(session, request):
        raise HTTPException(
            status_code=429,
            detail="Demasiadas acciones en 1 minuto. Espera un momento.",
        )

    if not ingredient_ids.strip():
        return RedirectResponse(url="/reorder", status_code=303)

    updated = 0
    skipped = 0
    for raw_id in ingredient_ids.split(","):
        raw_id = raw_id.strip()
        if not raw_id:
            continue
        try:
            iid = int(raw_id)
        except ValueError:
            continue
        ing = session.get(Ingredient, iid)
        if ing is None:
            continue
        target = float(ing.max_stock_qty or ing.min_stock_qty * 2)
        if target <= 0:
            skipped += 1
            continue
        delta = max(0.0, target - float(ing.stock_qty or 0))
        eff_supplier_id = get_effective_supplier_id(ing)
        last_price_gs: int = 0
        if eff_supplier_id is not None:
            from app.rms.models import IngredientPriceEvent

            last_evt = session.scalar(
                select(IngredientPriceEvent)
                .where(
                    IngredientPriceEvent.ingredient_id == iid,
                    IngredientPriceEvent.supplier_id == eff_supplier_id,
                )
                .order_by(IngredientPriceEvent.recorded_at.desc())
                .limit(1)
            )
            if last_evt is not None:
                last_price_gs = int(last_evt.price_gs or 0)
        if delta > 0:
            ing.stock_qty = target
            record_price_event(
                session,
                iid,
                last_price_gs,
                source="restock",
                supplier_id=eff_supplier_id,
            )
            updated += 1
        if eff_supplier_id is not None:
            record_purchase_supplier(session, iid, eff_supplier_id)
    audit_record(
        session,
        user_id=current_user_id(request) or "operator",
        action="write.reorder.bulk_quick_restock",
        request=request,
        detail={"updated": updated, "skipped": skipped, "ids": ingredient_ids[:500]},
    )
    session.commit()
    return RedirectResponse(url="/reorder", status_code=303)


@router.post("/registrar")
def reorder_registrar(
    request: Request,
    ingredient_id: int = Form(...),
    qty: float = Form(...),
    qty_unit: str = Form(""),
    price_gs: int = Form(...),
    notes: str = Form(""),
    supplier_id: int | None = Form(None),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Record a purchase: bump stock, append a 'restock' price event.

    Phase D — Q1 surface. the operator: cada vez que restockea carga los
    precios, así los paneles muestran cuánto gana realmente aunque los
    precios fluctúen.

    MER-01 (cross-cutting): qty_unit lets the operator enter the buy in
    any unit from the same family as the ingredient's stock unit (e.g.
    5000 g instead of 5 kg). Cross-family conversion raises a 400.

    Migration 072 (P2 reorder redesign): ``supplier_id`` is optional
    but tracked when provided. When supplied, ``record_purchase_supplier``
    updates the streak counter and may auto-lock the dropdown on the
    next visit to /reorder (after 3 consecutive buys from the same
    supplier). When omitted, we leave the existing last-purchase pointer
    intact (operator skipped the dropdown — e.g. used the keyboard
    shortcut to submit without picking one).
    """
    if is_write_rate_limited(session, request):
        raise HTTPException(
            status_code=429,
            detail="Demasiadas acciones en 1 minuto. Esperá un momento.",
        )

    if qty <= 0:
        raise HTTPException(status_code=400, detail="La cantidad debe ser mayor a 0")
    if price_gs < 0:
        raise HTTPException(status_code=400, detail="El precio no puede ser negativo")

    ing = session.get(Ingredient, ingredient_id)
    if ing is None:
        raise HTTPException(status_code=404, detail="Ingrediente no encontrado")

    # Validate the supplier_id FK when supplied so a malformed POST can't
    # silently write garbage into the streak/lock columns.
    chosen_supplier_id: int | None = None
    if supplier_id is not None:
        sup = session.get(Supplier, supplier_id)
        if sup is None:
            raise HTTPException(status_code=400, detail="Proveedor inválido")
        chosen_supplier_id = sup.id

    # Convert qty from the form unit to the ingredient's stock unit so
    # "5000 g" on the form lands as +5.00 kg on the ingredient.
    from app.rms.units import Unit, can_convert, convert_qty

    qty_in_stock_unit = qty
    if qty_unit and ing.unit and qty_unit != ing.unit:
        from_unit = Unit.coerce(qty_unit)
        to_unit = Unit.coerce(ing.unit)
        if not can_convert(from_unit, to_unit):
            raise HTTPException(
                status_code=400,
                detail=f"No se puede convertir {qty_unit} a {ing.unit} (familia distinta)",
            )
        qty_in_stock_unit = float(convert_qty(qty, from_unit, to_unit))

    ing.stock_qty = ing.stock_qty + qty_in_stock_unit
    record_price_event(
        session,
        ingredient_id,
        price_gs,
        source="restock",
        supplier_id=chosen_supplier_id,
    )
    if chosen_supplier_id is not None:
        record_purchase_supplier(session, ingredient_id, chosen_supplier_id)
    audit_record(
        session,
        user_id=current_user_id(request) or "operator",
        action="write.reorder.restock",
        request=request,
        detail={
            "ingredient_id": ingredient_id,
            "qty": qty_in_stock_unit,
            "qty_unit": qty_unit or ing.unit,
            "price_gs": price_gs,
            "supplier_id": chosen_supplier_id,
            "notes": notes or None,
        },
    )
    session.commit()
    return RedirectResponse(url="/reorder", status_code=303)


@router.post("/scrape")
def reorder_scrape(
    request: Request,
    q: str = Form(...),
    session: Session = Depends(get_session),
) -> JSONResponse:
    """Scrape public supermarket sites for the latest prices of ``q``.

    Returns a list of :class:`ScrapedPrice` per source so the /reorder UI
    can show a "Latest prices" dropdown next to the supplier picker. If
    a source can't be scraped (e.g. Stock needs JS), it's reported with
    an ``error`` instead of crashing.

    Audit row written (action=read.scraper.run) so the operator can see
    how often this is actually used.
    """
    from app.integrations.scrapers import scrape_all

    results = scrape_all(q.strip())
    payload = {
        "ok": True,
        "query": q.strip(),
        "sources": [
            {
                "source": r.source,
                "ok": r.ok,
                "error": r.error,
                "matches": [
                    {
                        "name": m.product_name,
                        "price_gs": m.price_gs,
                        "unit": m.unit,
                        "url": m.url,
                    }
                    for m in r.matches
                ],
            }
            for r in results
        ],
    }
    try:
        audit_record(
            session,
            user_id=current_user_id(request) or "operator",
            action="read.scraper.run",
            target_type="reorder",
            target_id="scraper",
            detail={
                "query": q.strip(),
                "sources": [r.source for r in results],
                "match_count": sum(len(r.matches) for r in results),
            },
        )
        session.commit()
    except Exception:
        session.rollback()  # don't fail the scrape over an audit miss
    return JSONResponse(payload)


@router.post("/lock-supplier")
def reorder_lock_supplier(
    request: Request,
    ingredient_id: int = Form(...),
    supplier_id: int = Form(...),
    reason: str = Form(""),
    session: Session = Depends(get_session),
) -> JSONResponse:
    """Manually pin an ingredient to a supplier (🔒 button on /reorder).

    Audit row written server-side via ``lock_supplier()``. Returns
    ``{"ok": true, "ingredient_id": ..., "supplier_id": ...}`` so the
    frontend can refresh. On error returns 4xx with ``{"ok": false,
    "error": "..."}``.
    """
    if is_write_rate_limited(session, request):
        raise HTTPException(
            status_code=429,
            detail="Demasiadas acciones en 1 minuto. Esperá un momento.",
        )

    ing = session.get(Ingredient, ingredient_id)
    if ing is None:
        raise HTTPException(status_code=404, detail="Ingrediente no encontrado")

    sup = session.get(Supplier, supplier_id)
    if sup is None:
        raise HTTPException(status_code=400, detail="Proveedor inválido")
    if not sup.is_active:
        raise HTTPException(
            status_code=400,
            detail=f"El proveedor '{sup.name}' está inactivo. Reactiválo en /settings/catalog antes de fijar.",
        )

    actor = str(current_user_id(request) or "operator")
    lock_supplier(
        session,
        ingredient_id=ingredient_id,
        supplier_id=sup.id,
        actor=actor,
        reason=reason,
    )
    session.commit()
    return JSONResponse({"ok": True, "ingredient_id": ingredient_id, "supplier_id": sup.id})


@router.post("/unlock-supplier")
def reorder_unlock_supplier(
    request: Request,
    ingredient_id: int = Form(...),
    reason: str = Form(""),
    session: Session = Depends(get_session),
) -> JSONResponse:
    """Clear the manual lock on an ingredient (🔓 button on /reorder).

    Audit row written server-side via ``unlock_supplier()``. Returns
    ``{"ok": true, "ingredient_id": ...}`` on success. No-op (still 200)
    if there was no lock.
    """
    if is_write_rate_limited(session, request):
        raise HTTPException(
            status_code=429,
            detail="Demasiadas acciones en 1 minuto. Esperá un momento.",
        )

    ing = session.get(Ingredient, ingredient_id)
    if ing is None:
        raise HTTPException(status_code=404, detail="Ingrediente no encontrado")

    actor = str(current_user_id(request) or "operator")
    unlock_supplier(
        session,
        ingredient_id=ingredient_id,
        actor=actor,
        reason=reason,
    )
    session.commit()
    return JSONResponse({"ok": True, "ingredient_id": ingredient_id})


@router.post("/upload-prices")
async def reorder_upload_prices(
    request: Request,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> JSONResponse:
    """Bulk-load supplier price rows from a CSV file.

    Migration 073 made IngredientPriceEvent carry a supplier_id so the
    /reorder dropdown can show per-supplier prices. This endpoint is
    the bulk path: paste a spreadsheet (or upload one) and the rows
    fill in.

    CSV format (UTF-8, comma-separated, with header row):

        ingredient_name,supplier_name,price_gs,date
        harina,Stock PY,4200,2026-10-01
        harina,Casa Rica,4500,2026-10-01
        azúcar,Stock PY,3500,2026-10-01
        ...

    Validation rules:
      - ingredient_name must resolve to an active ingredient (case-insensitive
        match on ``ingredient.name``)
      - supplier_name must resolve to an ACTIVE supplier
        (soft-deleted suppliers are skipped with an error in the response)
      - price_gs must be a positive integer (no decimals; matches the
        Gs. money rule)
      - date must be YYYY-MM-DD; defaults to today when blank. Future dates
        are accepted (she might be quoting upcoming prices) but warn.
      - duplicate (ingredient, supplier, date) tuples are skipped (one
        restock per supplier per day per ingredient makes sense).

    Response shape (always 200, even on per-row errors — caller renders
    a preview to the operator before committing):

        {
          "ok": true,
          "imported": 12,        // rows successfully written
          "skipped": 3,          // duplicates + future-date warnings
          "errors": [
            {"row": 5, "ingredient_name": "xxx", "error": "ingredient not found"}
          ],
          "preview": [
            {"ingredient": "harina", "supplier": "Stock PY", "price_gs": 4200, "date": "2026-10-01"}
          ]
        }
    """
    if is_write_rate_limited(session, request):
        raise HTTPException(
            status_code=429,
            detail="Demasiadas acciones en 1 minuto. Esperá un momento.",
        )

    # Read file body. Reject anything bigger than 2MB — a CSV with
    # thousands of rows is overkill for /reorder; this is meant for a
    # one-time spreadsheet paste.
    from app.rms.upload_limits import CSV_LIMIT_2MB, CSV_MIME_TYPES, validate_upload

    validate_upload(file, allowed_types=CSV_MIME_TYPES, max_size=CSV_LIMIT_2MB)
    raw = await file.read()
    try:
        text = raw.decode("utf-8-sig")  # tolerate BOM
    except UnicodeDecodeError:
        try:
            text = raw.decode("latin-1")
        except UnicodeDecodeError:
            raise HTTPException(
                status_code=400,
                detail="No se pudo decodificar el CSV. Usá UTF-8.",
            ) from None

    import csv
    import io
    from datetime import datetime as _datetime
    from datetime import timezone

    reader = csv.DictReader(io.StringIO(text))
    required = {"ingredient_name", "supplier_name", "price_gs"}
    if reader.fieldnames is None or not required.issubset(set(reader.fieldnames)):
        raise HTTPException(
            status_code=400,
            detail=(
                "Faltan columnas. Necesarias: "
                + ", ".join(sorted(required))
                + f". Encontradas: {reader.fieldnames}"
            ),
        )

    # Pre-load lookup maps so we issue one query per dimension instead
    # of one per row (cheap, but the test seed has 76 ingredients × 8
    # suppliers × 90 days = 54k possible rows; we'd be there all day).
    ingredients_by_name: dict[str, Ingredient] = {
        i.name.lower(): i for i in (session.execute(select(Ingredient)).scalars().all())
    }
    suppliers_by_name: dict[str, Supplier] = {
        s.name.lower(): s
        for s in (session.execute(select(Supplier).where(Supplier.is_active)).scalars().all())
    }

    today = _datetime.now(timezone.utc).date()
    imported = 0
    skipped = 0
    errors: list[dict] = []
    preview: list[dict] = []

    for row_idx, row in enumerate(reader, start=2):  # start=2 (header is row 1)
        ing_name = (row.get("ingredient_name") or "").strip()
        sup_name = (row.get("supplier_name") or "").strip()
        price_raw = (row.get("price_gs") or "").strip()
        date_raw = (row.get("date") or "").strip()

        if not ing_name or not sup_name:
            errors.append({"row": row_idx, "error": "ingredient_name o supplier_name vacío"})
            continue
        try:
            price_int = int(price_raw)
        except (ValueError, TypeError):
            errors.append(
                {
                    "row": row_idx,
                    "ingredient_name": ing_name,
                    "supplier_name": sup_name,
                    "error": f"price_gs inválido: {price_raw!r}",
                }
            )
            continue
        if price_int <= 0:
            errors.append(
                {
                    "row": row_idx,
                    "ingredient_name": ing_name,
                    "supplier_name": sup_name,
                    "error": "price_gs debe ser > 0",
                }
            )
            continue

        ing = ingredients_by_name.get(ing_name.lower())
        if ing is None:
            errors.append(
                {"row": row_idx, "ingredient_name": ing_name, "error": "ingrediente no encontrado"}
            )
            continue
        sup = suppliers_by_name.get(sup_name.lower())
        if sup is None:
            errors.append(
                {
                    "row": row_idx,
                    "supplier_name": sup_name,
                    "error": "proveedor no encontrado (o inactivo)",
                }
            )
            continue

        # Date parsing
        if date_raw:
            try:
                when = _datetime.strptime(date_raw, "%Y-%m-%d").date()  # noqa: DTZ007
            except ValueError:
                errors.append(
                    {
                        "row": row_idx,
                        "ingredient_name": ing_name,
                        "error": f"date inválido: {date_raw!r} (usá YYYY-MM-DD)",
                    }
                )
                continue
        else:
            when = today

        # Skip future-dated rows but warn
        if when > today:
            skipped += 1
            preview.append(
                {
                    "ingredient": ing.name,
                    "supplier": sup.name,
                    "price_gs": price_int,
                    "date": when.isoformat(),
                    "warning": "fecha futura — no se importó",
                }
            )
            continue

        # Dedup: one (ingredient, supplier, date) per restock makes sense
        existing = (
            session.execute(
                select(IngredientPriceEvent).where(
                    IngredientPriceEvent.ingredient_id == ing.id,
                    IngredientPriceEvent.supplier_id == sup.id,
                    IngredientPriceEvent.recorded_at
                    >= _datetime.combine(when, _datetime.min.time()),
                    IngredientPriceEvent.recorded_at
                    < _datetime.combine(when, _datetime.max.time()),
                )
            )
            .scalars()
            .first()
        )
        if existing is not None:
            skipped += 1
            preview.append(
                {
                    "ingredient": ing.name,
                    "supplier": sup.name,
                    "price_gs": price_int,
                    "date": when.isoformat(),
                    "warning": "duplicado — ya hay un evento para esta fecha",
                }
            )
            continue

        record_price_event(
            session,
            ingredient_id=ing.id,
            price_gs=price_int,
            source="csv_upload",
            at=_datetime.combine(when, _datetime.min.time()).replace(tzinfo=None),
            supplier_id=sup.id,
        )
        imported += 1
        preview.append(
            {
                "ingredient": ing.name,
                "supplier": sup.name,
                "price_gs": price_int,
                "date": when.isoformat(),
            }
        )

    audit_record(
        session,
        user_id=current_user_id(request) or "operator",
        action="write.reorder.csv_upload",
        request=request,
        detail={
            "imported": imported,
            "skipped": skipped,
            "errors": len(errors),
            "filename": getattr(file, "filename", None),
        },
    )
    session.commit()

    return JSONResponse(
        {
            "ok": True,
            "imported": imported,
            "skipped": skipped,
            "errors": errors[:50],  # cap error list
            "preview": preview[:50],
        }
    )


@router.post("/generate-po")
def reorder_generate_po(
    request: Request,
    selected: str = Form("", description="Comma-separated ingredient IDs"),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Generate a WhatsApp purchase order pre-fill link for selected ingredients.

    Redirects to a WhatsApp wa.me URL with the order text pre-filled.
    """
    if not selected:
        return RedirectResponse(url="/reorder", status_code=303)

    try:
        ids = [int(x.strip()) for x in selected.split(",") if x.strip()]
    except ValueError:
        return RedirectResponse(url="/reorder", status_code=303)

    items = compute_reorder_list(session)
    selected_items = [i for i in items if i.ingredient_id in ids]

    if not selected_items:
        return RedirectResponse(url="/reorder", status_code=303)

    # Group by supplier
    by_supplier: dict[str, list] = {}
    no_supplier: list = []
    for item in selected_items:
        ing = session.get(Ingredient, item.ingredient_id)
        supplier_name = ing.supplier.name if (ing and ing.supplier) else None
        if supplier_name:
            by_supplier.setdefault(supplier_name, []).append(item)
        else:
            no_supplier.append(item)

    # Build WhatsApp text
    lines = ["*Pedido de materiales*", ""]
    for supplier_name, sup_items in by_supplier.items():
        lines.append(f"📦 *{supplier_name}*")
        lines.extend(f"  • {item.name}: {item.suggested_qty:.2f} {item.unit}" for item in sup_items)
        lines.append("")
    if no_supplier:
        lines.append("📦 *Sin proveedor asignado*")
        lines.extend(
            f"  • {item.name}: {item.suggested_qty:.2f} {item.unit}" for item in no_supplier
        )
        lines.append("")

    text = "\n".join(lines).strip()
    # Encode for WhatsApp URL
    encoded = quote(text, safe="")
    wa_url = f"https://wa.me/?text={encoded}"

    audit_record(
        session,
        user_id=current_user_id(request) or "operator",
        action="write.reorder.generate_po",
        request=request,
        detail={"n_items": len(selected_items), "suppliers": list(by_supplier.keys())},
    )
    session.commit()

    return RedirectResponse(url=wa_url, status_code=303)


__all__ = ["router"]
