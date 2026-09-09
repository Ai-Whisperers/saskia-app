# CI smoke test against deploy-shape env

**Date:** 2026-09-04
**Author:** Kiki — post-mortem of the 5 hotfixes
**Cost guess:** M
**Phase guess:** 1.5
**Source:** post-mortem of `f1af406`/`c093a75`/`99b37c6`/`bb21eff`/`501bcff` 2026-09-04

## What

GitHub Actions job that boots the app with a Postgres testcontainer, applies `apply_neon_schema.py`, then hits `/healthz`, `/login`, `/inventario` with mock auth. Catches deploy-shape regressions before they hit production.

## Status

**Became Epic E2.S1 + E2.S2 on 2026-09-04.**


## Triage

**Moved to triaged:** 2026-09-09
**Status:** SHIPPED — `scripts/smoke_test_deploy_shape.py` + `.github/workflows/smoke.yml`
**Resolved by:** commit (in this turn)
**Notes:** Boots ephemeral Postgres in CI, runs the app against it,
probes /healthz/db + /healthz/schema for drift detection. Catches
the class of bug that caused the 2026-09-08 schema-version outage.
