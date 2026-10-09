# Plan — Quick-merma from /produccion + /merma page collapse

**Branch:** `feat/prod-quick-merma` (off `main`@67b2cc7)
**Date:** 2026-09-30
**Owner:** Hermes (dev team)
**Estimate:** 2-3h

## Goal
Move waste-logging context to where waste happens (`/produccion`). Add a per-row "🔥 Merma" trigger in the daily shift-execution table that opens a 2-tab modal (ingrediente suelto | lote entero). Collapse `/merma` to its analytical + single-ingredient role; remove the recipe card from it.

## Tickets

### T1. Production-context quick-merma modal
- **What:** Add `<dialog id="quick-merma-modal">` to `app/templates/produccion.html`, mirroring `adhoc-modal` style.
- **Tabs:** "Ingrediente suelto" (qty + unit + motivo + nota) | "Lote entero" (recipe preselected + batch_qty + motivo + nota).
- **Per-row trigger:** new "🔥 Merma" button in shift-execution table (next to "Ver receta"), populates the modal's hidden `recipe_id` / `product_id` fields via JS.
- **Submit:** POST to existing `/merma/registrar` (ingredient tab) or `/merma/receta` (recipe tab). No new backend endpoints.
- **Flash:** `/produccion?merma=ok&lines=N` shows green "✓ Merma registrada (N)" banner after redirect.

### T2. /merma page collapse
- **Remove:** recipe card from `app/templates/merma.html` (the "Merma de receta completa" `<section>`).
- **Add:** explanatory callout card: *"Perdiste una tanda entera? Registrala desde /producción → botón 🔥 Merma"*.
- **Keep:** ingredient card, summary card, eventos log, date filters, motivos API.

### T3. Audit source tagging
- **What:** Add `source: "production"` to the `detail` dict in `record_audit(...)` calls in `app/routers/merma.py`.
- **Why:** Lets the eventos log on `/merma` show "📍 Producción" badge vs "✍️ Manual" — operator can see where each event was reported from.
- **LOC:** ~3 lines (in both `merma_register` and `merma_register_recipe`).

### T4. Production-side missing-loss prompt
- **What:** Pure-JS, no DB. After shift-save submit, when `completed_qty < qty_to_produce` for any row, show inline prompt: *"N unidades sin registrar — registrarlas como merma?"* with one-click button that opens `quick-merma-modal` preloaded with the deficit.
- **LOC:** ~30 lines JS in `produccion.html`.

## Tests (TDD)

| File | Tests |
|---|---|
| `tests/test_quick_merma_modal.py` | POST `/merma/registrar` from `/produccion` context round-trip + redirect + stock decrement + audit `source: production` |
| `tests/test_merma_page_removed_recipe.py` | `/merma` HTML no longer renders recipe form; still renders ingredient form; renders callout pointing to `/produccion` |
| `tests/test_produccion_merma_flash.py` | `/produccion?merma=ok&lines=N` shows banner; `lines=N` matches merma event count for that day |
| `tests/test_produccion_quick_merma_button.py` | "🔥 Merma" button renders per row; data-recipe-id populated; modal opens |

## Verification ladder

1. Write all 4 tests → RED ✓
2. Implement T1 + T2 + T3 → GREEN ✓
3. Implement T4 (JS prompt) → manual browser verify ✓ (auto-fires when shift-saved + completed<target)
4. `uv run pytest -q` → no regressions vs current baseline ✓ (199/199 in focused suite)
5. `ruff check . && ruff format --check .` ✓ (4 files reformatted, lint clean)
6. `docker build --no-cache` (template change forces fresh image) ✓ (5026baaf47c5)
7. `md5sum` check on new image vs local ✓ (all 3 file hashes match: produccion.html, merma.html, merma.py)
8. `docker service update --force --detach=false saskia-vps_web` ✓ (converged in 21s)
9. Health-probe: t+0=404 (CF tunnel stale, predicted), t+30=200, t+90=200 ✓
10. Live-test: live container `533a3b2dd7b1` serving new md5s ✓

## Deploy record

- Branch: `feat/prod-quick-merma` @ `cd9b71b`
- Image: `saskia-rms:prod` (5026baaf47c5) — built with `DOCKER_BUILDKIT=0 docker build --no-cache`
- Service: `saskia-vps_web` (1/1 replicas, converged)
- Backup: `saskia-rms.bak.20260930_173454` (pre-deploy snapshot, kept on VPS)
- Public URL: https://saskia-vps.paragu-ai.com/merma, /produccion — both live with new code
- Operator smoke test recommended: login → /produccion → click 🔥 Merma on any row → submit ingrediente suelto → confirm stock decrement + green flash banner → check /merma shows new event in eventos log with 📍 Producción badge (when filtered)

## Risks / Decisions

- **Recipe preselect on row trigger:** locked (operator can change inside modal but pre-filled to row's recipe).
- **/merma recipe card kept as historical entry path?** No — operators navigate to `/produccion?view=day&date=YESTERDAY` instead. Easy to revert.
- **Audit `source` field:** backward-compatible addition (`source` is new key, doesn't break existing detail readers).