#!/usr/bin/env python3
"""scripts/shoot_all_pages.py — full-page PNG screenshots of every page.

Boots the real app (seeded via factories) + headless Chromium — same wiring
as tests/browser/helpers.py — then visits every renderable GET route and
saves a full-page screenshot.

Usage:
    uv run python scripts/shoot_all_pages.py [output_dir]

Output: <dir>/*.png + index.html (contact sheet) + summary.json
"""
from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "docs/user-guide/screenshots/all-pages")
CHROME = "/opt/hermes/.playwright/chromium_headless_shell-1243/chrome-headless-shell-linux64/chrome-headless-shell"


def boot_app():
    import os
    import tempfile

    os.environ.setdefault("SASKIA_TEST_AUTH_DISABLED", "1")

    import uvicorn

    from app.rms.db import init_db, make_engine, make_session_factory
    from app.rms.main import app as fastapi_app

    d = tempfile.mkdtemp(prefix="shoot-")
    engine = make_engine(f"sqlite:///{d}/shoot.sqlite")
    init_db(engine)
    sf = make_session_factory(engine)

    # Seed a rich little world so pages show real content
    from datetime import datetime, timedelta, timezone

    from tests.factories import (
        ing_line,
        make_catalog,
        make_customer,
        make_ingredient,
        make_pedido,
        make_product,
        make_recipe,
        make_sale,
    )

    with sf() as s:
        cat = make_catalog(s, price_gs=10_000)
        ing2 = make_ingredient(s, name="Levadura seca", stock_qty=0.4,
                               min_stock_qty=1.0, purchase_price_gs=18_000)
        make_product(s, name="Café con leche", sale_price_gs=7_000)
        make_recipe(s, name="Chipa guazú", lines=[ing_line(ing2, qty=0.05)])
        from tests.factories import pedido_item

        c1 = make_customer(s, name="María López", notes="alergia: gluten")
        make_customer(s, name="Pedro Giménez")
        t0 = datetime.utcnow() - timedelta(days=3)
        sale_ids = []
        for i in range(6):
            sale = make_sale(s, product=cat["product"], qty=2, at=t0 + timedelta(hours=i * 8))
            sale_ids.append(sale.id)
        ped = make_pedido(s, customer=c1,
                          items=[pedido_item(cat["product"])],
                          promised_date=datetime.utcnow().date())
        from app.rms.models import MarketBenchmark

        bench = MarketBenchmark(product_label="Chipa grande", our_retail_gs=5000,
                                comp_min_gs=4500, comp_avg_gs=5500)
        s.add(bench)
        s.commit()
        ids = {"product": cat["product"].id, "ingredient": cat["ingredient"].id,
               "recipe": cat["recipe"].id, "customer": c1.id,
               "sale": sale_ids[-1], "pedido": ped.id, "bench": bench.id}

    from app.rms import db as db_module
    from app.rms import main as main_module

    main_module.make_engine_dialect = lambda *a, **k: engine
    db_module.make_engine_dialect = lambda *a, **k: engine
    fastapi_app.state.engine = engine
    fastapi_app.state.session_factory = sf

    config = uvicorn.Config(fastapi_app, host="127.0.0.1", port=0, log_level="warning")
    server = uvicorn.Server(config)
    threading.Thread(target=server.run, daemon=True).start()
    for _ in range(50):
        if server.started:
            break
        time.sleep(0.1)
    port = server.servers[0].sockets[0].getsockname()[1]
    return f"http://127.0.0.1:{port}", server, engine, ids


def routes_to_shoot(ids):
    """(path, filename) for every renderable page; param routes use seeded ids."""
    return [
        ("/dashboard", "dashboard"),
        ("/analisis", "analisis"),
        ("/", "inicio"),
        ("/ventas", "ventas"),
        ("/ventas/historial", "ventas-historial"),
        ("/pedidos", "pedidos"),
        ("/pedidos/board", "pedidos-board"),
        ("/pedidos/nuevo", "pedidos-nuevo"),
        ("/inventario", "inventario"),
        ("/inventario/nuevo", "inventario-nuevo"),
        (f"/inventario/{ids['ingredient']}", "inventario-detalle"),
        ("/productos", "productos"),
        ("/productos/nuevo", "productos-nuevo"),
        (f"/productos/{ids['product']}/editar", "producto-editar"),
        ("/recetas", "recetas"),
        ("/recetas/nueva", "recetas-nueva"),
        (f"/recetas/{ids['recipe']}", "receta-detalle"),
        (f"/recetas/{ids['recipe']}/editar", "receta-editar"),
        ("/clientes", "clientes"),
        (f"/clientes/{ids['customer']}", "cliente-detalle"),
        (f"/clientes/{ids['customer']}/editar", "cliente-editar"),
        ("/produccion", "produccion"),
        ("/produccion-planner", "produccion-planner"),
        ("/eod", "eod"),
        ("/merma", "merma"),
        ("/reportes", "reportes"),
        ("/reportes/iva", "reportes-iva"),
        ("/reportes/libro-ventas", "reportes-libro-ventas"),
        ("/reportes/diario", "reportes-diario"),
        ("/reportes/comparacion", "reportes-comparacion"),
        ("/reportes/top-productos", "reportes-top-productos"),
        ("/reportes/retencion", "reportes-retencion"),
        ("/reportes/valor-pedido", "reportes-valor-pedido"),
        ("/reportes/ventas-hora", "reportes-ventas-hora"),
        ("/reportes/metodos-pago", "reportes-metodos-pago"),
        ("/reportes/precios", "reportes-precios"),
        ("/reportes/cierre-mensual", "reportes-cierre-mensual"),
        ("/reportes/food-cost-variance", "reportes-food-cost-variance"),
        ("/reportes/demand", "reportes-demand"),
        ("/reportes/freshness", "reportes-freshness"),
        ("/reportes/stock-intel", "reportes-stock-intel"),
        ("/reportes/afinidades", "reportes-afinidades"),
        ("/reportes/margenes", "reportes-margenes"),
        ("/shopping-list", "shopping-list"),
        ("/suppliers", "suppliers"),
        ("/proveedores", "proveedores-alias"),
        ("/wishlist", "wishlist"),
        ("/reorder", "reorder"),
        ("/pricing", "pricing"),
        ("/vs-mercado", "vs-mercado"),
        ("/bank", "bank"),
        ("/delivery-zones", "delivery-zones"),
        ("/auditoria", "auditoria"),
        ("/ops/status", "ops-status"),
        ("/excel", "excel"),
        ("/settings", "settings"),
        ("/settings/catalog", "settings-catalog"),
        ("/users", "users"),
        ("/guia", "guia"),
        ("/riesgos", "riesgos"),
        ("/login", "login"),
        # detail/secondary pages
        ("/ventas/buscar", "ventas-buscar"),
        (f"/ventas/{ids['sale']}/recibo", "venta-recibo"),
        (f"/inventario/{ids['ingredient']}/editar", "inventario-editar"),
        (f"/inventario/{ids['ingredient']}/movimientos", "inventario-movimientos"),
        (f"/inventario/{ids['ingredient']}/variantes", "inventario-variantes"),
        (f"/pedidos/{ids['pedido']}", "pedido-detalle"),
        (f"/pedidos/{ids['pedido']}/stock-preview", "pedido-stock-preview"),
        (f"/pedidos/{ids['pedido']}/duplicate", "pedido-duplicate"),
        (f"/recetas/{ids['recipe']}/crear-producto", "receta-crear-producto"),
        (f"/recetas/{ids['recipe']}/set-photo", "receta-set-photo"),
        ("/suppliers/nuevo", "supplier-nuevo"),
        ("/suppliers/1/editar", "supplier-editar") if False else ("/suppliers", "suppliers-dup"),
        (f"/reportes/margenes/{ids['product']}", "reportes-margenes-detalle"),
        (f"/reportes/price-impact/{ids['ingredient']}?new_price=7000", "reportes-price-impact"),
        (f"/vs-mercado/{ids['bench']}/edit", "vs-mercado-editar"),
        ("/guia/ventas", "guia-seccion"),
    ]


def main():
    from playwright.sync_api import sync_playwright

    OUT.mkdir(parents=True, exist_ok=True)
    base, server, engine, ids = boot_app()

    summary = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=CHROME, args=["--no-sandbox", "--disable-dev-shm-usage"]
        )
        ctx = browser.new_context(viewport={"width": 1280, "height": 900})
        page = ctx.new_page()
        page.goto(base + "/dashboard")
        page.wait_for_load_state("networkidle")

        for path, name in routes_to_shoot(ids):
            try:
                page.goto(base + path)
                try:
                    page.wait_for_load_state("networkidle")
                except Exception:  # noqa: BLE001 — slow assets shouldn't kill the shot
                    pass
                page.wait_for_timeout(250)
                page.screenshot(path=str(OUT / f"{name}.png"), full_page=True)
                status = "ok"
            except Exception as exc:  # noqa: BLE001
                status = f"ERROR: {exc}"[:120]
            summary[path] = {"file": f"{name}.png", "status": status}
            print(f"  {path:42s} {status}")

        # ── exports: save the actual files + a screenshot of rendered CSV ──
        exports = [
            ("/ventas/export.csv", "export-ventas.csv"),
            ("/productos/export.csv", "export-productos.csv"),
            ("/inventario/export.csv", "export-inventario.csv"),
            ("/pedidos/export-csv?status_filter=todos", "export-pedidos.csv"),
            ("/reportes/precios/csv", "export-reportes-precios.csv"),
            ("/excel/exportar", "export-excel.xlsx"),
            ("/reportes/diario/pdf", "export-reportes-diario.pdf"),
            ("/reportes/iva/pdf", "export-reportes-iva.pdf"),
        ]
        for path, fname in exports:
            try:
                resp = page.request.get(base + path)
                if resp.ok:
                    body = resp.body()
                    (OUT / fname).write_bytes(body)
                    # rendered preview: paint the text content in the browser
                    # (never navigate to the download URL — it throws)
                    if fname.endswith(".csv"):
                        text = body.decode("utf-8", errors="replace")[:20000]
                        page.goto("about:blank")
                        page.set_content(
                            f"<pre style='font:12px monospace;padding:16px'>"
                            f"{text.replace('&','&amp;').replace('<','&lt;')}</pre>"
                        )
                        page.screenshot(path=str(OUT / f"{fname[:-4]}.png"), full_page=True)
                    status = f"ok ({len(body)} bytes)"
                else:
                    status = f"HTTP {resp.status}"
            except Exception as exc:  # noqa: BLE001
                status = f"ERROR: {exc}"[:80]
            summary[f"EXPORT {path}"] = {"file": fname, "status": status}
            print(f"  {path:42s} {status}")

        ctx.close()
        browser.close()

    (OUT / "summary.json").write_text(json.dumps(summary, indent=2))

    ok = sum(1 for v in summary.values() if v["status"].startswith("ok"))
    # contact sheet
    cards = "\n".join(
        f'<figure><img src="{v["file"]}" loading="lazy"><figcaption>{k}</figcaption></figure>'
        for k, v in summary.items() if v["status"].startswith("ok")
    )
    (OUT / "index.html").write_text(
        f"<!doctype html><meta charset='utf-8'><title>Saskia pages</title>"
        f"<style>body{{font-family:sans-serif;margin:20px}}figure{{margin:0 0 28px}}"
        f"img{{max-width:100%;border:1px solid #ccc}}figcaption{{font-size:13px;color:#556}}</style>"
        f"<h1>Saskia RMS — {ok}/{len(summary)} pages</h1>{cards}"
    )
    print(f"\n{ok}/{len(summary)} pages captured → {OUT.resolve()}")
    server.should_exit = True
    engine.dispose()


if __name__ == "__main__":
    main()
