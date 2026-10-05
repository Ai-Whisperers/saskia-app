# 🔬 Logging, Errors & Observability Audit — sazon-app

**Date:** 2026-09-29
**Auditor:** Hermes (Ivan's profile)
**Scope:** every `logger.*` call, every `HTTPException`/`AppError` raise, every
`except` block, the central `errors.py` / `observability.py` / `messages.py`
infrastructure, the audit log coverage, and the user-facing error UX (500 / 404
templates + flash banners).
**Baseline:** the 2026-09-23 `OBSERVABILITY_AUDIT.md` work (typed exception
hierarchy + request-id middleware + centralized messages) is already shipped.
This is the next pass.

---

## TL;DR — what's strong, what's broken, what to add

### Strong (already shipped and good)
- Typed exception hierarchy (`errors.py`, 10 classes, reason_code + context + cause).
- Request-id middleware (`RequestContextMiddleware`) auto-binds to every loguru line.
- Global exception handler in `main.py` does 3-tier dispatch (AppError → HTTPException → unhandled 500).
- 500 HTML template shows click-to-copy request_id + expandable "What happened?" help.
- `/healthz`, `/healthz/db`, `/healthz/schema`, `/healthz/errors`, `/healthz/deps` — solid set of liveness/drift/dependency probes.
- Audit log auto-fills request_id + user_id via `record_audit()` helper.
- Rate-limit on auth (sliding 5-min window per IP, fail-open on DB outage — documented trade-off).
- Loguru JSON sink behind `AIW_SASKIA_LOG_FORMAT=prod` env flag.

### Broken (silent failures + leaks — fix before scaling)
1. **🐛 `observability._safe_get_user_id` looks at wrong session key** — auth writes `request.session["local_user_id"]` but the logger context reader checks `"user_id"` / `"uid"` / `"user"`. Result: **every log line for a bcrypt-backend user logs `user_id=None`**. Audit rows are correct (they use `auth.current_user_id`), but the loguru context that supports grep-by-user is dead.
2. **🐛 `routers/search.py` has 4 silent `except Exception: pass` blocks** — Cmd+K global search returns empty results with no log, no audit, no breadcrumb. Worst kind of silent failure (user blames the keyboard).
3. **🐛 `auth_supabase.py` has 4 bare `except Exception:` swallows** — Supabase token exchange failures are invisible. A bad token lookup just returns "not authenticated" with no operator signal.
4. **🐛 404 HTTPException on legacy routers carries no `reason_code`** — `/pedidos/{id}` returns `detail="Pedido no encontrado"` (string) instead of `detail={"reason": "pedido_not_found", ...}`. The typed-error → header machinery is bypassed.

### Gaps (no infra yet — biggest leverage)
1. **`messages.py` is imported by exactly 1 of 13 routers.** 40+ Spanish (vos) constants exist; 12 routers still use inline string literals. Result: typos, inconsistent capitalization, no i18n escape hatch.
2. **`except Exception` total = 84 across 22 files.** Many are intentional ("non-fatal", "fail-open"), but no canonical pattern forces the developer to log + decide on every block.
3. **No "last-error-toast" UX on form pages.** POST errors currently render the global 500 page (acceptable) but field-level validation errors on inline forms (e.g. `add a quick product` modal) often only show browser-native bubbles. No site-wide inline-error component.
4. **No `errors.html` for AppError → browser.** Right now AppError 4xx returns JSON only; a browser GET to `/pedidos/9999` gets a JSON blob instead of a styled page.
5. **Sentry wiring exists (`main.py:135`) but `request_id` is not in `tags`.** A Sentry alert today says "InternalServerError" without the trace token that connects back to the in-app error page.
6. **No first-failure-archive on persistent logs.** `/tmp/uvicorn-d17*.log` rotates but loguru's stderr sink has no size cap → disk fills slowly over months. No daily-rotate file sink.
7. **`/healthz/errors` is read-only counts** but there's no proactive alert route — operator only finds out something is broken by checking.

---

## 📊 Inventory (numbers)

| What | Count | Where |
|---|---|---|
| `logger.*` calls | **45** | 18 files (mainly `main.py`, `seed.py`, `observability.py`) |
| `raise HTTPException` (raw, not typed) | **128** | 21 files (`sales.py` 14, `pedidos.py` 14, `excel_io.py` 11, `products.py` 10) |
| `except Exception` blocks | **84** | 22 files (`db.py` 27, `main.py` 10, `auth_supabase.py` 5, `health.py` 5) |
| Bare `except: pass` (no log) | **5 sites** | `search.py` ×4 (one per entity), `auth_supabase.py` ×1 |
| Routers using typed `AppError` | **5 of 22** | `auth.py`, `inventory.py`, `herebus.py`, `shopping.py`, `pedidos.py` (partial) |
| Routers using `messages.py` | **1 of 13** | only `herebus.py` |
| Audit rows written on write endpoints | partial — see §3 | 13 routers import audit but only 3 use the safe `record_audit()` helper |
| Health endpoints | **7** | `/healthz`, `/healthz/head`, `/healthz/db`, `/healthz/schema`, `/healthz/errors`, `/healthz/deps`, `/healthz/migrate` |

---

## 1. Are the existing messages fully explanatory?

### What I checked
Sampled ~40 `HTTPException` raises + the typed `AppError.message` strings + the
user-facing `messages.py` catalog + the rendered 500/404 templates + the
`?flash=...` query-string banners on success pages.

### Verdict — mostly fine, but inconsistent

**Good examples (typed errors with full context):**
- `errors.NotFound("pedido", id=42)` → `"pedido #42 no existe"`, reason `pedido_not_found`, 404.
- `messages.PEDIDO_MIN_ORDER_NOT_MET` → clear Spanish (vos).
- 500 page → "Tuvimos un problema procesando tu pedido" + click-to-copy request_id.

**Weak/poor examples (raw HTTPException, vague):**

| File:line | Message | Issue |
|---|---|---|
| `sales.py:427` | `"sku requerido"` | English. Inconsistent with rest of Spanish UI. |
| `sales.py:601` | `detail=str(e) from e` | Bubbles internal exception text to user — leaks implementation detail, sometimes in English (SQLAlchemy error). |
| `pedidos.py:466` | `f"Fecha inválida: {promised_date!r}"` | Shows raw user input wrapped in single quotes (Python repr). Could be cleaner as `"La fecha '{promised_date}' no es válida. Usá el formato YYYY-MM-DD."` |
| `validation.py` (23 sites) | short English phrases | The whole module is English; used as guard library, never localized. |
| `reportes.py:457` | `"Mes/año inválido"` | Doesn't say what's wrong OR what format is expected. |
| `sales.py:480-560` (8 raises) | mix of `f"Cantidad no puede ser mayor a {MAX_QTY}"` with no units, no link to the offending field | User has to guess what went wrong. |
| `merma.py:154,208,230` | `detail=str(exc) from exc` | Same leak problem. |

**Verdict:** the typed `AppError` + `messages.py` machinery is solid but only ~25% adopted. The remaining 75% are raw strings, often English, often leaking `str(exc)` from lower layers.

---

## 2. Tracking and monitoring — what's there

### 2a. Tracking (audit log) — partial

The `AuditLog` table is the only persistent event store. Coverage today:

| Action | Logged? | Where |
|---|---|---|
| `login.success` | ✅ | `auth.py` |
| `login.failure` + `login.rate_limited` | ✅ | `auth.py` + `rate_limit.py` |
| `http.500` (any unhandled error) | ✅ | `main.py:635` (audit written from exception handler) |
| `inventory.*` create/update/delete | ✅ | `inventory.py` via `record_audit()` |
| `shopping_list.*` | ✅ | `shopping.py` via `record_audit()` |
| `herebus.bank.add` / `wishlist.*` | ✅ | `herebus.py` via `record_audit()` |
| `sale.create` | ✅ (via `audit_record()`) | `sales.py:619` |
| `pedido.create/update` | ✅ (via `audit_record()`) | `pedidos.py:32` |
| `merma.register` | ✅ (via `audit_record()`) | `merma.py:179,233` |
| `production.*` | ✅ (via `audit_record()`) | `produccion.py` |
| `user.create` / `user.delete` | ⚠️ — line referenced but lazy-imported; verify in `users.py` | |
| `customer.create/update/delete` | ⚠️ — `customers.py:341,374` imports `record` but I didn't verify all calls | |
| `settings.update` | ✅ | `settings.py:190,229` |
| `eod.check` | ✅ | `eod.py:185` |
| `excel_import.*` | ✅ (partial) | `excel_io.py:29` |
| `healthz.*` calls | ❌ (intentional — would spam) | — |

### 2b. Monitoring (live health) — good

The 7 health endpoints give an operator everything they need to diagnose
without log access:
- `/healthz` → liveness + 503 during cold start
- `/healthz/db` → DB up + journal_mode + last audit timestamp + metadata
- `/healthz/schema` → schema drift detector (500 when DB < code)
- `/healthz/errors` → 1h/24h http.500 counts (great for "is it broken right now?")
- `/healthz/deps` → env fingerprint + package versions for Render debug
- `/healthz/migrate` → public migration trigger
- `/admin/migrate` → auth-gated migration trigger

### 2c. Live monitoring — only `/healthz/errors` is the operator signal

There is no Sentry or push-notification path. UptimeRobot can hit `/healthz`
but can't hit `/healthz/errors`. So an operator looking at a Render dashboard
only sees "app is up" — they have no signal that `/ventas` has been 500-ing
for 4 hours.

---

## 3. Silent failures (the worst category)

A "silent failure" = an `except` block that swallows the exception AND emits
no log AND no audit row. The user sees an empty result with no explanation.

### Top offenders

| File:line | What | Why it's bad |
|---|---|---|
| `search.py:63,84,118,139` | `except Exception: pass` × 4 (per-entity search) | User types in Cmd+K, sees nothing. No log. Operator can't even tell search is broken. |
| `auth_supabase.py:151,163,187,267` | `except Exception:` × 4 (Supabase session lookup) | Token validation failures invisible. User sees "login failed" with no operator signal. |
| `ops.py:85` | `except Exception: pass` (session.close in finally) | Low impact (just cleanup) but the `f"reset_demo_data failed: {exc}"` at line 81 leaks the full SQL error to the API client. |
| `db.py` (27 sites) | mostly intentional fail-open in migrations | Documented in `migrate()` code but each site should be tagged `# EXPECTED: <reason>` for future readers. |
| `health.py:159` | `except Exception: pkgs[pkg] = "NOT INSTALLED"` | Correct intent but masks ALL exceptions — including KeyboardInterrupt subclass bugs. Should be `importlib.PackageNotFoundError`. |

### How to detect more

A linter rule: ban `except Exception:` + bare `pass` in `app/routers/` (allow in
`app/rms/db.py` with a comment marker). This would have caught the search.py
issue at PR time.

---

## 4. Recommendations — what to do next

Ordered by leverage × effort. Effort estimates are `XS` (< 1h), `S` (< ½ day), `M` (1-2 days), `L` (> 2 days).

### P0 — fix the broken stuff first (1-2 days total)

1. **`observability._safe_get_user_id` — read the right session key.** XS.
   The fix: import `auth.LOCAL_SESSION_KEY_USER_ID` and check that key first.
   Add a regression test in `test_observability.py` that logs in via bcrypt
   and asserts the loguru context contains `user_id=<int>`.

2. **Convert `search.py` 4 swallows → log + return empty-with-breadcrumb.** XS.
   Replace `except Exception: pass` with `except Exception: logger.warning("search.<entity> failed q={!r}: {!r}", q, e)` and (optionally) set `results["<entity>"] = [{"error": True}]` so the JS can show "Búsqueda parcial" with a tooltip.

3. **`auth_supabase.py` — log the Supabase failure.** XS. Same pattern: `logger.warning("supabase auth lookup failed uid={!r}: {!r}", uid, e)` at all 4 sites. Bonus: add `audit_record(session, action="login.supabase_error", user_id=None, detail={"err": str(e)[:200]}, request=request)` so the operator sees it in /auditoria.

4. **Add `lifespan_startup_logs` to loguru file sink with size rotation.** S.
   Today stderr only. Add a 50MB × 7-day rotating file at `./logs/sazon-{date}.log` so an operator who wasn't watching when the 500 happened can still pull the day. Crucial for a once-a-week baker who only opens the app briefly.

### P1 — extend the good infra to the remaining 75% (1-2 weeks)

5. **Wire `messages.py` into all routers.** M.
   Mechanical: replace the ~120 raw `detail="..."` strings with `messages.<CONST>`. The catalog already has 80% of what's needed; add ~20 more (customer.email_required, sale.max_qty_exceeded, etc.). This is the single highest-leverage cleanup: it gives you free i18n if you ever need to support a second language, and it forces every error message through review.

6. **Convert the remaining `raise HTTPException` → typed `AppError` raises.** M.
   Same pattern as the 2026-09-23 audit but for `sales.py`, `pedidos.py`, `excel_io.py`, `products.py`, `recipes.py`, `reportes.py`. Every conversion should add a `reason_code` (snake_case, unique per failure mode) so `X-Reason-Code` headers propagate to API clients and `/healthz/errors` can group by reason.

7. **HTML error template for 4xx AppError on browser routes.** S.
   Right now `NotFound` returns JSON only. Browsers hitting `/pedidos/9999` get a JSON blob. Extend the existing `errors/404.html` to also serve 400/403/409 from `errors/<code>.html` — render the `message` in Spanish, the `reason_code` for support, and a "Go back" button. Reuses the 500 template pattern.

8. **Sentry `request_id` tag.** XS.
   `sentry_sdk.set_tag("request_id", rid)` in the exception handler before the Sentry capture. Two lines; turns Sentry alerts from "InternalServerError" into "trace me via X-Request-Id".

### P2 — make monitoring proactive (1-2 weeks)

9. **Wire `/healthz/errors` into UptimeRobot via a derived status.** S.
   Today UptimeRobot hits `/healthz` (200/503 only). Add `/healthz/errors?threshold=10` that 503s when 1h http.500 count > threshold. Operators get a Slack alert before a user notices.

10. **First-failure-toast component.** M.
    A `<ui-toast>` web component that listens on a `<div id="flash-data" data-flash='{"kind":"error","msg":"..."}'>` injected by every template. Today success uses `?flash=` query string; failures render the 500 page. Inline-form failures (e.g. submit a modal that fails) currently just disappear. The component would: read flash on load → show toast for 5s → dismiss. Reuses existing pattern.

11. **Audit-log analytics page.** L.
    The `AuditLog` table has months of data nobody queries. Build `/auditoria/analytics` with: failed-login heatmap by hour, top-10 most-mutated entity types, login-IP geo summary (Cloudflare `cf-ipcountry` header). Reference: `BACKLOG.md #30`.

12. **Daily log rotate + archive to R2.** M.
    The R2 backup scheduler already runs nightly. Extend it to also ship yesterday's `sazon-{date}.log` to R2 with the same encryption. 90 days online, 1 year in cold storage. Pairs with #4.

13. **Linter: ban bare `except: pass` in `app/routers/`.** XS.
    Add a `ruff` custom rule (or a pre-commit grep). Catches the next `search.py`-style silent failure at PR time. Document exception in `app/rms/db.py` with `# EXPECTED: <reason>` markers so reviewers can `git grep EXPECTED`.

### P3 — nice-to-have

14. **OpenTelemetry traces.** L. Adds `trace_id` to every log line for cross-service stitching. Only worth it if you add another service.

15. **Rate-limit on read endpoints (currently only writes + auth).** S. `/ventas/export.csv` and `/auditoria` are uncapped scrapers today. Reference: `BACKLOG.md #10`.

16. **End-user "What happened?" link from 500 page → operator phone/email.** XS. The 500 template has the expandable section but no contact button. Add a `mailto:` link with the request_id pre-filled in the subject.

17. **`X-Reason-Code` propagation through redirects.** S. When a POST handler returns `RedirectResponse(url=..., status_code=303)`, the reason never reaches the next page. Add a `?err=...&rid=...` query string for 303s that started from an AppError, and a small banner on the destination.

---

## 5. Concrete first PR (≤ 4 hours of work, fixes 4 of the 17 items)

Combines items **1 + 2 + 3 + 8** above. Touches 4 files:

- `app/rms/observability.py` — fix `user_id` lookup + import the constant.
- `app/routers/search.py` — replace 4 `except: pass` with structured warnings.
- `app/auth_supabase.py` — replace 4 bare `except` with warnings + audit.
- `app/rms/main.py` — add `sentry_sdk.set_tag("request_id", rid)` in exception handler (2 lines).

Plus a single test in `tests/test_observability.py` that logs in via bcrypt
and asserts the captured log line includes `user_id=<int>`.

This is the smallest change that turns the existing observability machinery
from "infrastructure we have" into "infrastructure that catches the next
real bug." After this lands, items 5, 6, 7 become mechanical rollouts.

---

## 6. Files referenced

- `app/rms/errors.py` — typed exception hierarchy (180 lines)
- `app/rms/observability.py` — request-id middleware + `record_audit()` (159)
- `app/rms/messages.py` — user-facing Spanish constants (105)
- `app/rms/main.py` — global exception handler (820)
- `app/rms/audit.py` — audit log writer (176)
- `app/routers/health.py` — 7 health endpoints (391)
- `app/rms/rate_limit.py` — sliding-window limiter (186)
- `app/rms/notifications.py` — Twilio/SMTP delivery (288)
- `app/templates/errors/500.html` + `404.html` — user-facing error pages
- `OBSERVABILITY_AUDIT.md` — the 2026-09-23 audit this builds on

---

## 7. Verdict for Iván

The app is **already substantially better than most FastAPI codebases of
similar size** — request-id propagation, typed exception hierarchy, structured
reason_codes, and 7 health probes are above-the-bar work from the
2026-09-23 audit.

What's left is **finishing the rollout**: 75% of routers still use raw
HTTPException, the message catalog is unused by 12 of 13 routers, and there
are 4 known silent-failure sites that nobody noticed because there's no
alert on them.

The fix in §5 (first PR) is 4 hours of work and removes the worst silent
failures. Everything else is mechanical cleanup that compounds value every
time someone hits an error.

I'd recommend: ship the §5 PR, then queue §6 (rollout messages.py + typed
errors) as a single follow-up epic over the next sprint. The P2 monitoring
items (#9-12) become worth it once the operator is daily-active and we'd
actually notice the gap.
