"""app/routers/customers.py — /clientes (Customer directory + loyalty).

Built on top of app/rms/customers.py which has all the helpers:
- list_customers()
- get_customer()
- customer_stats()
- customer_purchase_history()
- tier_for_spend()
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Form, HTTPException, Path, Query, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.responses import RedirectResponse as StarletteRedirectResponse

logger = logging.getLogger(__name__)

from app.auth import require_login_or_disabled as require_login
from app.rms.customers import (
    batch_customer_stats,
    customer_purchase_history,
    customer_stats,
    list_customers,
    search_customers,
)
from app.rms.dependencies import get_session
from app.rms.models import Customer
from app.rms.observability import record_audit
from app.rms.nav import status_es
from app.services.template_render import render

router = APIRouter(prefix="/clientes", dependencies=[Depends(require_login)])

# P3 profile batch: closed vocabularies for the profile form
ALLOWED_HOW_FOUND = frozenset({
    "instagram", "whatsapp", "recomendacion", "local", "otro",
})
ALLOWED_CHANNELS = frozenset({
    "whatsapp", "llamada", "instagram", "presencial",
})


PAGE_SIZE = 50


@router.get("", response_class=HTMLResponse)
def clientes_list(
    request: Request,
    q: str | None = None,
    tier: str | None = None,
    sort: str | None = Query(
        None, description="Sort column: name, phone, n_sales, lifetime_spend_gs, points, tier"
    ),
    dir: str | None = Query("asc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Customer directory with loyalty tiers + points + filters."""
    import csv
    import io

    from starlette.responses import StreamingResponse

    from app.rms.models import CustomerAddress

    q = q or ""
    f"%{q.lower()}%"

    if tier:
        # Tier filter requires post-hoc filtering (stats needed per customer).
        customers = list_customers(session)
        if q:
            ql = q.lower()
            customers = [
                c
                for c in customers
                if (c.name and ql in c.name.lower()) or (c.phone and ql in c.phone)
            ]
        rows = []
        all_stats = batch_customer_stats(session, customers)
        for c in customers:
            stats = all_stats.get(c.id)
            if stats is None:
                continue
            if stats.tier.value == tier:
                rows.append(
                    {
                        "id": c.id,
                        "name": c.name or "(sin nombre)",
                        "phone": c.phone,
                        "lifetime_spend_gs": stats.lifetime_spend_gs,
                        "n_sales": stats.n_sales,
                        "last_sale_at": stats.last_sale_at,
                        "tier": stats.tier.value,
                        "tier_label": status_es(stats.tier.value)[0],
                        "tier_sev": status_es(stats.tier.value)[1],
                        "points": c.loyalty_points,
                        "created_at": c.created_at,
                    }
                )
    else:
        # No tier filter — search only.
        if q:
            ql = q.lower()
            customers = [
                c
                for c in list_customers(session)
                if (c.name and ql in c.name.lower()) or (c.phone and ql in c.phone)
            ]
        else:
            customers = list_customers(session)
        # Batch-fetch all stats in one query instead of N queries
        all_stats = batch_customer_stats(session, customers)
        rows = []
        for c in customers:
            stats = all_stats.get(c.id)
            if stats is None:
                continue
            rows.append(
                {
                    "id": c.id,
                    "name": c.name or "(sin nombre)",
                    "phone": c.phone,
                    "lifetime_spend_gs": stats.lifetime_spend_gs,
                    "n_sales": stats.n_sales,
                    "last_sale_at": stats.last_sale_at,
                    "tier": stats.tier.value,
                    "tier_label": status_es(stats.tier.value)[0],
                    "tier_sev": status_es(stats.tier.value)[1],
                    "points": c.loyalty_points,
                    "created_at": c.created_at,
                }
            )

    # Apply sorting
    sort_col = sort or "name"
    reverse = dir == "desc"
    col_map = {
        "name": "name",
        "phone": "phone",
        "n_sales": "n_sales",
        "lifetime_spend_gs": "lifetime_spend_gs",
        "points": "points",
        "tier": "tier",
    }
    col = col_map.get(sort_col, "name")
    if rows and col in rows[0]:
        rows.sort(
            key=lambda r: r.get(col) or "" if isinstance(r.get(col), str) else r.get(col) or 0,
            reverse=reverse,
        )

    # Pagination
    total = len(rows)
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = min(page, total_pages)
    start = (page - 1) * PAGE_SIZE
    end = start + PAGE_SIZE
    page_rows = rows[start:end]

    # P3 profile batch: full customer list for CSV enrichment + nudge.
    all_customers = list_customers(session)

    # --- CSV export (all rows, not just current page) ---
    if request.query_params.get("format") == "csv":
        # P3 profile batch: enrich with contact/profile fields for
        # promo segmentation (consent!) — keyed lookup by id.
        cust_by_id = {c.id: c for c in all_customers}
        export_rows = [
            {
                "id": r["id"],
                "name": r["name"],
                "phone": r["phone"] or "",
                "email": (cust_by_id[r["id"]].email if r["id"] in cust_by_id else "") or "",
                "birthday": (cust_by_id[r["id"]].birthday if r["id"] in cust_by_id else "") or "",
                "how_found": (cust_by_id[r["id"]].how_found if r["id"] in cust_by_id else "") or "",
                "preferred_channel": (cust_by_id[r["id"]].preferred_channel if r["id"] in cust_by_id else "") or "",
                "marketing_consent": "si" if (r["id"] in cust_by_id and cust_by_id[r["id"]].marketing_consent) else "no",
                "dietary_restrictions": (cust_by_id[r["id"]].dietary_restrictions if r["id"] in cust_by_id else "") or "",
                "n_sales": r["n_sales"],
                "lifetime_spend_gs": r["lifetime_spend_gs"],
                "tier": r["tier"],
                "points": r["points"],
                "last_sale_at": r["last_sale_at"].isoformat() if r["last_sale_at"] else "",
                "created_at": r["created_at"].isoformat() if r["created_at"] else "",
            }
            for r in rows
        ]
        buf = io.StringIO()
        w = csv.DictWriter(
            buf,
            fieldnames=[
                "id",
                "name",
                "phone",
                "email",
                "birthday",
                "how_found",
                "preferred_channel",
                "marketing_consent",
                "dietary_restrictions",
                "n_sales",
                "lifetime_spend_gs",
                "tier",
                "points",
                "last_sale_at",
                "created_at",
            ],
        )
        w.writeheader()
        w.writerows(export_rows)
        return StreamingResponse(
            iter([buf.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=clientes.csv"},
        )

    # P3 profile batch: data-completion nudge — counts of clients missing
    # key contact data, so the operator knows whose profile to fill next.
    nudge = {
        "sin_telefono": sum(
            1 for c in all_customers if not (c.phone or "").strip()
        ),
        "sin_dietary": sum(
            1 for c in all_customers if not (c.dietary_restrictions or "").strip()
        ),
        "sin_direccion": sum(
            1 for c in all_customers
            if not session.scalar(
                select(CustomerAddress.id).where(
                    CustomerAddress.customer_id == c.id
                ).limit(1)
            )
        ),
        "sin_consent": sum(
            1 for c in all_customers if not c.marketing_consent
        ),
    }
    return render(
        request,
        "clientes.html",
        {
            "customers": page_rows,
            "nudge": nudge,
            "q": q or "",
            "tier": tier or "",
            "tiers": ["bronze", "silver", "gold", "platinum"],
            "sort": sort or "",
            "dir": dir or "asc",
            "page": page,
            "total_pages": total_pages,
            "total": total,
            "page_start": (page - 1) * 50 + 1,
            "page_end": min(page * 50, total),
        },
    )


def customer_to_api_payload(c: Customer, session: Session) -> dict:
    """Serialize a Customer row + computed stats for the picker UI.

    For a single customer (N=1) — calls customer_stats() which makes 1 query.
    For lists use batch_customer_stats() instead.

    Returns the picker-friendly shape (compact stats, no top_products).
    For the full /clientes/api/{id} payload (notes, last_sale_at, top_products)
    use _customer_detail_payload() instead.
    """
    stats = customer_stats(session, c)
    lifetime_label = _format_gs_compact(stats.lifetime_spend_gs)
    return {
        "id": c.id,
        "name": c.name or "",
        "phone": c.phone or "",
        "email": c.email or "",
        "cedula": c.cedula or "",
        "notes": c.notes or "",
        "loyalty_points": c.loyalty_points,
        "n_sales": stats.n_sales,
        "lifetime_spend_gs": stats.lifetime_spend_gs,
        "lifetime_label": lifetime_label,
        "tier": stats.tier.value,
        "hint": f"{c.name} — {stats.n_sales} visitas, {lifetime_label} lifetime",
    }


def _customer_detail_payload(c: Customer, session: Session) -> dict:
    """Full payload for /clientes/api/{id} and /clientes/api/create response.

    Includes the same fields as the search/picker payload PLUS:
      - last_sale_at (ISO timestamp from latest Sale.sold_at, or null)
      - top_products: top 3 products the customer buys most often
        ([{name, count}]) — counted across non-voided sales

    Uses batch_customer_stats() to keep the stats query consistent with the
    search/list endpoints. One extra query walks Sale rows for top_products.
    """
    stats_map = batch_customer_stats(session, [c])
    stats = stats_map.get(c.id)
    if stats is None:
        # Shouldn't happen — batch_customer_stats() always fills in a BRONZE
        # row even when the customer has zero sales — but defend anyway.
        from app.rms.customers import customer_stats as _per_cust

        stats = _per_cust(session, c)
    lifetime_label = _format_gs_compact(stats.lifetime_spend_gs)
    top_products = _top_products_for_customer(session, c.id, limit=3)
    last_sale_at_iso = stats.last_sale_at.isoformat() if stats.last_sale_at else None
    return {
        "id": c.id,
        "name": c.name or "",
        "phone": c.phone or "",
        "email": c.email or "",
        "cedula": c.cedula or "",
        "notes": c.notes or "",
        "loyalty_points": c.loyalty_points,
        "n_sales": stats.n_sales,
        "lifetime_spend_gs": stats.lifetime_spend_gs,
        "lifetime_label": lifetime_label,
        "tier": stats.tier.value,
        "last_sale_at": last_sale_at_iso,
        "top_products": top_products,
        "hint": f"{c.name} — {stats.n_sales} visitas, {lifetime_label} lifetime",
    }


def _top_products_for_customer(session: Session, customer_id: int, limit: int = 3) -> list[dict]:
    """Return the customer's top-N products by total qty across non-voided sales.

    [{name: str, count: int|float}] — `count` is total units purchased.

    One query (group by product, sum qty, order by sum desc). Used by the
    customer info card on /ventas to show what they typically buy.
    """
    from app.rms.models import Product, Sale

    rows = session.execute(
        select(
            Product.name.label("name"),
            func.coalesce(func.sum(Sale.qty), 0).label("count"),
        )
        .join(Sale, Sale.product_id == Product.id)
        .where(Sale.customer_id == customer_id, Sale.voided_at.is_(None))
        .group_by(Product.name)
        .order_by(func.coalesce(func.sum(Sale.qty), 0).desc())
        .limit(limit)
    ).all()
    return [{"name": r.name, "count": int(r.count or 0)} for r in rows]


def _format_gs_compact(value: int) -> str:
    """Format an integer Gs. amount in compact human-friendly form.

    1_500_000 → 'Gs. 1.5M', 250_000 → 'Gs. 250k', 0 → 'Gs. 0'.
    """
    if value >= 1_000_000:
        return f"Gs. {value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"Gs. {value // 1_000}k"
    return f"Gs. {value}"


@router.get("/duplicados", response_class=HTMLResponse)
def clientes_duplicados(
    request: Request,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Surface likely-duplicate customers by phone prefix / exact name match.

    Renders a Jinja page with groups. Each group is one canonical
    candidate + its likely duplicates. The operator picks which row
    is the canonical (target) and submits the merge form to
    POST /clientes/{target_id}/merge with source_ids=<csv of dupes>.

    IMPORTANT: registered BEFORE the `/clientes/{customer_id}` dynamic
    route — otherwise Starlette matches the literal `duplicados` against
    `customer_id` and blows up trying to coerce "duplicados" to int.
    """
    from sqlalchemy import and_, literal_column, or_

    # Self-join: c1.id < c2.id guarantees each pair appears once.
    # Phone prefix match is the strongest signal in this codebase —
    # phone is the de-facto unique identifier at the counter.
    # Exact name match on >3 chars catches spelling-duplicate typos.
    pairs = session.execute(
        select(
            Customer.id.label("id1"),
            Customer.name.label("name1"),
            Customer.phone.label("phone1"),
            literal_column("c2.id").label("id2"),
            literal_column("c2.name").label("name2"),
            literal_column("c2.phone").label("phone2"),
        )
        .select_from(Customer)
        .join(
            Customer.__table__.alias("c2"),
            Customer.id < literal_column("c2.id"),
        )
        .where(
            or_(
                and_(
                    Customer.phone.is_not(None),
                    Customer.phone != "",
                    literal_column("c2.phone").is_not(None),
                    literal_column("c2.phone") != "",
                    func.substr(Customer.phone, 1, 5)
                    == func.substr(literal_column("c2.phone"), 1, 5),
                ),
                and_(
                    func.length(Customer.name) > 3,
                    Customer.name == literal_column("c2.name"),
                ),
            )
        )
    ).all()

    # Group pairs by canonical-id heuristic: smallest id wins within
    # a connected component. Simpler: build adjacency, then union-find.
    parent: dict[int, int] = {}

    def find(x: int) -> int:
        while parent.get(x, x) != x:
            parent[x] = parent.get(parent[x], parent[x])
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            if ra < rb:
                parent[rb] = ra
            else:
                parent[ra] = rb

    for r in pairs:
        union(int(r.id1), int(r.id2))

    # Collect groups.
    members: dict[int, set[int]] = {}
    for r in pairs:
        root = find(int(r.id1))
        members.setdefault(root, set()).update({int(r.id1), int(r.id2)})

    # Load full Customer rows for each group.
    all_ids = {i for ids in members.values() for i in ids}
    if not all_ids:
        return render(
            request,
            "clientes_duplicados.html",
            {"groups": [], "total_groups": 0, "total_dupes": 0},
        )

    customers_rows = session.scalars(
        select(Customer).where(Customer.id.in_(all_ids)).order_by(Customer.id)
    ).all()
    by_id = {c.id: c for c in customers_rows}

    groups: list[dict] = []
    for root in sorted(members.keys()):
        ids = sorted(members[root])
        # Canonical = smallest id (oldest row). The operator can change
        # the choice on the merge form anyway.
        canonical_id = ids[0]
        canonical = by_id.get(canonical_id)
        if canonical is None:
            continue
        dupes = [by_id[i] for i in ids[1:] if i in by_id]
        if not dupes:
            continue
        groups.append(
            {
                "canonical": canonical,
                "duplicates": dupes,
                "duplicate_ids": [d.id for d in dupes],
            }
        )

    return render(
        request,
        "clientes_duplicados.html",
        {
            "groups": groups,
            "total_groups": len(groups),
            "total_dupes": sum(len(g["duplicate_ids"]) for g in groups),
        },
    )


@router.get("/api/search", response_class=JSONResponse)
def customer_search_api(
    q: str = Query("", description="Search query"),
    limit: int = Query(10, ge=1, le=50),
    session: Session = Depends(get_session),
) -> JSONResponse:
    """Search customers by name/phone/email/cedula/notes (case-insensitive).

    Used by the customer picker modal on /ventas.
    """
    rows = search_customers(session, q, limit=limit)
    if not rows:
        return JSONResponse({"results": [], "count": 0})
    all_stats = batch_customer_stats(session, rows)
    payload = []
    for c in rows:
        stats = all_stats.get(c.id)
        if stats is None:
            continue
        lifetime_label = _format_gs_compact(stats.lifetime_spend_gs)
        payload.append(
            {
                "id": c.id,
                "name": c.name or "",
                "phone": c.phone or "",
                "email": c.email or "",
                "cedula": c.cedula or "",
                "notes": c.notes or "",
                "loyalty_points": c.loyalty_points,
                # P3 dietary: picker shows a warning chip + pedido form
                # autofills the alert banner when a restricted customer
                # is picked.
                "dietary_restrictions": [
                    t for t in (c.dietary_restrictions or "").split(",") if t.strip()
                ],
                "dietary_confirm_always": bool(c.dietary_confirm_always),
                "n_sales": stats.n_sales,
                "lifetime_spend_gs": stats.lifetime_spend_gs,
                "lifetime_label": lifetime_label,
                "tier": stats.tier.value,
                "hint": f"{c.name} — {stats.n_sales} visitas, {lifetime_label} lifetime",
            }
        )
    return JSONResponse({"results": payload, "count": len(payload)})


@router.post("/api/create", response_class=JSONResponse)
async def customer_create_api(
    request: Request,
    session: Session = Depends(get_session),
) -> JSONResponse:
    """Create (or update) a customer from form/JSON data.

    Accepts both form-encoded and JSON bodies. Required: name. If a phone
    matches an existing customer, that row is updated (idempotent).

    Returns JSON with the new/existing customer's id + FULL display payload
    (notes, last_sale_at, top_products, stats, tier) — same shape as the
    /clientes/api/{id} GET endpoint so the inline-create flow on /ventas
    can populate the customer info card without a second fetch.
    """
    content_type = (request.headers.get("content-type") or "").lower()
    if "application/json" in content_type:
        body = await request.json()
        data = dict(body) if isinstance(body, dict) else {}
    else:
        form = await request.form()
        data = {k: form.get(k) for k in form.keys()}

    name = (str(data.get("name") or "")).strip()
    if not name:
        raise HTTPException(status_code=422, detail="nombre es obligatorio")

    # Use centralized validation for email/phone/cedula so we don't accept
    # garbage like "nope" as an email or "abc" as a phone.
    from app.rms.validation import (
        optional_text,
        validate_cedula,
        validate_email,
        validate_phone,
    )

    phone = validate_phone(str(data.get("phone") or ""))
    email = validate_email(str(data.get("email") or ""))
    cedula = validate_cedula(str(data.get("cedula") or ""))
    notes = optional_text(str(data.get("notes") or ""), max_len=2000)

    from app.rms.customers import ensure_customer

    # Detect create vs update: if id is already populated after ensure_customer,
    # check whether the row existed before by comparing created_at vs now.
    # Simpler: ensure_customer returns the row. We capture an `existed`
    # flag by snapshotting IDs before, since ensure_customer may create.
    pre_ids = set(session.scalars(select(Customer.id)).all())
    customer = ensure_customer(
        session,
        name=name,
        phone=phone,
        email=email,
        cedula=cedula,
        notes=notes,
    )
    session.commit()
    session.refresh(customer)
    was_created = customer.id not in pre_ids
    if was_created:
        record_audit(
            request,
            session=session,
            action="write.customer.create",
            target_type="customer",
            target_id=customer.id,
            detail={"name": name},
        )
        session.commit()
    return JSONResponse(
        {
            "id": customer.id,
            "created": True,
            "customer": _customer_detail_payload(customer, session),
        }
    )


@router.get("/api/{customer_id}", response_class=JSONResponse)
def customer_detail_api(
    customer_id: int = Path(..., ge=1, description="Customer primary key"),
    session: Session = Depends(get_session),
) -> JSONResponse:
    """Return a single customer's full payload (notes + stats + top_products).

    Used by the inline customer info card on /ventas. 404 if not found.
    500 on DB error (defensive — the picker UI relies on this never crashing).
    """
    try:
        customer = session.get(Customer, customer_id)
        if customer is None:
            return JSONResponse({"error": "not_found"}, status_code=404)
        return JSONResponse(_customer_detail_payload(customer, session))
    except Exception:
        # OPSEC: log only the customer_id, never the name/phone/email.
        logger.exception("customer_detail_api failed for customer_id=%s", customer_id)
        return JSONResponse({"error": "internal_error"}, status_code=500)


@router.get("/{customer_id}", response_class=HTMLResponse)
def cliente_detail(
    request: Request,
    customer_id: int = Path(...),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Single customer: stats + purchase history."""
    from datetime import datetime, timezone

    from app.rms.customers import get_customer

    customer = get_customer(session, customer_id)
    if customer is None:
        return RedirectResponse(url="/clientes", status_code=status.HTTP_303_SEE_OTHER)
    stats = customer_stats(session, customer)
    history = customer_purchase_history(session, customer.id)

    # P0 fix: the template's `s.product_name` never existed on Sale — Jinja
    # Undefined → EVERY row rendered "(eliminado)". decorate_history snapshots
    # the live product name; "(eliminado #id)" if a product ever goes missing.
    from app.rms.customers import decorate_history
    history_view = decorate_history(session, history)

    # Tier badge days-since-last-sale: SQLite returns NAIVE datetimes while
    # now() is aware — subtracting them raises TypeError (500 on
    # /clientes/{id}, ref 9da40358ea00). Normalize both to aware-UTC here
    # so the template only does integer comparison.
    last_sale_at = stats.get("last_sale_at") if isinstance(stats, dict) else getattr(stats, "last_sale_at", None)
    last_days = 999
    if last_sale_at is not None:
        if last_sale_at.tzinfo is None:
            last_sale_at = last_sale_at.replace(tzinfo=timezone.utc)
        last_days = (datetime.now(timezone.utc) - last_sale_at).days

    from app.rms.customer_dietary import load_profile
    profile = load_profile(
        customer.dietary_restrictions,
        customer.dietary_preferences,
        customer.dietary_confirm_always,
    )
    return render(
        request,
        "cliente_detalle.html",
        {
            "customer": customer,
            "stats": stats,
            "history": history,
            "history_view": history_view,
            "dietary_profile": profile,
            "now_iso": datetime.now(timezone.utc).isoformat(),
            "last_days": last_days,
        },
    )


@router.get("/{customer_id}/editar", response_class=HTMLResponse)
def cliente_edit(
    request: Request,
    customer_id: int = Path(...),
    session: Session = Depends(get_session),
) -> object:
    """Edit form for an existing customer."""
    customer = session.get(Customer, customer_id)
    if customer is None:
        return StarletteRedirectResponse(url="/clientes", status_code=303)
    from app.rms.customer_dietary import load_profile
    from app.rms.tagging.vocabulary import CANONICAL_DIETARY_TAGS
    profile = load_profile(
        customer.dietary_restrictions,
        customer.dietary_preferences,
        customer.dietary_confirm_always,
    )
    from app.rms.models import CustomerAddress
    addresses = session.scalars(
        select(CustomerAddress)
        .where(CustomerAddress.customer_id == customer_id)
        .order_by(CustomerAddress.is_default.desc(), CustomerAddress.id)
    ).all()
    from app.rms.models import DeliveryZone
    zones = session.scalars(
        select(DeliveryZone).where(DeliveryZone.is_active.is_(True)).order_by(DeliveryZone.position)
    ).all()
    zone_names = {z.id: z.name for z in zones}
    return render(
        request,
        "cliente_editar.html",
        {
            "customer": customer,
            "dietary_profile": profile,
            "dietary_tag_options": sorted(CANONICAL_DIETARY_TAGS),
            "addresses": addresses,
            "zones": zones,
            "zone_names": zone_names,
            "how_found_options": sorted(ALLOWED_HOW_FOUND),
            "channel_options": sorted(ALLOWED_CHANNELS),
        },
    )


@router.post("/api/{customer_id}/addresses", response_class=JSONResponse)
async def address_create_api(
    customer_id: int,
    request: Request,
    session: Session = Depends(get_session),
) -> JSONResponse:
    """P3 profile: add a delivery address from the client edit form."""
    import json as _json

    from app.rms.models import CustomerAddress

    cust = session.get(Customer, customer_id)
    if cust is None:
        return JSONResponse({"error": "not_found"}, status_code=404)
    try:
        payload = await request.json()
    except ValueError:
        return JSONResponse({"error": "bad_json"}, status_code=400)
    text_val = str(payload.get("address_text", "")).strip()
    if not text_val:
        return JSONResponse({"error": "address_text required"}, status_code=400)
    label = str(payload.get("label", "casa")).strip()[:32] or "casa"
    zone_id = payload.get("zone_id")
    zone_int = int(zone_id) if zone_id else None
    first = not session.scalar(
        select(CustomerAddress.id).where(CustomerAddress.customer_id == customer_id).limit(1)
    )
    addr = CustomerAddress(
        customer_id=customer_id,
        label=label,
        address_text=text_val,
        zone_id=zone_int,
        is_default=first,
    )
    session.add(addr)
    session.commit()
    record_audit(
        request,
        session=session,
        action="write.customer.update",
        target_type="customer",
        target_id=customer_id,
        detail={"address_added": label},
    )
    session.commit()
    return JSONResponse({"id": addr.id, "label": addr.label,
                         "address_text": addr.address_text,
                         "zone_id": addr.zone_id, "is_default": addr.is_default})


@router.delete("/api/{customer_id}/addresses/{address_id}", response_class=JSONResponse)
def address_delete_api(
    customer_id: int,
    address_id: int,
    request: Request,
    session: Session = Depends(get_session),
) -> JSONResponse:
    """P3 profile: remove a delivery address from the client edit form."""
    from app.rms.models import CustomerAddress

    addr = session.get(CustomerAddress, address_id)
    if addr is None or addr.customer_id != customer_id:
        return JSONResponse({"error": "not_found"}, status_code=404)
    session.delete(addr)
    session.commit()
    record_audit(
        request,
        session=session,
        action="write.customer.update",
        target_type="customer",
        target_id=customer_id,
        detail={"address_removed": addr.label},
    )
    session.commit()
    return JSONResponse({"ok": True})



@router.post("/{customer_id}/editar")
def cliente_update(
    request: Request,
    customer_id: int = Path(...),
    name: str = Form(""),
    phone: str = Form(""),
    email: str = Form(""),
    cedula: str = Form(""),
    notes: str = Form(""),
    # P3 dietary: repeated dietary_restriction checkboxes + preference rows
    dietary_restriction: list[str] = Form([]),
    dietary_prefs_payload: str = Form(""),  # JSON [{tag, rank, note}]
    dietary_confirm_always: str = Form(""),
    # P3 profile batch
    birthday: str = Form(""),
    how_found: str = Form(""),
    preferred_channel: str = Form(""),
    marketing_consent: str = Form(""),
    invoice_name: str = Form(""),
    invoice_ruc: str = Form(""),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Update an existing customer's fields."""
    from app.rms.validation import (
        optional_text,
        require_text,
        validate_cedula,
        validate_email,
        validate_phone,
    )

    customer = session.get(Customer, customer_id)
    if customer is None:
        return RedirectResponse(url="/clientes", status_code=303)
    customer.name = require_text(name, field="nombre", max_len=120)
    customer.phone = validate_phone(phone)
    customer.email = validate_email(email)
    customer.cedula = validate_cedula(cedula)
    customer.notes = optional_text(notes, max_len=2000)

    # P3 dietary profile: restrictions (canonical tags, cleaned), ordered
    # preferences (JSON), confirm-always flag.
    from app.rms.customer_dietary import (
        format_preferences,
        format_restrictions,
        parse_preferences,
    )
    from app.rms.tagging.vocabulary import CANONICAL_DIETARY_TAGS

    clean_restrictions = [
        r.strip() for r in dietary_restriction
        if r.strip() in CANONICAL_DIETARY_TAGS
    ]
    customer.dietary_restrictions = format_restrictions(clean_restrictions) or None
    try:
        prefs = parse_preferences(dietary_prefs_payload)
    except Exception:  # noqa: BLE001 — malformed JSON from a stale tab
        prefs = []
    customer.dietary_preferences = format_preferences(prefs) if prefs else None
    customer.dietary_confirm_always = dietary_confirm_always == "1"

    # P3 profile batch
    from app.rms.validation import optional_choice
    # Birthday: accept DD-MM or DD-MM-AAAA (as hinted in the form) and
    # normalize to MM-DD for the dashboard's month-day comparison.
    import re as _re
    bd = (birthday or "").strip()
    if bd:
        m_bd = _re.match(r"^(\d{1,2})-(\d{1,2})(?:-(\d{4}))?$", bd)
        if not m_bd:
            from fastapi import HTTPException as _HE
            raise _HE(status_code=400, detail="Cumpleaños inválido: usá DD-MM o DD-MM-AAAA")
        dd, mm = int(m_bd.group(1)), int(m_bd.group(2))
        if not (1 <= dd <= 31 and 1 <= mm <= 12):
            from fastapi import HTTPException as _HE
            raise _HE(status_code=400, detail="Cumpleaños inválido: día/mes fuera de rango")
        customer.birthday = f"{mm:02d}-{dd:02d}"
    else:
        customer.birthday = None
    customer.how_found = optional_choice(
        how_found, ALLOWED_HOW_FOUND, field="how_found"
    )
    customer.preferred_channel = optional_choice(
        preferred_channel, ALLOWED_CHANNELS, field="canal preferido"
    )
    customer.marketing_consent = marketing_consent == "1"
    customer.invoice_name = optional_text(invoice_name, max_len=120)
    customer.invoice_ruc = optional_text(invoice_ruc, max_len=20)
    session.commit()
    record_audit(
        request,
        session=session,
        action="write.customer.update",
        target_type="customer",
        target_id=customer_id,
        detail={"name": customer.name},
    )
    session.commit()
    return RedirectResponse(
        url=f"/clientes/{customer_id}?flash=Cliente+actualizado", status_code=303
    )


@router.post("/bulk-eliminar")
def clientes_bulk_delete(
    request: Request,
    ids: str = Form(""),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Delete multiple customers at once. Skips any with sales."""
    deleted = 0
    skipped = 0
    for cid in ids.split(","):
        cid = cid.strip()
        if not cid:
            continue
        try:
            c = session.get(Customer, int(cid))
        except ValueError:
            continue
        if c is None:
            continue
        # Check for sales — use limit(1) for efficiency
        from app.rms.models import Sale

        has_sales = session.scalar(select(Sale.id).where(Sale.customer_id == c.id).limit(1))
        if has_sales is not None:
            skipped += 1
            continue
        # Log deletion before deleting
        record_audit(
            request,
            session=session,
            action="write.customer.delete",
            target_type="customer",
            target_id=c.id,
            detail={"name": c.name, "phone": c.phone},
        )
        session.delete(c)
        deleted += 1

    session.commit()
    flash = f"{deleted} cliente(s) eliminado(s)"
    if skipped:
        flash += f", {skipped} omitido(s) por tener ventas"
    return RedirectResponse(url=f"/clientes?flash={flash}", status_code=303)


@router.post("/{target_id}/merge")
def cliente_merge(
    request: Request,
    target_id: int = Path(..., ge=1),
    source_ids: str = Form(...),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Merge `source_ids` (comma-separated) into `target_id`.

    Domain rules live in `app/rms/customer_merge.customer_merge()`.
    This wrapper handles:
      - Parsing `source_ids` into ints
      - CSRF: the middleware already validated the cookie (cookie-level
        check); form `csrf_token` is also submitted (double-submit).
      - Auth: enforced by the router-level `require_login` dependency.
      - Audit row: `write.customer.merge` with the list of merged ids
        and the totals.
      - Transactional commit / rollback.

    Redirects to /clientes with a flash message. On error (ValueError
    from the domain layer), redirects with an error flash so the
    operator sees what went wrong.
    """
    # Source-id list parsing.
    try:
        source_id_list = [int(s) for s in source_ids.split(",") if s.strip()]
    except ValueError:
        return RedirectResponse(
            url="/clientes/duplicados?flash=IDs+inv%C3%A1lidos",
            status_code=303,
        )
    if not source_id_list:
        return RedirectResponse(
            url="/clientes/duplicados?flash=No+se+seleccionaron+duplicados",
            status_code=303,
        )

    from app.rms.customer_merge import customer_merge as _customer_merge

    try:
        result = _customer_merge(
            session,
            target_id=target_id,
            source_ids=source_id_list,
        )
    except ValueError as e:
        msg = str(e).replace(" ", "+").replace("\n", "+")
        return RedirectResponse(
            url=f"/clientes/duplicados?flash={msg}",
            status_code=303,
        )

    # Audit row — use the same session so the audit + the merge land
    # atomically.
    record_audit(
        request,
        session=session,
        action="write.customer.merge",
        target_type="customer",
        target_id=target_id,
        detail={
            "sources": [
                {"id": s.from_id, "name": s.from_name}
                for s in result.sources_merged
            ],
            "sales_reassigned": sum(s.sales_reassigned for s in result.sources_merged),
            "pedidos_reassigned": sum(s.pedidos_reassigned for s in result.sources_merged),
            "phone_filled_from_source": result.phone_filled_from_source,
            "email_filled_from_source": result.email_filled_from_source,
        },
    )
    session.commit()

    flash = f"Se+fusionaron+{len(result.sources_merged)}+clientes+en+1"
    return RedirectResponse(url=f"/clientes?flash={flash}", status_code=303)
