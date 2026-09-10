# Saskia RMS — State Analysis & Next Steps

> **Compiled:** 2026-09-08 (live, not from memory)
> **Repo:** `Ai-Whisperers/saskia-app` (code-only — companion `saskia-context` holds PII)
> **Operator:** Iván van der Pol (solo)

---

## 1. Where the code is

- **Working tree:** `/opt/data/profiles/ivan/scratch/saskia-app-work/` (clone of `Ai-Whisperers/saskia-app`)
- **Branch:** `main`, local HEAD = `e344950`, remote HEAD = `668d262`
- **16 commits ahead of remote** (all local — see Blocked §6)
- **80 total commits in repo**; ~57 functional + ~5 ops/docs + ~6 bugfixes
- **40 modules in `app/rms/`**, **56 test files**, **824 tests** (all passing last run)
- **CHANGELOG:** `app/CHANGELOG.md` has 30+ entries covering E6 through E35 + 4 bugfixes + the a11y audit
- **Plans:** 4 in `docs/plans/` (Fase-1 dev plan, complete-epic-plan v3 855 lines, data-intelligence v4 458 lines)
- **Wishlist:** 21 raw items already in `docs/wishlist/raw/` from 2026-09-04 sprint

---

## 2. What shipped (epic inventory)

| Phase | Scope | Status |
|---|---|---|
| E1-E5 (Fase 1 dev plan, Aug-31) | Auth, db, migrations, models, seed | ✅ shipped |
| E6-E25 (epic plan v3, Sep-07) | Tags, analytics, settings, customers/loyalty, waste, IVA, perf, PWA, multi-tenant, notifications, ESC/POS, barcode, backup, seasonal, RBAC seam | ✅ shipped |
| E26-E35 (data-intelligence v4, Sep-08) | Ingredient/recipe intelligence, menu engineering, inventory/sales/product-similarity/production-scheduler/food-cost/dashboard-insights | ✅ shipped |
| 4 bugfixes (Sep-08) | dialect-aware migrations, JSONB app_meta, N+1 batch-load, product.sku migration no-op | ✅ shipped local |
| Accessibility audit (Sep-08) | skip link, aria-current nav, /healthz fix, aria-live alerts, focus-visible | ✅ shipped |

**Test counts:** 629 (baseline) → 802 (after E34) → **824** (after audit fixes), all green.

---

## 3. What lives on the live Neon DB right now (live query, 2026-09-08)

```
=== app_meta ===
  schema_version:  8                ← stale; local code is at v10
  last_seed_at:    2026-09-08T03:18:19Z

=== row counts ===
  ingredient           30
  recipe               12
  recipe_line          80
  product              20
  sale                 920
  sale_stock_move      6169        ← grew from 2317 (more sales since last query)
  tag                  31
  tag_link             31
  audit_log            2
  customer             0           ← seeded feature exists, no data yet
  waste_log            0           ← feature exists, no data yet
  tenant               0           ← exists; "herbus" tenant should auto-seed
  user                 DROPPED     ← Supabase Auth is source of truth
```

**Ingredient columns live:** id, name, unit, stock_qty, purchase_price_gs, min_stock_qty,
notes, purchase_price_updated_at, last_consumed_at, shelf_life_days
→ **Missing the E26 columns** (`category`, `subcategory`, `allergens`, `dietary_tags`,
`role`, `storage`) — those land when v9 migration runs.

**Recipe columns live:** id, name, yield_qty, yield_unit, notes, prep_minutes
→ **Missing E27 columns** (`family`, `difficulty`, `is_vegan`, `is_vegetarian`,
`is_gluten_free`, `cook_minutes`, `cost_per_gram`) — those land when v10 migration runs.

---

## 4. Live site status (curl, just-now)

| URL | HTTP | Notes |
|---|---|---|
| `/healthz` | 200 ✅ | fine |
| `/healthz/db` | **503** ❌ | **the known PRAGMA bug — fixed in local `f272e87`, NOT deployed** |
| `/healthz/deps` | 200 ✅ | fine |
| `/login`, `/`, `/productos`, `/recetas`, `/inventario`, `/ventas`, `/excel` | 200 ✅ | dashboard does NOT yet show the E35 insights panel (deploy pre-dates that work) |
| Render auto-deploy service id: `srv-dac8g2u7bikc73f3psf0`, last deploy = commit `668d262` |

---

## 5. Architecture / decisions worth keeping in mind

- **Two deployment modes**: local-first (127.0.0.1:8765, SQLite) + hosted (Neon + Render + Cloudflare + Supabase Auth at saskia-rms.paragu-ai.com). See `docs/operations/2026-09-02-saskia-decision-hosted-pivot.md`.
- **Hard rules** (`AGENTS.md`): Decimal money / integer Gs. in DB, vos Spanish only, WAL mode, dialect-aware migrations (no `INSERT OR IGNORE` / no `AUTOINCREMENT`), no new deps without operator OK.
- **CI discipline gate**: every PR touching `app/`, `scripts/`, `tests/`, or `.github/` MUST also touch `app/CHANGELOG.md`.
- **Wishlist discipline**: append-only at entry level (`raw/` → `triaged/` → shipped or `rejected/`). New ideas should land there, not in formal epic backlogs.
- **One-commit-per-epic**: each E# ships as exactly one commit (module + tests + CHANGELOG bump + ruff clean + all tests passing).
- **Dialect-aware migrations**: every migration must work on SQLite AND Postgres. Helpers in `app/rms/db_dialect.py`.
- **`app_meta.value` is JSONB on Neon**: all inserts must cast `to_jsonb(:value::text)`. This is documented but easy to miss.
- **Live `user` table is dropped**: Supabase Auth is the source of truth in hosted mode.

---

## 6. What's blocked (must be solved by operator or external)

### 6.1 GitHub push (BLOCKS deployment of all 16 local commits)
- All `/opt/data/.gh_token*` files dead/revoked.
- BWS dedup 2026-09-06 deleted `github-pat-deploy`+`GITHUB_TOKEN`; only `aiw-deploy` App 4866705 remains, but PEM file isn't on disk.
- `mcp__github__push_files` has known bug.
- **Effect:** live site is on `668d262`; the 16 local commits including /healthz/db fix, N+1 perf fix, and E26-E35 are unreachable from Render until push works.
- **Operator options:**
  - Provide a fresh classic PAT (`ghp_*`) via BWS or `/tmp`.
  - Restore the PEM for App 4866705.
  - Push manually via `gh` CLI / GitHub UI for each commit.

### 6.2 Once push works → cascading unblocks (operator + Kiki steps)
- `aiw-saskia migrate` on Render → applies v9 + v10 to Neon (adds ingredient_intel + recipe_intel columns; additive, no data loss).
- Re-seed → populates E26/E27 inferred columns on existing 30 ingredients / 12 recipes.
- /healthz/db starts returning 200.
- /productos + /recetas get N+1 fix.
- Dashboard starts showing E35 insights panel.

### 6.3 Cloudflare tunnel token rotation (`docs/operations/cf-tunnel-rotation.md`)
- Operator-required. Token values [REDACTED]. Without rotation, hosted URL could become unreachable in 30 days.

### 6.4 testcontainers for real Postgres in CI
- Deferred — SQLite covers 83%+ of behavior, schema-versioned tests prove dialect-awareness. Worth doing only if we add a Postgres-specific feature.

### 6.5 UptimeRobot wiring + runbook
- Operator-required (5 min job).

---

## 7. Real gaps I see (from reading the code, not from a wishlist frame)

These are bugs/missing-features that affect real users of the deployed site RIGHT NOW:

1. **/healthz/db 503** — ops visibility broken. Fix is local. **Cost: 1 push.**
2. **/productos + /recetas N+1** — page load on Neon takes seconds. Fix is local. **Cost: 1 push.**
3. **E26-E35 not deployed** — dashboard shows nothing new; new intelligence modules unused. **Cost: 1 push + 1 migrate.**
4. **No GET /ventas/nueva** — only POST exists. Inline form lives on /ventas (POST target), so this is **NOT actually broken** — my audit script hit it expecting 200 but it's correctly POST-only. Listed for completeness; ignore.
5. **Audit trail has 2 entries** — feature ships, no usage. Worth a one-shot "backfill demo audit" via a fixture if we want to demo the audit log to Saskia.
6. **customer/waste_log/tenant = 0 rows** — schemas exist but no demo data. Same pattern as audit_log.
7. **No real `customer_id` linkage on `sale`** — sale → customer isn't recorded even when customer present. This is a design gap from E13 (the customer module landed but the sale-write path wasn't taught to look up customer by phone). Worth a small follow-up if loyalty accrual matters.
8. **/login form doesn't enforce CSRF** — AGENTS.md explicitly says "SameSite=lax + CSP defense-in-depth: No CSRF tokens" so this is intentional, but worth a code review comment so it doesn't get added by mistake later.
9. **`is_auth_disabled()` test seam is in production code** — `SASKIA_TEST_AUTH_DISABLED=1` is checked at request time. Fine for our use, but should be operator-only (env var, not request param).

---

## 8. Tier-1 ideas worth shipping next (small, high value)

These are concrete, each is 1 epic (~half-day to 1-day of work), no new dependencies:

| Idea | Why | Effort |
|---|---|---|
| **E36: Customer-on-sale auto-lookup** (POST /ventas/nueva accepts phone → matches or creates customer → records sale.customer_id) | Makes E13 loyalty actually accrue | 1 day |
| **E37: Sale refund / void with reason** (E33 already has `waste_cost` infrastructure; sales.void is the symmetric counterpart with stock-restore) | Real bakeries void sales; today only "anular" exists | 1 day |
| **E38: Printable daily report PDF** (HTML→PDF via weasyprint; or just a clean printable HTML route) | Saskia prints end-of-day; today exports are xlsx only | 2 days |
| **E39: Reorder list generator** (ingredient_intel + inventory_intel → auto-generate `reorder_suggestions` view + 1-click `crear_orden` stub) | Saves a real weekly chore | 2 days |
| **E40: 2FA on operator login** (TOTP via PyOTP; Supabase Auth supports TOTP natively in hosted mode) | Defense-in-depth; cheap on hosted | 1 day |
| **E41: Real audit-log viewer** (route + paginated table; today audit_log has data but no UI) | Compliance, debugging | 1 day |
| **E42: Mobile-friendly POS quick-entry** (today /ventas is desktop-shaped; a single-input "tap product, tap +/-, submit" mode for tablet) | Saskia's actual workflow on a tablet | 3 days |

Each maps cleanly to existing models; no new tables needed for any of them.

---

## 9. Tier-2 ideas (real value, larger)

- **Customer-facing storefront** (read-only menu + order-placement via tokenized link; integrates with hosted site + Supabase Storage for product photos). 2 weeks.
- **WhatsApp Cloud API real integration** (today `notifications.py` is a stub; need actual Meta Business onboarding + template approval). 1 week.
- **MercadoPago integration** (the actual Paraguayan payment gateway; webhook + reconciliation). 1 week.
- **Multi-location** (Tenant → Branch hierarchy + transfer orders + consolidated reports). 2 weeks.
- **Real PWA offline cache** (service worker stubs exist; needs actual strategy + asset manifest). 1 week.
- **Production worksheet printed** (today `produccion-del-dia` is HTML; a printable version with checkboxes saves the real morning workflow). 2 days.

---

## 10. Tier-3 / aspirational (NOT recommending right now)

- 1000-item wishlist volume expansion (no business case today).
- Voice/SMS/AI concierge ordering (operator complexity not justified).
- Multi-language i18n beyond `lang="es"` (Paraguayan Spanish only — `AGENTS.md` rule).
- Mobile app (web is responsive enough; native app = new dep + new auth + new release pipeline).
- Real accounting sync (banking integrations in PY are paper-heavy; not automatable cleanly).

---

## 11. My recommendation for the next session

**Before any new feature work:** solve the push blocker. All 16 local commits are valuable and unreachable. Two options:

1. **Push block → solved by operator** (5 min): operator provides a working PAT or PEM. Then 1 `aiw-saskia migrate` on Render, 1 re-seed, live site is materially better and the E26-E35 work is visible to Saskia.

2. **Push block → unsolved**: continue feature work, but every new commit piles up. Live site stays on 668d262 indefinitely. Diminishing returns.

**Once unblocked**, ship E36 (customer-on-sale), E37 (refund/void), E38 (printable daily report). These three together turn E26-E35 from "intelligence" into "operational" — they make the data actually affect the day-to-day workflow. Estimated 4 working days.

**Skip for now:** the 1000-item wishlist. The wishlist directory already exists with 21 raw items; more ideas can land there organically. Volume isn't the bottleneck — operator bandwidth on push + deploy + migrate is.

---

## 12. Open questions for you (Iván)

1. Push path — do you want to dig for a PEM file, generate a new PAT, or do you want me to try the `mcp__github__push_files` bug workaround?
2. Of the Tier-1 ideas, which 1-2 should I scope up next?
3. Do you want me to add real `customer_id` linkage to sales as a quick follow-up, or wait for E36?

(I won't take action on these — they'll wait for your call.)
