# Multi-user roles (admin vs cashier)

**Date:** 2026-09-04
**Author:** operator (Iván) — inferred from v1 plan §11
**Cost guess:** L
**Phase guess:** 3
**Source:** `docs/plans/2026-08-31-rms-fase-1-dev-plan.md §11` (out of scope for Fase 1)

## What

Right now there's exactly one Supabase-authenticated user (Saskia) who has all permissions. Future: a cashier who can register sales but not void sales; a second admin. Add a `role` field on a `User` table, gate routes by role, update the audit log to record acting user per action.

## Why not now

Fase 1's scope is single-operator. Adding RBAC adds complexity that isn't justified yet.

## Repro / context

- The Operator-only `/audit` view (E3.S1) is the first step toward a role system.
- Needs Saskia to confirm she ever expects multiple people using the same install.
## Triage

**Moved to rejected:** 2026-09-09
**Status:** REJECTED — explicitly out-of-scope per AGENTS.md "no multi-tenant / no RBAC for single-user deployment". Code removed in earlier refactor (commits in Tier 1 R1 deleted `tenants.py` and `future.py`).
