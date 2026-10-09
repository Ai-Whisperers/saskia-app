# 2026-09-08 Sazón — Reliability Review

Comprehensive analysis of failure modes for keeping
`https://sazon-rms.paragu-ai.com` live on the free-tier Render +
Neon + Supabase + Cloudflare stack.

Scope: single-tenant, single-operator bakery management app. No
multi-user, no multi-tenant. Free tier only.

## Critical (will fail in production — guaranteed)

### 1. App does not auto-run migrations (FIXED 2026-09-08)

Until commit `7e80644`, the lifespan required
`AIW_RMS_RUN_MIGRATIONS=1` env var. The Neon DB was stuck at
schema v10 while code expected v11 (sale.payment_method column).
Result: `column sale.payment_method does not exist` 500s.

**Fix:** migrations auto-run by default. Env var
`AIW_RMS_RUN_MIGRATIONS=0` to disable for maintenance windows.

### 2. Free-tier Render cold-start penalty (30-90s)

After ~5 min idle, the next request takes 30-90s to wake the container.
Every cold-start window: dashboard returns 502/504.

**Mitigation in place:**
- `app.state.ready` flag — `/healthz` returns 503 `warming_up`
  instead of crashing during cold start.
- UptimeRobot monitor (id `803916096`) pings `/healthz` every 5 min
  to keep the container warm for ~95% of idle periods.
- `init_db()` is called in lifespan on every boot — first DB call
  adds ~3-5s.

**Permanent fix:** upgrade to Render Standard ($7/mo) which has no
sleep. Operator decision pending.

### 3. Schema drift canary (Phase 1 R1)

New `/healthz/schema` endpoint reports drift between code version
and DB version. Returns 500 with `hint` field when drift > 0,
allowing monitoring to catch this category of failure before users
see 500s.

### 4. Cloudflare WAF blocks legitimate request probes

When the user reported "Internal Server Error" earlier, it was partly
the app crashing AND partly Cloudflare's bot-protection 429ing
probes. Real users behind CF see proper HTML responses.

## High-priority reliability gaps

### 5. SupabaseAuth calls run inline on every request

`/login` and `/` perform `supabase.auth.get_user()` HTTP calls
(50-300ms each). Combined with PG round-trip (~5-20ms), the
cold-start dashboard takes 18s for the first hit.

### 6. No Pydantic validation on form inputs (FIXED Phase 2 R4)

Negative discounts, 1M-unit sales, missing required fields could
pass silently. Replaced `Form.get()` with FastAPI `Form(...)`
constraints (gt=0, le=MAX_QTY, ge=0, le=MAX_DISCOUNT_GS). Bad input
→ 422.

### 7. CSRF middleware half-implementation (FIXED Phase 2 R7)

Previously always set `Secure=True` on CSRF cookie, breaking
local-dev plain HTTP. Now opt-in via
`AIW_RMS_FORCE_SECURE_COOKIES=1` env var (auto-set on Render).

### 8. No rate limiting on write endpoints (FIXED Phase 2 R5)

Bot could create thousands of phantom sales/merma in seconds.
`/ventas/nueva` and `/merma/registrar` now rate-limit 10/min/IP
via `is_write_rate_limited()` in `app.rms.rate_limit`.

### 9. audit_log grows unbounded (FIXED Phase 3 R9)

`scripts/audit_prune.py` deletes rows > 30 days. Default retention:
30 days (configurable via `--days N`).

## Medium priority

### 10. Dashboard batch fix depends on identity-map identity

`batch_products_cost_margin()` uses session's identity map. In high
concurrency, two requests sharing a connection could see each
other's in-flight data. SQLAlchemy `Session(bind=engine)` per
request is enforced, but no type guard prevents accidentally
sharing. Out of scope (single-user deployment).

### 11. `/healthz/db` only tests `SELECT 1`

Doesn't catch pool exhaustion. `pool_pre_ping=True` (Phase 2 R6)
ensures the next query retries after the pool recovers.

### 12. Logs go to stderr only (FIXED Phase 3 R8)

JSON-structured logs in prod (`AIW_SASKIA_LOG_FORMAT=prod`), human
in dev. Render log viewer now machine-parseable.

### 13. `/auditoria` had no date-range filter (FIXED Phase 3 R10)

Added `?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD` filters.

### 14. CSRF cookie on plain HTTP was broken (FIXED Phase 2 R7)

`AIW_RMS_FORCE_SECURE_COOKIES=1` controls Secure flag.

## Low priority (acceptable for now)

### 15. WasteImpact dataclass bug (FIXED 2026-09-08)

`@dataclass` declared `by_reason: dict[str, int]` without
`field(default_factory=dict)` — was a class attribute, not instance
attribute. Template tried `.items` on the class method. Fixed in
Task 5.

### 16. merma template rendered `items` without parens (FIXED)

`.items` → `.items()`.

### 17. No pagination on Ventas (deferred to Phase 6)

Shows 50 rows. With 920 sales, can become unwieldy but acceptable.

## Operator actions recommended

1. **Upgrade Render Standard** ($7/mo) — eliminates cold-start.
2. **Wire UptimeRobot to monitor `/healthz/schema`** — alerts on drift.
3. **Wire UptimeRobot to monitor `/healthz/errors`** — alerts on
   `last_1h > N` errors.
4. **Schedule `python scripts/audit_prune.py --days 30`** weekly via
   operator-side cron.

## Three things NOT to do

1. Don't add new dependencies without operator OK. AGENTS.md hard
   rule. Each new dep is a security review.
2. Don't add multi-tenant (E15). Single-restaurant deployment.
3. Don't add multi-user RBAC (E25). Single-operator deployment.

## See also

- `docs/operations/2026-09-08-live-site-issues-fixes.md` — past outages
- `docs/operations/2026-09-08-incident-response.md` — playbook
- `.hermes/plans/2026-09-08_205004-sazon-rms-free-tier-reliability.md` — full plan
