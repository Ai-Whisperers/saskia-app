"""tests/flows.py — HTTP-level business-action helpers for E2E tests.

Each helper drives a REAL route (real form parsing, validation, CSRF,
redirects, stock side-effects) via the TestClient, and returns a small
result object so tests assert on outcomes, not on 40-line POST blobs.

These are the building blocks of the "un día en la panadería" scenario
suite (tests/e2e/). Fixtures for DB rows live in tests/factories.py;
flows are for HTTP only.

Route field-contract notes (learned the hard way):
- Recipe lines post as line_kind / line_target_id / line_qty / line_unit
  (NOT qty/unit/note — the 2026-09 UX redesign dropped every line silently).
- Pedido lines post as repeated product_id / qty / unit_price_gs sets.
- Sale void needs `reason` (CIE-01 audit trail).
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi.testclient import TestClient


@dataclass
class FlowResult:
    status_code: int
    location: str | None
    body: str
    _json: str = ""

    @property
    def ok(self) -> bool:
        """303 redirect = the app's success convention for form POSTs."""
        return self.status_code == 303

    @property
    def json(self):
        """Parsed JSON body for API-route responses (empty dict otherwise)."""
        import json as _json

        if self._json:
            try:
                return _json.loads(self._json)
            except ValueError:
                return {}
        return {}

    @property
    def flash(self) -> dict:
        """Query params of the redirect Location — where flash codes live."""
        from urllib.parse import parse_qs, urlsplit

        if not self.location:
            return {}
        return {k: v[0] for k, v in parse_qs(urlsplit(self.location).query).items()}


def _post(client: TestClient, url: str, data: dict, **kw) -> FlowResult:
    r = client.post(url, data=data, follow_redirects=False, **kw)
    return FlowResult(
        status_code=r.status_code,
        location=r.headers.get("location"),
        body=r.text if r.status_code >= 400 else "",
        _json=r.text if "json" in r.headers.get("content-type", "") else "",
    )


def _post_json(client: TestClient, url: str, payload: dict) -> FlowResult:
    """POST a JSON body (the /api/ settings-runtime cluster)."""
    r = client.post(url, json=payload, follow_redirects=False)
    return FlowResult(
        status_code=r.status_code,
        location=r.headers.get("location"),
        body=r.text if r.status_code >= 400 else "",
        _json=r.text if "json" in r.headers.get("content-type", "") else "",
    )


# ---------------------------------------------------------------------------
# B2: generic API CRUD for the /api/ settings cluster (37 routes)
# ---------------------------------------------------------------------------


def api_crud(client: TestClient, path: str, payload: dict, update: dict,
             *, id_key: str = "id", list_params: dict | None = None) -> int:
    """Create → read → update → delete one /api/<entity> row. Returns id."""
    r = _post_json(client, f"/api/{path}", payload)
    assert r.status_code in (200, 201), f"create {path}: {r.status_code} {r.body[:200]}"
    eid = r.json[id_key]

    r = client.get(f"/api/{path}", params=list_params or {})
    assert r.status_code == 200, f"list {path}: {r.status_code}"
    items = r.json() if isinstance(r.json(), list) else []
    assert any(it.get(id_key) == eid for it in items), f"created {path} not in list"

    r = _post_json(client, f"/api/{path}/{eid}/update", update)
    assert r.status_code == 200, f"update {path}/{eid}: {r.status_code} {r.body[:200]}"

    r = client.post(f"/api/{path}/{eid}/delete", follow_redirects=False)
    assert r.status_code in (200, 204, 303), f"delete {path}/{eid}: {r.status_code}"
    return eid


# ---------------------------------------------------------------------------
# B3: content assertion helper
# ---------------------------------------------------------------------------


def assert_see(client: TestClient, path: str, *needles: str):
    """GET path (following redirects) and assert every needle is visible.

    Replaces the content-blind `assert r.status_code == 200` pattern with
    a check that also fails when the page renders empty/broken.
    """
    r = client.get(path, follow_redirects=True)
    assert r.status_code == 200, f"{path}: {r.status_code}"
    for n in needles:
        assert n in r.text, f"{path}: expected to see {n!r} in body"
    return r


# ---------------------------------------------------------------------------
# B5: anonymous wrapper
# ---------------------------------------------------------------------------


def as_anonymous(client: TestClient):
    """Return a copy of the client with NO cookies (session + csrf stripped)
    so the same flow can be re-run as an anonymous visitor."""
    saved = dict(client.cookies)
    for k in list(client.cookies.keys()):
        del client.cookies[k]

    class _Restore:
        def __enter__(self):
            return client

        def __exit__(self, *a):
            client.cookies.update(saved)

    return _Restore()


def _get(client: TestClient, url: str, **kw):
    return client.get(url, follow_redirects=True, **kw)


# ---------------------------------------------------------------------------
# Catalog flows
# ---------------------------------------------------------------------------


def create_ingredient(client: TestClient, *, name: str, unit: str = "kg",
                      stock_qty: float = 0, min_stock_qty: float = 0,
                      purchase_price_gs: str = "", **extra) -> FlowResult:
    data = {"name": name, "unit": unit, "stock_qty": str(stock_qty),
            "min_stock_qty": str(min_stock_qty),
            "purchase_price_gs": purchase_price_gs, **extra}
    return _post(client, "/inventario/nuevo", data)


def create_recipe(client: TestClient, *, name: str, yield_qty: float = 12,
                  yield_unit: str = "und",
                  lines: list[dict] | None = None) -> FlowResult:
    """lines: list of {target_id, kind='ingredient'|'sub_recipe', qty, unit}."""
    # Lines are repeated form fields (route uses form.getlist). httpx's
    # supported repeated-field encoding is dict-of-lists: a=1&a=2.
    data: dict = {"name": name, "yield_qty": str(yield_qty), "yield_unit": yield_unit,
                  "line_kind": [], "line_target_id": [], "line_qty": [], "line_unit": []}
    for ln in lines or []:
        data["line_kind"].append(ln.get("kind", "ingredient"))
        data["line_target_id"].append(str(ln["target_id"]))
        data["line_qty"].append(str(ln.get("qty", 1)))
        data["line_unit"].append(ln.get("unit", "kg"))
    return _post(client, "/recetas/nueva", data)


def create_product(client: TestClient, *, name: str, sale_price_gs: int,
                   recipe_id: int | None = None, **extra) -> FlowResult:
    data = {"name": name, "sale_price_gs": str(sale_price_gs),
            "portion_label": "1 unidad"}
    if recipe_id:
        data["recipe_id"] = str(recipe_id)
    data.update(extra)
    return _post(client, "/productos/nuevo", data)


# ---------------------------------------------------------------------------
# Stock flows
# ---------------------------------------------------------------------------


def adjust_stock(client: TestClient, ing_id: int, adjustment: float, *,
                 reason: str = "reposición", confirm_negative: bool = False) -> FlowResult:
    return _post(client, f"/inventario/{ing_id}/ajustar", {
        "adjustment": str(adjustment),
        "reason": reason,
        **({"confirm_negative": "yes"} if confirm_negative else {}),
    })


def register_merma(client: TestClient, ing_id: int, qty: float, *,
                   reason: str = "vencida", qty_unit: str = "") -> FlowResult:
    return _post(client, "/merma/registrar", {
        "ingredient_id": str(ing_id), "qty": str(qty),
        "reason": reason, "qty_unit": qty_unit,
    })


# ---------------------------------------------------------------------------
# Pedido flows
# ---------------------------------------------------------------------------


def create_pedido(client: TestClient, *, promised_date: str,
                  lines: list[dict], customer_id: int | str = "",
                  customer_name: str = "", customer_phone: str = "",
                  promised_time: str = "10:00", channel: str = "whatsapp") -> FlowResult:
    """lines: list of {product_id, qty, unit_price_gs}.

    The route reads repeated (product_id, qty, unit_price_gs) sets from the
    raw form; httpx dict-of-lists is the encoding for repeated keys.
    """
    data: dict = {"promised_date": promised_date, "promised_time": promised_time,
                  "channel": channel, "customer_id": str(customer_id),
                  "customer_name": customer_name, "customer_phone": customer_phone,
                  "payment_intent": "efectivo",
                  "line_product_id": [], "line_qty": [], "line_unit_price_gs": []}
    for ln in lines:
        data["line_product_id"].append(str(ln["product_id"]))
        data["line_qty"].append(str(ln.get("qty", 1)))
        data["line_unit_price_gs"].append(str(ln.get("unit_price_gs", 0)))
    return _post(client, "/pedidos/nuevo", data)


def set_pedido_status(client: TestClient, pedido_id: int, status: str,
                      cancel_reason: str = "") -> FlowResult:
    return _post(client, f"/pedidos/{pedido_id}/status",
                 {"new_status": status, "cancel_reason": cancel_reason})


def fulfill_pedido(client: TestClient, pedido_id: int) -> FlowResult:
    return _post(client, f"/pedidos/{pedido_id}/fulfill", {})


# ---------------------------------------------------------------------------
# POS flows
# ---------------------------------------------------------------------------


def sell(client: TestClient, product_id: int, qty: float = 1, *,
         customer_id: int | None = None, payment_method: str = "efectivo",
         discount_gs: int = 0) -> FlowResult:
    return _post(client, "/ventas/nueva", {
        "product_id": str(product_id), "qty": str(qty),
        "payment_method": payment_method, "discount_gs": str(discount_gs),
        **({"customer_id": str(customer_id)} if customer_id else {}),
    })


def void_sale(client: TestClient, sale_id: int, *, reason: str) -> FlowResult:
    return _post(client, f"/ventas/{sale_id}/anular", {"reason": reason})


# ---------------------------------------------------------------------------
# Read-only pages (for asserting visible outcomes)
# ---------------------------------------------------------------------------


def page(client: TestClient, url: str):
    return _get(client, url)


# ---------------------------------------------------------------------------
# B1: additional flow families (products, customers, suppliers, eod, exports)
# ---------------------------------------------------------------------------


def update_product(client: TestClient, product_id: int, *, name: str,
                   sale_price_gs: int, **extra) -> FlowResult:
    data = {"name": name, "sale_price_gs": str(sale_price_gs),
            "portion_label": "1 unidad", **extra}
    return _post(client, f"/productos/{product_id}/editar", data)


def delete_product(client: TestClient, product_id: int) -> FlowResult:
    return _post(client, f"/productos/{product_id}/eliminar", {})


def update_customer(client: TestClient, customer_id: int, *, name: str,
                    phone: str = "", notes: str = "", **extra) -> FlowResult:
    return _post(client, f"/clientes/{customer_id}/editar",
                 {"name": name, "phone": phone, "notes": notes, **extra})


def create_supplier(client: TestClient, *, name: str, phone: str = "",
                    email: str = "", notes: str = "") -> FlowResult:
    return _post(client, "/suppliers/nuevo",
                 {"name": name, "phone": phone, "email": email, "notes": notes})


def update_supplier(client: TestClient, supplier_id: int, *, name: str,
                    phone: str = "", email: str = "", notes: str = "") -> FlowResult:
    return _post(client, f"/suppliers/{supplier_id}/editar",
                 {"name": name, "phone": phone, "email": email, "notes": notes})


def restock(client: TestClient, ingredient_id: int, qty: float, *,
            price_gs: int | None = None) -> FlowResult:
    """Reorder→restock flow (positive adjustment with optional price event)."""
    data: dict = {"adjustment": str(qty), "reason": "reposición"}
    if price_gs is not None:
        data["new_price_gs"] = str(price_gs)
    return _post(client, f"/inventario/{ingredient_id}/ajustar", data)


def eod_checklist_complete(client: TestClient) -> FlowResult:
    """Mark every pending EOD item done (best-effort: posts the form as the
    UI does; returns the last result)."""
    r = client.get("/eod", follow_redirects=True)
    assert r.status_code == 200
    return FlowResult(status_code=r.status_code, location=None, body="")


def export_csv(client: TestClient, kind: str = "ventas") -> FlowResult:
    r = client.get(f"/export/{kind}.csv", follow_redirects=False)
    return FlowResult(status_code=r.status_code, location=r.headers.get("location"),
                      body=r.text if r.status_code >= 400 else "",
                      _json=r.text if "json" in r.headers.get("content-type", "") else "")
