# Per-user audit log of CRUD on inventory/recipes/sales

**Date:** 2026-09-04
**Author:** operator (Iván)
**Cost guess:** S
**Phase guess:** 1.5
**Source:** `installer/ROUND-1-NOTES.md` future-state + Fase 1.5 hardening plan

## What

A single `AuditLog` SQLAlchemy model + a `log()` helper that wraps sensitive CRUD: who did what, when, to which row. Visible at `/audit` to operators only.

## Status

**Became Epic E3.S1 on 2026-09-04.** Story is being shipped as part of the Fase 1.5 hardening work.

## Repro / context

- Triggers: `void_sale`, `login_success/failure`, `import_xlsx`, `delete_ingredient`, `delete_recipe`, `delete_product`, `user_create`.
- Best-effort: log failure does NOT fail the original action.
