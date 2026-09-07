# Real Drive-shape fixture for Excel import test

**Date:** 2026-09-04
**Author:** operator (Iván) — flagged in v1 plan §11
**Cost guess:** S
**Phase guess:** 1.5
**Source:** `docs/plans/2026-08-31-rms-fase-1-dev-plan.md §11`

## What

Build a synthetic xlsx mirroring what Saskia keeps editing in Google Drive after import. Wire into `tests/test_import_xlsx.py`.

## Why now

The import is one of the few paths where Saskia regularly breaks things on her side — she edits the Drive file, then the next import has to gracefully merge.

## Repro / context

- Existing fixture is synthetic small. Drive-shape needs ≥ 50 ingredients, ≥ 10 recipes with sub-recipes, all 6 sheets.
- Should be committed as a real binary in `tests/fixtures/` so future regressions catch the same shapes.
