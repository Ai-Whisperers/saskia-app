# Phase 14 (2026-10-01) — Post-Phase-13 Execution Plan

User said: "do all of this all areas and analyze all additional things to do"

## Batches (one logical change per batch, verify + commit + deploy each)

### Batch A: Decorator completeness (P0 systemic)
- Add tests/test_decorate_pedido_completeness.py — locks _decorate_pedido's keys
  against the Pedido ORM columns. Catches the class of bug Phase 13 hit.
- Then fix _decorate_pedido to include ALL Pedido columns. This fixes
  ventana_text + invoice + address absence in:
    - pedidos.html (list)
    - pedido_board.html (kanban)
    - recibo.html (receipt)
    - pedido_publico.html (customer-facing)

### Batch B: Receipt + public view Phase-13 (P0)
- pedido_publico.html: ventana_text + address_text + invoice_ruc/razon_social
- recibo.html: same

### Batch C: Native <select> → <saskia-combo> migrations (P0 + systemic)
- pedidos_nuevo.html: address_kind, address_departamento, invoice profile
- cliente_editar.html: 3 selects
- The 8 other non-context files: suscripcion_form, productos, producto_form,
  produccion, merma, inventario, insight_margenes_detalle, insight_margenes, bank
- Update tests/browser/pages.py selectors for affected components

### Batch D: Customer-side CRUD (P1)
- New endpoints POST /clientes/{id}/invoice-profile[/...] + .../address[/...]
- New section in cliente_editar.html: Perfiles + Direcciones manager
- tests/test_invoice_profile_crud.py + tests/test_address_crud.py

### Batch E: Migration 082 — Expense model (P0 — biggest real bug)
- New app/rms/models/expense.py + Expense table
- Migration 082_expense_model
- Wire app/rms/accounting.py: expense summary from real rows, not placeholder=0
- Bump CURRENT_SCHEMA_VERSION to 82

### Batch F: Mobile UX audit (P1)
- Re-shoot all pages, examine 4 longest forms at 360px
- Apply fixes if needed

### Batch G: TODOs cleanup (P2)
- herebus.py:489 reconciled_by from session
- nav.py:217 /clientes/nuevo route
- riesgos.html POST /riesgos/new endpoint
- modelos/channels.py: remove deprecated TODO

### Batch H: Coverage gate (P2)
- Add pytest-cov to dev deps
- CI config: minimum 70% coverage

### Batch I: CF-tunnel liveness monitoring (P2)
- Cron that probes saskia-vps.paragu-ai.com/healthz every 5 min, alerts on 404

### Batch J: Catalog import from local → VPS (P2 — known backlog)
- Use xlsx export/import via /excel/exportar + /excel/importar

## Tracking

I'll work in order. Each batch = one commit + verify + push + deploy.

## Status
- [x] Plan recorded