"""Source locks for proveedores, movimientos, caja, banco, and fiado rows.

Proveedores answers who to call. Movimientos answers what changed the stock.
Caja answers open or close the drawer. Banco answers the date, the amount,
and whether it is reconciled. Fiado answers who owes and whether the account
is active.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = REPO_ROOT / "app" / "templates"


def _read(name: str) -> str:
    return TEMPLATES.joinpath(name).read_text(encoding="utf-8")


def _slice(src: str, start: str, end: str, from_idx: int = 0) -> str:
    begin = src.find(start, from_idx)
    assert begin >= 0, f"Missing {start!r}"
    finish = src.find(end, begin)
    assert finish > begin, f"Missing {end!r} after {start!r}"
    return src[begin:finish]


def test_suppliers_leads_with_nombre_and_telefono():
    """L1 is Nombre, Teléfono, and the Nuevo proveedor button.

    Contacto, Email, RUC, Ingredientes, and the row actions sit under
    Ver detalles. There is no import/export on this page, so no Más.
    """
    src = _read("suppliers.html")
    table = src.find("<table")
    assert table > 0
    assert src.find("Nuevo proveedor") < table
    assert 'href="/suppliers/nuevo"' in src[:table]

    thead = _slice(src, "<thead>", "</thead>", table)
    for label in ("Nombre", "Teléfono", "Ver detalles"):
        assert label in thead, label
    for parked in ("Contacto", "Email", "RUC", "Ingredientes"):
        assert parked not in thead, parked
        assert parked in src

    tbody = _slice(src, "<tbody>", "</tbody>", table)
    details = tbody.find("<summary>Ver detalles</summary>")
    assert details > 0
    lead = tbody[:details]
    assert "s.phone" in lead
    assert "fmt.entity_name(s)" in lead
    parked = tbody[details:]
    for label in ("Contacto", "Email", "RUC", "Ingredientes"):
        assert label in parked, label
    for token in (
        'href="/suppliers/{{ s.id }}/precios"',
        'href="/suppliers/{{ s.id }}/ordenes"',
        'href="/suppliers/{{ s.id }}/editar"',
        'action="/suppliers/{{ s.id }}/eliminar"',
        'action="/suppliers/{{ s.id }}/reactivar"',
        "Ver precios",
        "Ordenar",
        "Editar",
        "Desactivar",
        "Reactivar",
        "js-confirm-form",
    ):
        assert token in parked, token
    assert "<summary>Más</summary>" not in src
    assert "<summary>Filtros</summary>" not in src
    assert "supplier-list" in src
    assert "ops-list__details" in src


def test_movimientos_leads_with_fecha_tipo_and_cantidad():
    """L1 is Fecha, Tipo, and Cantidad.

    The handler has no type or date filter, so the page does not invent
    Filtros. Balance, motivo, referencia, and operador sit under Ver detalles.
    """
    src = _read("inventario_movimientos.html")
    assert "Volver al inventario" in src
    assert 'href="/inventario"' in src
    table = src.find("<table")
    thead = _slice(src, "<thead>", "</thead>", table)
    for label in ("Fecha", "Tipo", "Cantidad", "Ver detalles"):
        assert label in thead, label
    for parked in ("Balance antes", "Balance después", "Motivo", "Referencia", "Operador"):
        assert parked not in thead, parked

    tbody = _slice(src, "<tbody>", "</tbody>", table)
    details = tbody.find("<summary>Ver detalles</summary>")
    assert details > 0
    lead = tbody[:details]
    assert "m.recorded_at" in lead
    assert "m.movement_type" in lead
    assert "m.qty" in lead
    parked = tbody[details:]
    for label in ("Balance antes", "Balance después", "Motivo", "Referencia", "Operador"):
        assert label in parked, label
    assert 'href="/ventas/{{ m.reference_id }}/recibo"' in parked
    assert "m.balance_before" in parked
    assert "m.balance_after" in parked
    assert "m.created_by" in parked
    assert "<summary>Filtros</summary>" not in src
    assert "move-list" in src


def test_caja_open_close_stays_and_sessions_park_amounts():
    """Abrir and Cerrar stay on the page. Session amounts sit under Ver detalles."""
    for name, opener in (("caja.html", "money("), ("caja_z.html", "money(")):
        src = _read(name)
        sessions = src.find("Sesiones recientes")
        assert sessions > 0, name
        assert src.find('action="/caja/abrir"') < sessions, name
        assert src.find('action="/caja/cerrar"') < sessions, name
        assert src.find(">Abrir caja</button>") < sessions, name
        assert src.find("Cerrar caja (Z)") < sessions, name

        table = src.find("<table", sessions)
        thead = _slice(src, "<thead>", "</thead>", table)
        assert "Apertura" in thead, name
        assert "Cierre" in thead, name
        assert "Ver detalles" in thead, name
        for parked in ("Esperado", "Contado", "Diferencia"):
            assert parked not in thead, f"{name} {parked}"

        tbody = _slice(src, "<tbody>", "</tbody>", table)
        details = tbody.find("<summary>Ver detalles</summary>")
        assert details > 0, name
        lead = tbody[:details]
        assert "s.opened_at" in lead, name
        assert "s.closed_at" in lead, name
        parked = tbody[details:]
        for label in ("Apertura", "Esperado", "Contado", "Diferencia"):
            assert label in parked, f"{name} {label}"
        assert 'href="/caja/z/{{ s.id }}"' in parked, name
        assert ">Z</a>" in parked, name
        assert f"{opener}s.opening_gs)" in parked, name
        assert f"{opener}s.expected_gs)" in parked, name
        assert f"{opener}s.counted_gs)" in parked, name
        assert f"{opener}s.diff_gs)" in parked, name
        assert "<summary>Filtros</summary>" not in src, name
        assert "caja-list" in src, name


def test_bank_leads_with_fecha_importe_and_conciliacion():
    """L1 is Fecha, Importe, and Conciliación.

    Currency, dates, category, and CSV sit under Filtros. The manual
    movement form stays its own disclosure. Cuenta, Categoría, Contraparte,
    and Descripción sit under Ver detalles.
    """
    src = _read("bank.html")
    assert src.count("<ui-kpi-card") == 4
    filtros = src.find("<summary>Filtros</summary>")
    assert filtros > 0
    filtros_end = src.find("</details>", filtros)
    assert filtros_end > filtros
    panel = src[filtros:filtros_end]
    for token in (
        "currency=EUR",
        "currency=PYG",
        'name="start_date"',
        'name="end_date"',
        'action="/bank"',
        "/bank/export.csv",
        "categories",
    ):
        assert token in panel, token
    assert ">Filtros</button>" not in src

    add = src.find("Agregar movimiento manualmente")
    assert filtros_end < add
    assert 'action="/bank/add"' in src[add:]
    assert src.find("Conciliados") < filtros
    assert "reconciled=yes" in src[:filtros]

    table = src.find("<table")
    assert add < table
    thead = _slice(src, "<thead>", "</thead>", table)
    for label in ("Fecha", "Importe", "Conciliación", "Ver detalles"):
        assert label in thead, label
    for parked in ("Cuenta", "Categoría", "Contraparte", "Descripción"):
        assert parked not in thead, parked

    tbody = _slice(src, "<tbody>", "</tbody>", table)
    details = tbody.find("<summary>Ver detalles</summary>")
    assert details > 0
    lead = tbody[:details]
    assert 'action="/bank/{{ tx.id }}/reconcile"' in lead
    assert 'action="/bank/{{ tx.id }}/unreconcile"' in lead
    assert "tx.posted_at" in lead
    assert "tx.amount" in lead
    parked = tbody[details:]
    for label in ("Cuenta", "Categoría", "Contraparte", "Descripción"):
        assert label in parked, label
    assert "tx.counterparty_name" in parked
    assert "tx.description" in parked
    assert "tx.currency" in parked
    assert "bank-list" in src


def test_fiado_leads_with_cliente_saldo_and_estado():
    """L1 is Cliente, Saldo, and Estado. Límite and Ver sit under Ver detalles.

    The list has no nuevo or export control. The client ledger stays four
    columns, and Cobrar stays on that page.
    """
    src = _read("fiado.html")
    assert "Por vencer" in src
    assert "<summary>Más</summary>" not in src
    assert "<summary>Filtros</summary>" not in src
    table = src.find("<table")
    thead = _slice(src, "<thead>", "</thead>", table)
    for label in ("Cliente", "Saldo", "Estado", "Ver detalles"):
        assert label in thead, label
    assert "Límite" not in thead
    tbody = _slice(src, "<tbody>", "</tbody>", table)
    details = tbody.find("<summary>Ver detalles</summary>")
    assert details > 0
    lead = tbody[:details]
    assert "r.nombre" in lead
    assert "r.saldo" in lead
    assert "r.active" in lead
    parked = tbody[details:]
    assert "Límite" in parked
    assert "r.limit_gs" in parked
    assert 'href="/fiado/{{ r.customer_id }}"' in parked
    assert ">Ver</a>" in parked
    assert "fiado-list" in src

    ledger = _read("fiado_cliente.html")
    ledger_head = _slice(ledger, "<thead>", "</thead>")
    for label in ("Fecha", "Tipo", "Monto", "Nota"):
        assert label in ledger_head, label
    assert "<summary>Ver detalles</summary>" not in ledger
    assert 'action="/fiado/{{ cust.id }}/cobrar"' in ledger
    assert ">Cobrar</button>" in ledger


def test_ops_list_phone_puts_ver_detalles_on_its_own_row():
    """At 640px the disclosure does not share a grid row with the L1 fields.

    Open, the disclosure is the full-width second row. Print shows the panel.
    """
    css = (REPO_ROOT / "app" / "static" / "theme.css").read_text(encoding="utf-8")
    marker = "/* Ops lists"
    block = css[css.find(marker) :]
    assert block.startswith(marker)
    open_rule = block[
        block.find(".ops-list__details[open]") : block.find("@media (max-width: 640px)")
    ]
    assert "display: block" in open_rule
    assert "grid-column: 1 / -1" in open_rule
    assert "grid-row: 2" in open_rule
    phone = block[block.find("@media (max-width: 640px)") : block.find("@media print")]
    assert ".ops-list__details" in phone
    assert "grid-column: 1 / -1" in phone
    assert "grid-row: 2" in phone
    assert "grid-row: 3" in phone
    printed = block[block.find("@media print") :]
    assert "::details-content" in printed
    assert "content-visibility: visible" in printed
    assert ".inv-list__panel" in printed
