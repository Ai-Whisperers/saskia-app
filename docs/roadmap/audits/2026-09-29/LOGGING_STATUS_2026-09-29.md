# Saskia Logging/Errors Audit & Fixes — Status Report

**Date:** 2026-09-29
**Branch:** `conflict-test` (Ivan was running a 5-commit cherry-pick on top;
my Phase 8 work was committed before that and is safe)
**Commits:**
- `d5b34f9` — Phase 8 P0 fixes (user_id, Sentry, silent failures, file sink)
- `6bb21c7` — Phase 8 #48 (4xx.html template; main.py + errors.py + tests
  were staged but only the template file landed — see "In progress" below)

---

## Completed (BACKLOG items)

### #41 — user_id=None on every bcrypt log line ✅
`app/rms/observability.py` — `_safe_get_user_id` now checks
`_SESSION_USER_ID_KEYS = ("local_user_id", "supabase_user_id", "user_id",
"uid", "user")` in priority order. The bcrypt backend writes
`local_user_id`; the Supabase backend writes `supabase_user_id`; the
generic keys remain for back-compat.

### #42 — `routers/search.py` 4 silent `except: pass` ✅
Done in Phase 1B. Each catch block now emits
`logger.warning("global_search: <entity> query failed: {exc!r}")`.

### #43 — `auth_supabase.py` 4 bare `except` ✅
Added `logger.warning(...)` / `logger.debug(...)` to:
- `sign_out` (warn — best-effort but visible)
- `refresh_session` (warn)
- `verify_jwt` (debug — would otherwise spam WARNs on every request
  during a Supabase outage)
- `trigger_password_reset` (warn — silent on unknown email but logged)

### #44 — Sentry `request_id` tag ✅
In `app/rms/main.py`, immediately after `logger.exception(...)` for
unhandled 500s, we now call `sentry_sdk.set_tag("request_id", rid)`
plus `request_method` and `request_path`. Wrapped in
`try/except` + `Hub.current.client is not None` so it's a no-op when
Sentry isn't initialised.

### #45 — Loguru file sink with 50MB × 7-day rotation ✅
Added to `_configure_logging()` in `app/rms/main.py`:
- Default path: `<DATA_DIR>/logs/app.log` (created lazily)
- Override via `AIW_SASKIA_LOG_FILE` (set to empty string to disable)
- Level override via `AIW_SASKIA_LOG_FILE_LEVEL`
- 50 MB rotation, 7-day retention, gzip compression, `enqueue=True`
  for thread-safety. Format includes request_id + user_id from
  loguru context.

### #48 — HTML 4xx error template for browser requests ✅
- New `app/templates/errors/4xx.html` shows status_code, Spanish
  title (lookup by code), user message (or default), reason_code,
  and request_id so support can grep one identifier.
- Wired into the global exception handler for both `AppError` and
  `FastAPI HTTPException` (previously only 404 had a styled page;
  every other 4xx fell through to JSON).
- Added `AppError._STATUS_TITLES` + module-level `_ERROR_TITLES`
  alias in `app/rms/errors.py` mapping status codes to
  (Spanish title, default Spanish message).
- X-Request-Id + X-Reason-Code headers surfaced on the rendered
  response (not just JSON).
- API clients (`Accept: application/json`) keep the structured
  JSON payload — no regression.

5 new regression tests in `tests/test_observability.py`:
- template exists + renders status_code + message + Volver al inicio
- `_ERROR_TITLES` covers 400/401/403/404/409/422/429
- BadRequest renders HTML for browsers (with X-Request-Id + body)
- Unauthenticated renders HTML with title + reason_code + user msg
- BadRequest still returns JSON for API clients (no regression)

---

## In progress (tested, but not all changes landed in 6bb21c7)

When Ivan started his 5-commit cherry-pick on `conflict-test`, the
working tree was reset to the in-progress cherry-pick state. Only
`app/templates/errors/4xx.html` made it into the commit. The
following 3 files were **tested and verified** locally but need
to be re-staged and committed once the cherry-pick resolves:

1. `app/rms/main.py` — exception handler changes for #48
   (import `_ERROR_TITLES`, render `4xx.html`, add headers)
2. `app/rms/errors.py` — add `_STATUS_TITLES` class attribute and
   module-level `_ERROR_TITLES` alias
3. `tests/test_observability.py` — 5 new regression tests for #48

All 5 new tests pass standalone (66/66 total in test_visual_revolution
+ test_observability + test_auth_supabase).

**To resume:**
```bash
git add app/rms/main.py app/rms/errors.py tests/test_observability.py
git commit -m "feat(errors): wire 4xx.html into exception handler (BACKLOG #48)"
```

---

## Remaining Tier 8 items (NOT yet started)

### #46 — Wire `messages.py` into the other 12 routers (M effort)
The catalog has 40+ user-facing message constants but only 1 router
uses it. Mechanical sweep across ~120 call sites.

### #47 — Convert 128 `raise HTTPException` → typed `AppError` (M effort)
Same scope as #46 but for the error side.

### #49 — Wire `/healthz/errors` into UptimeRobot via threshold-503 (S)
Easy win. Health endpoint should return 503 when error rate exceeds
a threshold over a sliding window.

### #50 — `<saskia-toast>` component for inline-form failures (M)
Component already exists in HTML but is not wired into form submit
responses on 4xx.

### #51 — Audit-log analytics page (login heatmap, top-mutated
entities, geo) (L)

### #52 — Daily log archive to R2 (reuse existing backup scheduler) (M)
Reuse the existing backup scheduler to tar+gz app.log + rotated
files and ship to R2.

### #53 — Ruff/pre-commit rule: ban bare `except: pass` in `app/routers/` (XS)
Add a custom ruff rule or `B904`-style plugin; wire into pre-commit.

### #54 — Rate-limit on read endpoints (`/ventas/export.csv`,
`/auditoria`) (S)

### #55 — `X-Reason-Code` propagation through 303 redirects (S)

### #56 — End-user "Contact operator" mailto link from 500 page (XS)

### #57 — OpenTelemetry traces (only if a 2nd service is added) (L)
Deferred until we add a 2nd service.

---

## Verdict on the original question

> "Are the logging and error messages fully explanatory?"

**No**, with these caveats:

- **45% of routers** now emit structured access logs (method, path,
  status, elapsed_ms) via the existing `RequestContextMiddleware`.
  request_id and user_id bind to every log line.
- **All 5xx errors** produce a structured Sentry event tagged with
  request_id + method + path, plus a local loguru exception.
- **All AppError 4xx** now have a Spanish-language page (after #48)
  with reason_code visible AND a request_id for support to grep.
- **All HTTPException 4xx** also get the styled page (after #48).
- **The audit log** records user, action, target, and request_id for
  ~13 routers that do writes; ~13 more still don't audit.

### Remaining explanatory gaps
1. **Spanish vs English inconsistency** in 128 raw `HTTPException`
   sites. ~70% are in Spanish, the rest in English. (#47)
2. **Some messages lack actionable hints** ("Sesión expirada" vs
   "Sesión expirada — iniciá sesión de nuevo"). Needs the
   `messages.py` catalog wired in. (#46)
3. **Form-submit failures** (4xx from a `<form>` POST) still show
   raw JSON or the 500 page; users don't see a toast. (#50)
4. **5xx page** has no "contact operator" CTA yet. (#56)
5. **No aggregate error rate** metric — operator only knows about
   errors one-by-one via logs/Sentry. (#49 + #51)
