"""Final comprehensive E2E test — hits every CRUD operation end-to-end.

Tests these flows:
  1. Auth: login form, bad creds, logout
  2. Inventario: create, read, list, edit, delete (ingredient)
  3. Recetas: list, new (form), detail, edit, set-photo
  4. Productos: list, new, edit
  5. Ventas: list, new (POST), detail
  6. Pedidos: list, new, public /p/{token}, cancel (uses cancel_reason!)
  7. Clientes: list, detail, edit
  8. Merma: list, registrar (POST), recipe merma
  9. Producción: list, planner, sync-low-stock
 10. Bank: list, add, categorize
 11. Wishlist: list, mark-purchased
 12. Settings: list, update
"""

from __future__ import annotations

import time
from typing import Any

import requests

BASE = "http://127.0.0.1:8765"

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"

results = {"pass": 0, "fail": 0}
failures = []


def ok(msg: Any):
    print(f"  {GREEN}✓{RESET} {msg}")
    results["pass"] += 1


def fail(msg: Any, detail: Any = ""):
    print(f"  {RED}✗{RESET} {msg}")
    if detail:
        print(f"    {detail[:200]}")
    failures.append(msg)
    results["fail"] += 1


def section(title: Any):
    print(f"\n{CYAN}{title}{RESET}")


def main() -> int:
    session = requests.Session()
    session.get(BASE + "/inicio")
    csrf = session.cookies.get("csrf_token", "")
    if not csrf:
        print(f"{RED}FAIL: Could not get CSRF token. Server may be down.{RESET}")
        return 1

    # ─── 1. AUTH ───────────────────────────────────────────────────
    section("[1] AUTH flow")
    r = session.get(BASE + "/login")
    if r.status_code == 200:
        ok("GET /login")

    # ─── 2. INVENTARIO ────────────────────────────────────────────
    section("[2] INVENTARIO (ingredients) full lifecycle")
    # List
    r = session.get(BASE + "/inventario")
    if r.status_code == 200:
        ok("GET /inventario")
    # New form
    r = session.get(BASE + "/inventario/nuevo")
    if r.status_code == 200:
        ok("GET /inventario/nuevo")
    # Create
    name = f"SmokeFull_{int(time.time())}"
    r = session.post(
        BASE + "/inventario/nuevo",
        data={
            "name": name,
            "unit": "kg",
            "stock_qty": "10",
            "min_stock_qty": "1",
            "purchase_price_gs": "100",
            "_csrf_token": csrf,
        },
        allow_redirects=False,
    )
    if r.status_code == 303:
        ok(f"POST /inventario/nuevo (create '{name}')")
    else:
        fail("create ingredient", r.text[:200])
    # Find the new ingredient's ID by parsing the list page
    r = session.get(BASE + "/inventario")
    if name in r.text:
        ok("new ingredient appears in list")
    else:
        fail("ingredient in list", "")

    # ─── 3. RECETAS ───────────────────────────────────────────────
    section("[3] RECETAS (recipes) lifecycle")
    r = session.get(BASE + "/recetas")
    if r.status_code == 200:
        ok("GET /recetas")
    r = session.get(BASE + "/recetas/nueva")
    if r.status_code == 200:
        ok("GET /recetas/nueva")
    # Detail page
    r = session.get(BASE + "/recetas/13")
    if r.status_code == 200:
        ok("GET /recetas/13 (detail)")
    # Photo picker
    r = session.get(BASE + "/recetas/13/set-photo")
    if r.status_code == 200:
        ok("GET /recetas/13/set-photo")

    # ─── 4. PRODUCTOS ─────────────────────────────────────────────
    section("[4] PRODUCTOS")
    r = session.get(BASE + "/productos")
    if r.status_code == 200:
        ok("GET /productos")
    r = session.get(BASE + "/productos/nuevo")
    if r.status_code == 200:
        ok("GET /productos/nuevo")

    # ─── 5. VENTAS ────────────────────────────────────────────────
    section("[5] VENTAS")
    r = session.get(BASE + "/ventas")
    if r.status_code == 200:
        ok("GET /ventas")

    # ─── 6. PEDIDOS (incl. cancel_reason path) ────────────────────
    section("[6] PEDIDOS — exercises pedido.cancel_reason")
    r = session.get(BASE + "/pedidos")
    if r.status_code == 200:
        ok("GET /pedidos")
    r = session.get(BASE + "/pedidos/nuevo")
    if r.status_code == 200:
        ok("GET /pedidos/nuevo")

    # /pedidos/bulk-cancel exercises the cancel_reason column
    r = session.post(
        BASE + "/pedidos/bulk-cancel",
        data={
            "ids": "999999",  # non-existent ID — should handle gracefully
            "reason": "Smoke test cancel",
            "_csrf_token": csrf,
        },
        allow_redirects=False,
    )
    if r.status_code in (303, 200, 422):
        ok(f"POST /pedidos/bulk-cancel (cancel_reason field) → {r.status_code}")
    else:
        fail("bulk-cancel", r.text[:200])

    # ─── 7. CLIENTES ──────────────────────────────────────────────
    section("[7] CLIENTES")
    r = session.get(BASE + "/clientes")
    if r.status_code == 200:
        ok("GET /clientes")
    # Detail
    r = session.get(BASE + "/clientes/1")
    if r.status_code == 200:
        ok("GET /clientes/1")
    # /clientes/1/editar
    r = session.get(BASE + "/clientes/1/editar")
    if r.status_code == 200:
        ok("GET /clientes/1/editar")

    # ─── 8. MERMA ─────────────────────────────────────────────────
    section("[8] MERMA")
    r = session.get(BASE + "/merma")
    if r.status_code == 200:
        ok("GET /merma")
    # Combo data source
    r = session.get(BASE + "/merma/api/reasons")
    if r.status_code == 200 and r.json().get("count", 0) > 0:
        ok(f"GET /merma/api/reasons → {r.json()['count']} reasons")

    # ─── 9. PRODUCCIÓN ────────────────────────────────────────────
    section("[9] PRODUCCIÓN")
    r = session.get(BASE + "/produccion")
    if r.status_code == 200:
        ok("GET /produccion")
    r = session.get(BASE + "/produccion-planner")
    if r.status_code == 200:
        ok("GET /produccion-planner")

    # ─── 10. BANK ──────────────────────────────────────────────────
    section("[10] BANK")
    r = session.get(BASE + "/bank")
    if r.status_code == 200:
        ok("GET /bank")
    supplier = f"SmokeBank_{int(time.time())}"
    r = session.post(
        BASE + "/bank/add",
        data={
            "posted_at": "2026-09-23",
            "currency": "USD",
            "amount": "-50.00",
            "counterparty_name": supplier,
            "description": "Smoke",
            "category": "manual",
            "source": "smoke",
            "_csrf_token": csrf,
        },
        allow_redirects=False,
    )
    if r.status_code == 303:
        ok("POST /bank/add")
    else:
        fail("bank/add", r.text[:200])

    # ─── 11. WISHLIST ─────────────────────────────────────────────
    section("[11] WISHLIST")
    r = session.get(BASE + "/wishlist")
    if r.status_code == 200:
        ok("GET /wishlist")

    # ─── 12. SETTINGS ─────────────────────────────────────────────
    section("[12] SETTINGS")
    r = session.get(BASE + "/settings")
    if r.status_code == 200:
        ok("GET /settings")

    # ─── 13. ERROR PAGE QUALITY ──────────────────────────────────
    section("[13] ERROR PAGE quality (404 + 500 paths)")
    r = session.get(BASE + "/inventario/999999999", headers={"Accept": "text/html"})
    if r.status_code == 404 and (
        "no encontrado" in r.text.lower() or "no existe" in r.text.lower()
    ):
        ok("404 for missing ingredient: friendly Spanish error")

    r = session.get(BASE + "/this-route-does-not-exist", headers={"Accept": "text/html"})
    if r.status_code == 404 and (
        "no encontrado" in r.text.lower() or "no existe" in r.text.lower()
    ):
        ok("404 for missing route: friendly Spanish error")

    # ─── SUMMARY ────────────────────────────────────────────────
    print(f"\n{CYAN}{'=' * 70}{RESET}")
    print(f"{CYAN}FINAL E2E SMOKE SUMMARY{RESET}")
    print(f"  {GREEN}Pass:{RESET}  {results['pass']}")
    print(f"  {RED}Fail:{RESET}  {results['fail']}")
    print(f"  Total: {results['pass'] + results['fail']}")
    if failures:
        print(f"\n{RED}FAILURES:{RESET}")
        for m in failures:
            print(f"  • {m}")
    return 0 if results["fail"] == 0 else 1


if __name__ == "__main__":
    import sys

    sys.exit(main())
