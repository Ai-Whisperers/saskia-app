# Auto-reorder based on stockout report

**Date:** 2026-09-04
**Author:** operator (Iván) — inferred from Saskia's Round-1 verbal feedback
**Cost guess:** M
**Phase guess:** 2
**Source:** inferred from stockout report usage; Saskia mentioned "could the app tell me when to reorder?" 2026-09-02

## What

When the monthly stockout report lists ingredients that fell below `min_stock`, automatically generate a "to reorder" list grouped by supplier. Each entry has: ingredient name, current stock, target stock, suggested order qty, supplier contact (if known).

## Why now

The stockout report is the closest existing signal to "what to reorder next", but right now Saskia has to manually compare each row against her supplier list.

## Repro / context

- Saskia has ~30 ingredients, ~8 suppliers. Manual reorder takes 20-30 min/week.
- No supplier table in DB yet — would need to add `supplier_id` FK to Ingredient.
