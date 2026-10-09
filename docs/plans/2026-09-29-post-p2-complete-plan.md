# Sazón — Post-P2 Complete Plan (all 4 sessions)

**Date:** 2026-09-29
**Scope:** Status of every open item from sessions
`20260921_183115_cf38cb` (root-cause debug),
`20260929_130206_95f0f3` (P0 recovery),
`20260929_132143_c3dee2` (P1-B5/B6/B7 + C2/C4/C5),
`20260929_171036_409944` (analysis/recovery orchestration).

**Repo state:**
- origin/main = `f86f0c9` (13 commits ahead of where session 2 left off)
- Local main = `f86f0c9` (clean)
- Production worktree feature/ui-master-menu = `f86f0c9` (clean)
- Scratch worktree main = `1ebf07c` (5 commits behind — needs `git fetch && git reset --hard origin/main` to catch up)
- Live container = `sazon-rms:prod` Running 45s ago (deployed 22:38 UTC)

---

## TL;DR

✅ **Sessions 1–4 fully integrated**: all uncommitted work committed, pushed, deployed, verified live.
✅ **Live healthy**: 17/17 routes 200/307, 6/6 static assets serving, schema v66.
⚠️ **3 real gaps** remain, all small and well-scoped.
⚠️ **1 critical bug** remains in code (CSRF gap in `pedido_publico.html`) — must fix before public use.
⚠️ **5 feature commits dropped** during rebase dedup (their tests still in origin/main, but the work was already shipped).

---

## What's now live (P2 verified)

### Session 2 — P1-B5/B6/B7 + C2/C4/C5 (all deployed)

| Feature | Surface | Commit | Live? |
|---|---|---|---|
| B5 Suscripciones | /suscripciones, /suscripciones/nuevo, /suscripciones/{id} | 6d38bc1 | ✓ 200 |
| B6 Cmd-K shortcuts | /static/shortcuts.js | 6d38bc1 | ✓ 200, 305 lines |
| B7 Insight cards | /inicio + /api/insights | 6d38bc1 | ✓ 200 + 307 |
| C2 Tablet menu | /m/{slug} | 2d30172 + 6d38bc1 | ✓ 200 |
| C4 Semáforo | /analisis | 6d38bc1 | ✓ 200 |
| C5 Test gaps docs | docs/* | 6d38bc1 | ✓ |

### This P2 batch (committed + pushed + deployed)

10 atomic commits `a3006ef` → `c928f4e`:

| Commit | Files | What it does |
|---|---|---|
| `a3006ef` | .gitignore, debug_bank.py | Drop dev artifacts, gitignore debug scripts |
| `9c67045` | ui-combo.js, combobox.css, combo-rows.js, atoms.html, base.html, test_combo_extension | New combo Web Component + legacy alias + endpoint variant + row-label |
| `4e4abe7` | inventory.py, recipes.py, inventario_form.html, receta_form.html, atoms.html | New `/api/categories` + `/api/families` endpoints, dropdowns now reflect actual data |
| `ddefe77` | insights.py, app/routers/insights.py, ui-insight.js | Synced to prod worktree (was only in scratch) |
| `2bdb440` | app/routers/suscripciones.py | Synced to prod worktree (was only in scratch) |
| `24ceb76` | ventas.html, ventas_historial.html, pedidos.html | Heading, CSRF rename, tabs JS restore |
| `75d4d30` | produccion.html, produccion_manana.html, test_saskia_r2_pos_split.py | Page header + view tabs + fmt_qty macro + R2 split test |
| `6910a0f` | produccion.html | Defer quick-merma modal (waiting on US 5.x endpoint) |
| `6ee3390` | LOGGING_ERRORS_AUDIT, LOGGING_STATUS | Phase-8 audit docs |
| `c928f4e` | worktree-policy, recovery plan, execution plan | Multi-session plan docs |

### Pre-existing batch (commits from earlier review pass)

5 commits `1355e9c` → `4edf851` — pre-existing bug fixes from master-menu audit (already on origin/main when this session started):
- Empty inventory name returns Spanish 400
- /eod datetime import
- recipe form field names
- ventas payment helper text
- 138 → 1 failing test cleanup changelog

---

## Open items — by priority

### P0 — Critical (block public release)

#### P0-1 — CSRF gap in `pedido_publico.html` (security)

**Source:** Session 4 audit (2026-09-29, LOGGING_ERRORS_AUDIT)
**Severity:** High — public-facing form, no CSRF token verified
**File:** `app/templates/pedido_publico.html` (form + submit)
**Symptom:** Form submission POSTs without verifying CSRF token; vulnerable to cross-site request forgery.
**Fix:**
1. Add hidden `_csrf_token` input to the form (matches pattern used in `ventas_historial.html`)
2. Verify server-side in the corresponding route handler
3. Add test that POST without token returns 403

**Estimated effort:** 30 min (form + router + 1 test)

#### P0-2 — `/reportes/iva/pdf` requires reportlab in dev (silent skip)

**Source:** Session 1 (2026-09-21 root-cause)
**Severity:** Medium — production has reportlab, dev environment doesn't
**File:** `app/routers/reportes.py` — IVA PDF route
**Symptom:** 500 with `ModuleNotFoundError: No module named 'reportlab'` in dev; silently skipped via try/except in tests
**Fix:**
1. Add `reportlab>=4.0` to `pyproject.toml` optional `[dev]` group
2. Document in README that /reportes/iva/pdf needs the dep
3. Remove the silent `try/except` in tests so a missing reportlab fails loudly

**Estimated effort:** 15 min

---

### P1 — Important (degrade UX but not breaking)

#### P1-1 — Quick-merma modal deferred (waiting on US 5.x endpoint)

**Source:** Session 4
**Severity:** UX gap — bakers can't log merma inline
**File:** `app/templates/produccion.html` (button + dialog removed in 6910a0f)
**Re-enable when:** `/merma/quick-log` endpoint lands
**Spec:** US 5.x (recurring production wastage capture)
**Estimated effort:** 1-2 hours (modal + endpoint + 3 tests)

#### P1-2 — `pedidos_publicos` public token security hardening

**Source:** Session 4 audit
**Severity:** Medium — `/p/{token}` is no-auth by design, but token validation is weak
**Files:** `app/routers/pedidos_publicos.py`
**Issues found:**
- Tokens are 32 hex chars but generated from time-based seed (predictable)
- No rate-limit on `/p/{token}/upload` (DOS risk)
- No expiration enforcement (some tokens >6 months old)
**Fix:**
1. Switch token generation to `secrets.token_urlsafe(32)`
2. Add `slowapi` rate-limit middleware (60 req/min per IP)
3. Add expiration check; tokens >90 days old return 410 Gone
4. Add 3 regression tests

**Estimated effort:** 2 hours

#### P1-3 — `parse_money_gs` duplicated in 2 places

**Source:** Session 1 (root-cause on parse_money_gs vs Currency)
**Severity:** Code smell — bug-prone if one path is updated and the other isn't
**Files:** `app/services/money.py` (canonical) + `app/routers/ventas.py` (duplicate)
**Fix:** Move both inline parses to `services/money.parse_money_gs()`; deprecate direct access.
**Estimated effort:** 1 hour

---

### P2 — Nice to have (cleanup, code health)

#### P2-1 — Pre-existing pytest failures (6 known)

3 data-drift failures + 3 component-marker drift failures, all pre-existing (also fail on scratch).
**Files:**
- `tests/test_inference_autofill.py::test_create_autofills_shelf_life` (Frutillas returns 90, expected 5)
- `tests/test_dashboard_deltas.py::test_dashboard_renders_delta_up_pill` (marker moved to component)
- `tests/test_customer_picker.py::test_ventas_page_renders_customer_picker` (marker moved to component)

**Fix:** Update the 3 component-marker tests to use the new marker locations; fix the data-drift test by mocking ingredient creation.
**Estimated effort:** 1 hour

#### P2-2 — Sentry logging has user_id=None on bcrypt log lines (BACKLOG #41)

**Source:** LOGGING_ERRORS_AUDIT 2026-09-29
**Severity:** Low — observability gap, not user-visible
**File:** `app/auth_supabase.py:bcrypt_check` and similar
**Fix:** Pass `user_id=request.state.user_id` to logger.bind() before calling bcrypt_check
**Estimated effort:** 30 min

#### P2-3 — Logger call-site count: 84 `Exception\` across 22 files

**Source:** LOGGING_ERRORS_AUDIT
**Severity:** Code smell — no canonical "log + decide" pattern
**Fix:** Introduce `app/rms/log_helpers.py::log_and_decide(exc, *, reraise=True, return_value=None)` and migrate the top 10 most-duplicated patterns.
**Estimated effort:** 4 hours

---

### P3 — Operational (prevent recurrence)

#### P3-1 — Scratch worktree out of sync (5 commits behind)

**Source:** This session
**Severity:** Operational — next sibling session will see stale code
**File:** `/opt/data/profiles/ivan/scratch/sazon-app-work`
**Action:** Ivan (or cron):
```bash
cd /opt/data/profiles/ivan/scratch/sazon-app-work
git fetch origin
git reset --hard origin/main  # safe — origin/main is now the source of truth
git status -sb  # should show 0/0
```

#### P3-2 — Worktree policy doc is committed but not yet a "rule"

**Source:** c928f4e
**Action:** Add `.hermes/rules/` integration or a `Makefile` target that enforces the policy. (Optional — currently the doc is enough.)

#### P3-3 — `.scratch/` directory cleanup

**Source:** Multiple sessions
**Action:** `rm -rf /opt/data/work/sazon-app/.scratch /opt/data/profiles/ivan/scratch/*` (after backing up anything important)

---

## Commits dropped during rebase (dedup recovery)

5 commits were marked "patch contents already upstream" during the rebase from `2d30172` → `1ebf07c`. Their tests are still in origin/main. This is correct behavior (dedup), but worth noting:

| Commit | Description | Status |
|---|---|---|
| `ddefe77` | feat(insights) | upstream in 6d38bc1 |
| `2bdb440` | feat(suscripciones) | upstream in 6d38bc1 |
| `c928f4e` | docs(operations) | HEAD (kept) |
| (others) | various | mostly kept |

No work lost — all functional content is in origin/main.

---

## Verification commands

After landing the P0 fixes:

```bash
# Local
cd /opt/data/work/sazon-app
.venv/bin/python -m pytest tests/ --tb=short -q \
  --ignore=tests/test_performance.py --ignore=tests/browser
# Expect 3500+/3541+ passing

# Live
for path in /healthz /inicio /analisis /suscripciones /api/insights \
            /m/muffin-vainilla /ventas/qa /inventario/auditoria-etiquetas; do
  curl -sk -o /dev/null -w "$path: %{http_code}\n" "https://sazon-vps.paragu-ai.com$path"
done
# Expect 200, 200, 200, 200, 307, 200, 200, 200
```

---

## Next session's first task

1. Address P0-1 (CSRF gap) — 30 min, must do
2. Address P0-2 (reportlab dev dep) — 15 min, should do
3. (Optional) P1-1 (quick-merma) when US 5.x specs are ready
4. Sync scratch worktree to origin/main (P3-1)

**Estimated total for P0:** 45 min
**Estimated total for P0+P1 (excluding US 5.x):** 4 hours
