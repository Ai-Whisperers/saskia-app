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

## DECIDED (Iván, 2026-10-07) — DEFERRED until Saskia (La Vaquita Holandesa) is happy

**Model chosen: per-client INSTANCES, not shared-DB multi-tenancy.** Each client gets their own
website/instance with everything fully loaded for them (own DB, own branding, own data).
Possibly one BASE Supabase project as the template that gets copied per new client, plus a
separate cross-client analytics layer to understand all clients' metadata and help them better.

Consequences:
- **No RLS, no ORM tenancy, no tenant_id enforcement work now.** The `tenant` table (migration
  008) stays dormant at tenant_id=1.
- The future build is an **instance-provisioning pipeline** (clone base → configure branding →
  seed client data → deploy instance) + a **fleet-analytics aggregator**, NOT tenancy code.
- Trigger to revisit: Saskia confirms satisfaction / a second client is signed.
- The per-instance model also means SASKIA-209's `sazon rollback` and the rule-17 backup
  discipline apply per-instance — the safety net scales with the fleet for free.

## Scope IF shared-DB route — NOT CHOSEN, kept only for reference

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
