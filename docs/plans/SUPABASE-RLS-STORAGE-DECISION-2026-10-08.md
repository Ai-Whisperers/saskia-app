# SASKIA-Supabase-RLS-Storage — Decision Required

> **For Iván.** This is a one-pager to decide whether/when to tackle
> IMPROVEMENT_BACKLOG items #37 (Supabase Storage) and #38 (Supabase
> RLS). Both are security/data-architecture items per AGENTS.md
> Decision framework → ASK before implementation.

## Current state (probed 2026-10-08)

- **#37 — Product images today**: `app/routers/products.py:upload_image()`
  saves to a configurable CDN URL (`/static/products/*.jpg`). Backend
  storage uses an external CDN (TBD: Cloudflare R2, AWS S3, or
  Cloudinary — operator picks). Files are referenced by URL, not
  uploaded to Supabase Storage. Searched `app/` — no Supabase Storage
  SDK installed (`grep -r "supabase_storage"` returns 0 hits).
- **#38 — Tenant table**: `app/rms/models/tenant.py:1` defines the
  model but no rows exist. `Tenant.id` exists as a column on `Product`
  (`nullable=True`) and a few other models. RLS policies don't exist
  (Postgres not on Supabase — running on Neon, no RLS feature).

## Why both deferred per SASKIA-210

`2206111b docs: SASKIA-210 DECIDED — per-client instances, not
shared-DB tenancy; deferred until Saskia is happy`: Saskia/La Vaquita
Holandesa is the only client. Each future client gets own Postgres +
app instance. **No multi-tenant DB**, so **no shared tenancy to
isolate** — RLS wouldn't add anything until we change this decision.

## Trigger conditions (when to revisit)

- **#37 (Storage)**: when Sazón either (a) exceeds 500 products and the
  CDN URL config gets unwieldy, (b) wants to upload photos from a
  mobile app that doesn't have a server-side proxy, or (c) starts
  serving images to a public web route that needs auth-gated URLs.
  Estimate: 6+ months out.
- **#38 (RLS)**: ONLY if SASKIA-210 is reversed AND a second client
  starts onboarding before Sazón has its own instance. Currently
  unlikely.

## Two implementation options if you say yes

### Option A — Storage only (#37)

**What**: add `supabase` Python SDK; refactor `app/routers/products.py`
to upload images to `supabase.storage.from_("products").upload()`;
swap the URL field to the public bucket URL.

**Cost**: M (per BACKLOG). 2-3 days.

**Security implications**:
- Public bucket vs authenticated bucket?
- Sazón is single-tenant today — bucket is private + signed URLs only.
- If you reverse SASKIA-210 later, this still works (each instance has
  its own bucket).

**Operator action**: set `SUPABASE_URL` + `SUPABASE_SERVICE_KEY` env on
VPS (already in `.env.example`). BWS has these in the
`aiwhisperers-supabase` item.

### Option B — Storage + RLS (#37 + #38)

**What**: Option A + add Postgres RLS policies on every table.

**Cost**: L (per BACKLOG). 1-2 weeks because every table needs a
policy review + testing.

**Security implications**:
- If we adopt this, we MUST reverse SASKIA-210 (RLS makes no sense
  in a single-instance-per-client world — the schema would be
  app-level tenant_id filtering).
- Test surface grows: every test that creates a row would need a
  tenant context.
- Migration path: the SASKIA-210 doc already covers the per-instance
  template for cloning prod → post-deploy.

## Recommended action (per Operator POV)

**Defer both indefinitely** until either:
- SASKIA-210 is reversed (then implement both A and B together),
- OR SKU volume / image-handling needs make Storage worth doing alone
  (M cost).

Until then, this one-pager can sit in `docs/plans/` and act as the
"yes-but-not-yet" decision record.

## What I need from you

Pick one:

1. **Defer both indefinitely** (recommended). This file becomes the
   deferral record; no code work.
2. **Implement Option A (Storage only)**. M effort, security-
   minded, your sign-off required before I touch the upload route.
3. **Implement Option A + B together**. L effort; usually bundled
   with reversing SASKIA-210.

---

**Author:** Hermes (autonomous session, 2026-10-08, per `WHAT_NEXT.md`
top-3 #3). **Status:** pending Iván decision.