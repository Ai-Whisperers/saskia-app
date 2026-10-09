"""PRO-PED: /produccion/manana shows per-client pedido line items and
Pronóstico (forecast) + Pedidos + Total + Plan columns with persisted Plan overrides.

Captures the behavior changes that landed in 8a91f0e2 (sidebar wrap) +
the manana rewrite (pedidos per client, Plan column, pedidos_by_product
in forecast table). 4 tests, all run in <8s.
"""

import re
from datetime import timedelta

from app.rms.config import ASUNCION_TZ


def test_manana_pedidos_per_client(authed_client, qseed):
    """Each pedido renders as a card with the line items the client
    is actually buying (not just the customer name + total)."""
    qseed("with_manana_pedidos")
    r = authed_client.get("/produccion/manana")
    assert r.status_code == 200
    body = r.text
    # The pedidos section is structured as cards now
    assert "pedidos-manana" in body, "pedidos-manana details block missing"
    assert "pedido-card" in body, "pedido-card per pedido missing"
    # Each pedido shows its customer (rendered with the full name)
    assert "María Rodríguez" in body
    assert "Carlos Pereira" in body
    # The line items are visible (product names inside pedido-card)
    # Pedido 1 has Producto QA (6) + Empanada QA (12); pedido 2 has 3×QA
    assert "Producto QA" in body
    assert "Empanada QA" in body


def test_manana_queproducir_columns(authed_client, qseed):
    """The "Qué producir" table has Forecast + Pedidos + Total + Plan
    columns. Plan is the editable override (the old Override column
    renamed for clarity)."""
    qseed("with_manana_pedidos")
    r = authed_client.get("/produccion/manana")
    assert r.status_code == 200
    body = r.text
    # Each column header appears in the table
    for col in ("Pronóstico", "Pedidos", "Total", "Plan ⇄"):
        assert col in body, f"Column '{col}' missing from Qué producir table"
    # The "9 unidades comprometidas" pill from pedidos_by_product
    assert "9 unidades comprometidas" in body or "9</span>" in body
    # The Total = forecast + pedidos (10 = 1 forecast + 9 pedidos)
    assert ">10<" in body  # 10 unidades displayed


def test_manana_plan_persists(authed_client, qseed):
    """POST /produccion/override-bulk with qty[<id>]=N persists into
    ProductionPlanOverride. Reloading /produccion/manana shows the
    pre-filled Plan input."""
    from datetime import datetime

    qseed("with_manana_pedidos")
    r = authed_client.get("/produccion/manana")
    assert r.status_code == 200
    m = re.search(r'name="qty\[(\d+)\]"', r.text)
    assert m, "No qty input found (the new 'Plan' column)"
    pid = m.group(1)
    # Use Asunción date so the key matches what the route reads
    tomorrow_asu = (datetime.now(ASUNCION_TZ).date() + timedelta(days=1)).isoformat()
    r2 = authed_client.post(
        "/produccion/override-bulk",
        data={"for_date": tomorrow_asu, f"qty[{pid}]": "12"},
        follow_redirects=False,
    )
    assert r2.status_code == 303, f"override post returned {r2.status_code}"
    r3 = authed_client.get("/produccion/manana")
    assert r3.status_code == 200
    pat = rf'name="qty\[{pid}\]"[^>]*value="([\d.]+)"'
    m2 = re.search(pat, r3.text)
    assert m2 and m2.group(1) in ("12", "12.0"), (
        f"Plan override not persisted for product {pid}: {m2.group(0) if m2 else 'no match'}"
    )


def test_sidebar_app_shell_wrapper(authed_client, qseed):
    """The <div id="app-shell"> wrapper exists so the JS mobile toggle
    and CSS grid layout both work. The wrap landed in 8a91f0e2 to fix
    Ivan's 'lost the navigation bar on the left' report."""
    qseed("with_many_products")
    r = authed_client.get("/produccion")
    assert r.status_code == 200
    body = r.text
    # The wrapper must have the app-shell class (CSS uses
    # body.has-app-shell > .app-shell as the grid container)
    m = re.search(r'<div id="app-shell" class="app-shell">', body)
    assert m, "app-shell wrapper missing or missing the app-shell class"
    # The sidebar and main are direct children of the wrapper, in order
    m = re.search(
        r'<div id="app-shell" class="app-shell">\s*<aside class="sidebar"',
        body,
        re.DOTALL,
    )
    assert m, "sidebar is not a direct child of #app-shell"
    # The wrapper closes after the footer
    assert body.count('<div id="app-shell" class="app-shell">') == 1
    assert body.count("</div><!-- /.app-shell -->") == 1
