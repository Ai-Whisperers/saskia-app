# SASKIA-210 one-pager — Supabase RLS + Storage multi-tenant readiness (backlog #8)

**Status:** scoped, not started. L effort (~3 days). Blocked-on-nothing but gated on a product
decision (see "Decide first").

## Current state (verified 2026-10-07)

- `app/auth_supabase.py` (repo root) — hosted-mode JWT auth. Sign-out clears the cookie only;
  the access_token stays valid until expiry. The "server-side revocation is a TODO from them"
  comment is **accurate but misattributed**: Supabase added revocation material long ago —
  what's missing HERE is checking it (see Revocation below).
- Schema: `tenant` table exists since migration 008; `tenant_id` col on the tenanted tables
  (e.g. `app/rms/models_legacy.py:666`, default 1). Single-tenant in practice: every row = 1.
- Storage: branding uploads land on the local FS (`app/static/branding/<id>/`), NOT Supabase
  Storage. There is no Storage dependency today.
- Postgres parity: models_legacy carries Postgres CheckConstraints, but the hosted DB is
  SQLite-on-VPS (`/data/rms.sqlite`). **Supabase RLS is only relevant if/when the hosted app
  moves its DB to Supabase Postgres** — a deployment change, not a code change.

## Decide first (Iván — product, not code)

1. Is external-tenant onboarding actually planned for the VPS hosted mode, or is this
   future-proofing? (30-customers rule cuts both ways.)
2. If yes: does the tenant DB move to Supabase Postgres (RLS matters, biggest change), or stay
   SQLite (RLS irrelevant; tenancy = WHERE tenant_id = :current enforcement in SQLAlchemy
   events, much smaller)?
   - **Recommendation: stay SQLite, enforce tenancy at the ORM layer** (session-scoped
     `tenant_id` filter via `with_loader_criteria` hook). RLS buys nothing on a single-writer
     SQLite file and costs a migration + connection layer rewrite.

## Scope IF SQLite route (recommended)

1. **Tenant context** — `app/rms/tenant_context.py`: request-scoped current tenant (from auth
   session), a `Session` factory that auto-applies `with_loader_criteria(TenantMixin,
   tenant_id == current)` on ALL selects + auto-sets `tenant_id` on inserts. ~1 day incl. tests.
2. **`TenantMixin`** on the 8-10 genuinely per-tenant tables (customers, sales, pedidos,
   ingredients, products, recipes, shopping, wishlist) — NOT on config/audit tables. Migration
   114 fills any NULL tenant_id → 1 (no-op today, matters on first real tenant).
3. **Revocation** — on sign-out, delete the Supabase refresh_token server-side via admin API
   (`auth.admin.signOut({userId})` / logout endpoint) so a stolen refresh token can't outlive
   the session; keep the cookie-clear + short access-token TTL as defense in depth. ~0.25d.
4. **Tests** — two tenants, cross-tenant read/write attempts all 404/empty; insert auto-stamps;
   revocation kills refresh.

## Scope IF Supabase Postgres route (defer)

All of the above PLUS: full DB move, RLS policies per table (`tenant_id = auth.jwt ->> 'tenant_id'`),
service-role vs anon key split in the connection layer, Storage bucket policies for branding
uploads, and a migration runbook for the VPS data. This is the 3-day+ version and should not
start before decision 2 lands.

## Est (SQLite route)

- tenant_context + loader-criteria session: 1d
- TenantMixin + migration 114: 0.5d
- Revocation via admin API: 0.25d
- Tests (cross-tenant matrix): 0.75d
- Runbook: 0.25d
