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

    @property
    def ok(self) -> bool:
        """303 redirect = the app's success convention for form POSTs."""
        return self.status_code == 303

    @property
    def flash_in_body(self) -> str:
        return self.body


def _post(client: TestClient, url: str, data: dict, **kw) -> FlowResult:
    r = client.post(url, data=data, follow_redirects=False, **kw)
    return FlowResult(
        status_code=r.status_code,
        location=r.headers.get("location"),
        body=r.text if r.status_code >= 400 else "",
    )


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
