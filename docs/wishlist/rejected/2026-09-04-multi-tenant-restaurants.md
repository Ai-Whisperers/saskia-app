# Multi-tenant (multiple restaurants under one deploy)

**Date:** 2026-09-04
**Author:** operator (Iván) — inferred from AGENTS.md
**Cost guess:** XL
**Phase guess:** 4+
**Source:** `AGENTS.md` "Multi-tenant" mentioned as future

## What

Multiple Saskias under one hosted deploy. Each `tenant_id` scopes all data; login routes to the right tenant; backups are per-tenant.

## Why not now

Saskia is the only customer. Multi-tenant is only worth building when we have ≥ 3 paying restaurants and a clear per-tenant pricing model. Schema accepts `tenant_id` later without breaking changes.
## Triage

**Moved to rejected:** 2026-09-09
**Status:** REJECTED — explicitly out-of-scope per AGENTS.md "no multi-tenant / no RBAC for single-user deployment". Code removed in earlier refactor (commits in Tier 1 R1 deleted `tenants.py` and `future.py`).
