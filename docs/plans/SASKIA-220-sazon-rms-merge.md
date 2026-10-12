# SASKIA-220 — Sazón Restaurant Management System (merge + rename + first tenant)

**Status:** DRAFT. Awaiting Iván sign-off. Supersedes SASKIA-210.

## Context (why now)

The 2026-10-07 SASKIA-210 decision (per-client INSTANCES) is REVERSED (2026-10-12, Iván).
The new direction: a single shared codebase that supports multiple restaurant tenants via
**separate Supabase projects** (per-tenant DB, env-selected). The repo itself is renamed
to **Sazón Restaurant Management System**, and Saskia/La Vaquita Holandesa becomes the
first (currently only) tenant — she gets her own Supabase project + own seed data + own
admin account, loaded from her Google Maps / WhatsApp exports.

## Good news (2026-10-12)

**The Sazon stack ALREADY uses Traefik Host-based routing** for its 3 env stacks
(`saskia-vps.paragu-ai.com`, `saskia-test.paragu-ai.com`, `saskia-dev.paragu-ai.com`).
See `deploy/docker-stack.template.yml` for the existing pattern. So the URL-based
multi-tenant routing for SASKIA-220 is a **generalization** of an existing pattern,
not a new infrastructure.

**What this means concretely**:
- The Traefik expertise is already in the deploy system.
- The Host header injection pattern is already battle-tested.
- Adding tenant routing is a 1-line change to the router label + a middleware in
  the FastAPI app to read the Host and resolve a tenant.
- No new infrastructure: same VPS, same Docker Swarm, same Traefik, same Cloudflare.

## What's wrong today (the merge problem)

We have two repos in `/opt/data/work/`:

| Repo | Origin | Purpose | Latest |
|---|---|---|---|
| `saskia-app` | `git@github.com:Ai-Whisperers/saskia-app.git` (was upstream; PRs #148-153) | The "blessed" mainline with 12+ sprints of work | `5bdc4b28` SASKIA-212 |
| `saskia-app-vaquita` | `git@github.com:Ai-Whisperers/saskia-app.git` (fork) | La Vaquita tenant work (SASKIA-213 packs.py, SASKIA-215/216 seeds) | `e5e40e4a` SASKIA-215+216 |

The split is a relic of "one repo per tenant" thinking. The Sazon RMS direction is
"one repo, many tenants in it" — so the fork is now an anti-pattern.

The third worktree `saskia-app-abstraction-gates` is just a temporary checkout of main
created during the SASKIA-211d enforcement work; it can be removed after the merge.

## Goal

1. **One repo, named Sazón Restaurant Management System**, on github.com.
2. Saskia/La Vaquita = first tenant, on a NEW Supabase project, with her seed data loaded.
3. Tenant abstraction is **env-driven** (one tenant per process, switched by `.env`).
4. The "upstream" `saskia-app` repo gets **archived** (read-only, kept for history).

## Architecture (the new model)

### Repo
- **New repo name**: `sazon-restaurant-management-system`
- **Visibility**: private (matches current)
- **Branch**: `main` (the surviving branch from the merge; no feature branches stay around)
- **License**: still MIT (matches)

### Tenancy model — URL-based routing
- **One codebase, one process pool, ONE VPS deploy.** Multiple tenants share the same
  app containers.
- **Each tenant has their own URL** (subdomain: `la-vaquita.sazon.app`,
  `lido22.sazon.app`, etc.). The URL is the routing key.
- **How URL → DB works**: Traefik (already in the stack) reads the `Host` header and
  injects a per-tenant `TENANT_CONFIG` env var (or sets an HTTP header) that the app
  reads on every request.
- **The app** has a middleware that resolves `Host` → tenant config (filesystem
  `/etc/sazon/tenants/<host>.yaml`) → DATABASE_URL → SQLAlchemy engine.
- **No cross-tenant queries in the app code.** Each request gets a single tenant's
  engine. The `tenant` table (migration 008) stays dormant — tenancy is at the
  routing layer, not the DB layer.
- **Why this design**:
  - One deploy, one codebase → operators maintain ONE thing
  - Per-tenant Supabase = strong data isolation (each tenant = its own Supabase project,
    its own DB, its own backups, its own RLS auth settings)
  - URL-based routing means the operator doesn't need to add a tenant table or row-level
    security — the proxy handles the dispatch
  - Adding a new tenant = add a `tenants/<host>.yaml` + a Traefik rule + provision a
    new Supabase project. No code change.
- **The `tenants/vaquita.yaml` file format** (proposed, TBD):
  ```yaml
  host: la-vaquita.sazon.app
  display_name: "La Vaquita Holandesa"
  locale: es_PY
  branding:
    primary_color: "#8B4513"
    logo_path: /etc/sazon/tenants/la-vaquita/logo.png
  database_url_env: SUPABASE_DB_URL_VAQUITA
  ```

### Tenant config (on disk)
- **Location**: `/etc/sazon/tenants/<host>.yaml` on the VPS (NOT in the repo — these
  contain Supabase URLs that are deployment-specific).
- **Repo mirror**: a sanitized `tenants/example.yaml` checked into the repo as a template.
- **Loader**: `app/rms/tenant.py::resolve_tenant(host: str) -> TenantConfig` — reads
  the YAML based on the request's `Host` header. Fails closed if the host is not found.
- **DB engine cache**: `app/rms/tenant.py::get_engine(tenant)` — SQLAlchemy engines
  are cached per-tenant (one engine per tenant, not per-request).

### Saskia-specific data (what was in saskia-app-vaquita)
- `app/rms/seed/packs.py` — `seed_pack(session, 'Pizzería')` etc. (SASKIA-213)
- `tests/test_packs_saskia220.py` — pack tests
- The SASKIA-215/216 work (seed verification, +2 commits)
- All the `app/rms/seed/` work for Vaquita — moves into the new repo unchanged.

### Saskia deployment (the first tenant)
- **Today**: Saskia runs as `saskia-vps` Docker stack on paragu-ai, with SQLite-on-VPS
  at `/data/rms.sqlite`. Migrations 1-114 applied. Loaded with her seed data
  (298 products / 59 Asunción businesses, from her Google Maps + WhatsApp exports).
- **After the merge**: her stack gets renamed to `sazon-vps` and runs against **her own
  Supabase project** (separate from any future `sazon-rms` shared Supabase).
- **Migrate story**: SQLite → Postgres. Apply Sazon's 114 migrations to a fresh Supabase
  Postgres project → export her current data → import into the new Postgres → verify with
  the Sazon test suite on the new DB.
- **The Supabase project** is the tenant boundary. The app code is unaware of tenancy —
  one process connects to one DB.

### Archived: saskia-app upstream
- Set the GitHub repo `Ai-Whisperers/saskia-app` to **archived** (read-only).
- Keep all 5 PRs (#148-153) in history.
- Local clones stay on disk for the next 90 days; then delete.

## What gets dropped (vs the "merge both repos" naive plan)

- `saskia-app` upstream's SASKIA-212 (recipe instructions editor) — **NOT merged** in v1.
  Reason: the SASKIA-211d abstraction-usage enforcement + SASKIA-212 recipes
  PR are valuable but they're the upstream's, and the Sazon direction is "merge Vaquita's
  work into one repo, not graft upstream on top". The Sazon RMS team can pull SASKIA-212
  in a v2 plan once the merge is stable.
- The 3 commits on the `SASKIA-211a-utcnow-and-apply-sale-imports` branch — **also NOT
  merged** in v1. Same reason. Those are upstream work.

So the merge is actually: **saskia-app-vaquita's main + SASKIA-213/215/216/220 work
becomes the new Sazon RMS main**. The saskia-app upstream history is archived but
not merged.

## Plan (multi-day, sign-off at each gate)

### Day 1 (TODAY) — Plan + sign-off
- [x] Memory updated with SASKIA-210 reversal + SASKIA-220 plan (awaiting approval)
- [ ] **This doc reviewed and approved by Iván** ← you are here
- [ ] Identify what specific commits/branches from `saskia-app-vaquita` need to land in Sazon RMS
- [ ] Decide tenant config file format (YAML vs JSON vs env-only)

### Day 2 — Repo creation
- [ ] Create `Ai-Whisperers/sazon-restaurant-management-system` (private) on github
- [ ] Add SSH key access (already in place: github-hermes-agent)
- [ ] Set repo description, topics, AGPL/MIT license file (decide on TBD)
- [ ] Add CODEOWNERS, .gitignore, README skeleton

### Day 3 — Merge + rename
- [ ] Add new remote to `saskia-app-vaquita` worktree
- [ ] Cherry-pick or fast-forward all 8 vaquita commits → Sazon RMS main
- [ ] Rename the codebase: `Sazón RMS` references everywhere (commit message, package name?)
- [ ] Delete the old `Saskia-rms` references in the merged tree (keep "Sazón" branding)
- [ ] First commit: "Initial Sazon Restaurant Management System import from saskia-app-vaquita"

### Day 4 — Tenant abstraction (URL-based)
- [ ] Add `tenants/example.yaml` (sample, sanitized — not the real Supabase URL)
- [ ] Add `app/rms/tenant.py` with `resolve_tenant(host) -> TenantConfig` and
      `get_engine(tenant) -> Engine` (cached)
- [ ] Add FastAPI middleware that reads `Host` header → resolves tenant → sets
      `request.state.tenant` (and `request.state.db`)
- [ ] Update `app/rms/main.py` startup to log the registered tenants
- [ ] Traefik: no change needed! The Host-based routing is already done
      (see `deploy/docker-stack.template.yml`)
- [ ] Add 5+ tests for tenant loading (unknown host, missing file, malformed YAML,
      engine caching, no leakage between tenants)
- [ ] **Bonus**: expand Traefik to support wildcards (like `*.sazon.app`) so
      we can route multiple tenant subdomains without explicit configs

### Day 5 — Saskia's Supabase project
- [ ] Provision `sazon-rms-vaquita` Supabase project
- [ ] Apply Sazon's 114 migrations to the new Postgres project
- [ ] Seed with Vaquita's pack (298 products, 59 businesses) — verify against `seed_pack` test
- [ ] Smoke test: login as Saskia, see her own data
- [ ] Update `docs/operations/SASKIA-220-vaquita-supabase-setup.md` with the actual steps

### Day 6 — Archive + cleanup
- [ ] Archive `Ai-Whisperers/saskia-app` on github (read-only)
- [ ] Add redirect note in saskia-app README → Sazon RMS
- [ ] Remove `saskia-app-abstraction-gates` worktree locally
- [ ] Final verification: clone Sazon RMS from scratch, run the test suite, deploy to a staging VPS

## Risks / open questions

1. **License**: Sazon RMS vs MIT license. Open question — do we change?
2. **Branding**: the current UI says "Saskia" in many places. Do we rebrand to "Sazón" everywhere?
3. **Migration story**: saskia-app-vaquita has migration 114 on SQLite. The new Supabase
   is Postgres. The Sazon tests have been run on SQLite; do they pass on Postgres? (Likely yes
   for migrations 1-114, but worth a smoke test on day 5.)
4. **GitHub repo name**: `sazon-restaurant-management-system` is verbose. Alternatives:
   `sazon-rms`, `sazon-rm`, `sazon`. Operator preference TBD.
5. **What if the new repo has CI issues**: saskia-app-vaquita currently has the CI gate
   enforcement (PRO-SEC, SASKIA-211d) — the new repo needs the same gate. Plan to copy
   the existing `.github/workflows/` from saskia-app-vaquita.
6. **Traefik Host routing**: Traefik already terminates TLS for `sazon-vps.paragu-ai.com`.
   Adding wildcard routing `*.sazon.app` means: (a) wildcard DNS, (b) wildcard TLS cert
   (Let's Encrypt supports this), (c) Traefik rule for `Host()` matching. All known how-tos,
   but adds operational surface. The first tenant (Vaquita) might want to keep her
   specific hostname (`la-vaquita.sazon.app`) instead of wildcard.
7. **Tenant data isolation**: per-tenant Supabase gives strong isolation, BUT shared app
   code = shared vulnerabilities. A bug in `app/rms/...` that affects one tenant's auth
   could affect all tenants. The URL→tenant middleware must be bullet-proof (Host header
   validation, no header injection from upstream).
8. **Migrating Saskia's data**: she's on SQLite. The new Supabase is Postgres. We need
   to either: (a) export/import with a custom tool, (b) re-seed from her Google Maps +
   WhatsApp exports, or (c) keep SQLite as the historical record and only the new
   (post-migration) data goes to Postgres. (c) is risky (data split). (a) is the right
   answer but needs a tool that handles the Sazon 117-migration schema + the Sazon
   money math (Decimal → int) + the stock_movements foreign keys.

## What I am NOT going to do without further sign-off

- Touch the live Saskia deployment (saskia-vps service) until the new repo + new Supabase
  is verified end-to-end in a staging environment.
- Delete the `saskia-app` repo on github (archive only).
- Merge saskia-app upstream's SASKIA-211/212 work in v1.

## Decisions captured from the clarifications (2026-10-12)

| Question | Decision |
|---|---|
| Scope of merge | saskia-app-vaquita (SASKIA-215/216) + Sazon RMS. saskia-app upstream DROPPED. |
| Multitenancy | Per-tenant Supabase project (env-selected). |
| When | Multi-day; plan first, get sign-off, then execute. |
| Tenant routing | URL-based (Host header → tenant config). One process pool, many tenants. |
| Now | Keep summarizer running, draft this plan in parallel. |

## Sign-off

Iván: please review and either approve as-is, or annotate. The plan is to keep this doc
in `docs/plans/` as the source of truth until the merge is done; then archive it.
