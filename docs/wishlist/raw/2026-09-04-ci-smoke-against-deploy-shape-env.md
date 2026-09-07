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
