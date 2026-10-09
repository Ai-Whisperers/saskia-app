# Barcode scanner integration for inventory receive

**Date:** 2026-09-04
**Author:** operator (Iván) — noted during Phase 1 ops review
**Cost guess:** M
**Phase guess:** 2
**Source:** `docs/operations/2026-09-02-sazon-team-tasks.md`

## What

Add a barcode field to `Ingredient` and a "scan to add" mode that triggers from a USB barcode-scanner keyboard wedge. Each ingredient has a printable label template.

## Why now

the operator's volume is small enough that hand-typing is OK, but as she adds more SKUs the typing gets slower than scanning. Foundation for the future auto-reorder.

## Repro / context

- Need to check what barcode format her items use (EAN-13, Code-128, custom).
- Could integrate with the existing Excel import by adding a barcode column.

## Triage

**Moved to triaged:** 2026-09-09
**Status:** SHIPPED — `app/rms/barcode.py` (SKU column on Product + `get_product_by_sku()` lookup) + wired via `/sales/scan` route. E23.
