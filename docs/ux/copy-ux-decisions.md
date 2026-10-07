# Sazon Copy/UX Hardening — Decisions & Plan (v3, repo-informed)

**Date:** 2026-10-07
**Branch:** `feat/SASKIA-301-copy-globals`
**Status:** Phase 0 ready to start

## Decisions made after analyzing the live repo

### D1. Style guide authority: fix `copy-vos.md`, don't just follow it

`app/docs/copy-vos.md` line 15 says `Save | Guardá`. That's **Argentine voseo**, not Paraguayan. The correct Paraguayan convention is:

- **Buttons:** infinitive (`Guardar`, `Cancelar`, `Editar`, `Eliminar`). `Guardar` is universal and clear in PY Spanish.
- **Empty states / hints:** Paraguayan voseo imperative or `vos`-conjugated. The actually-canonical PY form for commands with "vos" is: `Guardá` (1 syllable, stressed) for very common verbs, OR `Guardá el archivo` is the standard imperative. The forms `Tocá`/`Hacé`/`Buscá`/`Cargá` are 2nd-person-imperative with stress-shift — they're shared between PY and AR for the "tú-attached voseo" zones. **The KEY differentiator is the -s ending for non-stressed forms: `tenés` (not `tené`), `querés` (not `queré`), `sabés` (not `sabé`).** All of these ARE used in the current templates correctly.
- **Buttons that are NOT 1st-imperative voseo** should be infinitive.

**Verdict:** Buttons say `Guardar` (infinitive). Hints/empty states use the vose forms already in the codebase. We will NOT mass-replace `Tocá`/`Hacé`/`Buscá`/`Cargá` (they're fine). We WILL replace `Guardá`/`Decí`/`Salvá` in **buttons and primary action labels** (where infinitive is the Paraguayan+AR+neutral universal) with `Guardar`/`Indicar`/`Guardar`.

`copy-vos.md` line 15 will be fixed to say `Save | Guardar` as part of SASKIA-310 (glossary).

### D2. Phase 0 scope: more than originally estimated

Actual count from grep on the working tree:

| Bad pattern | Files | Original estimate | Actual |
|---|---|---|---|
| `Guardá` (button text) | ingrediente_detalle, inventario_form, pedido_publico, produccion (×2), produccion_manana (×2), produccion_print, producto_form, supplier_form, suscripcion_form | 2-3 | **11** |
| `Loyalty` (UI text) | cliente_detalle, inicio, ops_status | 1 | **3** |
| `₲` (Unicode guaraní) | eod_print, ops_status, reportes_mermas_cost, suppliers_volatility | 4 | **4** (correct) |
| `Batches` (UI) | insight_demand | 1 | 1 |
| `Revenue` (UI) | reportes_top_productos | 1 | 1 |
| `COGS` (UI) | reportes_diario, reportes_valor_pedido | 1 | **2** |
| `Lotes` (in production context) | planner, cotizador | 2 | 2 |

The expanded scope adds ~2 hours to Phase 0 (most of the extra work is `Guardá` → `Guardar` which is mechanical).

### D3. Phase 8 (errors) scope shrinks

`errors/500.html` is already safe — it shows a friendly "Algo salió mal" + `request_id` for support. It does NOT leak stack trace, DB info, or secrets. The P0 "leakage" concern is moot.

What SASKIA-309 (Phase 8) WILL do:
- Add a regression test that asserts `errors/500.html` source does NOT contain "traceback" / "Traceback" / "File \"" / `app/` paths / "sqlite" / "SQLAlchemy" / "schema" / "password" / "secret" / "key=" / "token" / "auth_"
- Verify `errors/404.html` and `errors/4xx.html` are also safe (same check)
- That's it. No template edits needed unless the test finds a leak.

### D4. Worktree + sibling recovery

The repo has only one worktree on this filesystem (`/opt/data/work/saskia-app`). The worktree-policy.md mentions a "scratch" worktree at `/opt/data/profiles/ivan/scratch/sazon-app-work` that doesn't exist here. So:

- **The repo at `/opt/data/work/saskia-app` is the active worktree**, on `main`.
- **SASKIA-207 had uncommitted files** (stock_ledger.py, test, audit doc) + uncommitted edits (waste.py, herebus.py, shopping.py, .xlsx).
- **My recovery move:** commit the new files to a recovery branch, then merge into my feature branch. The uncommitted edits to waste.py/herebus.py/shopping.py STAY in the working tree for the sibling to land when it resumes.
- **The uncommitted .xlsx change** is binary same-bytes — likely a phantom diff. I'll leave it for the sibling.

### D5. No direct main push (per worktree policy)

Even though I have no separate scratch worktree, the policy says "no direct main push — feature branch + PR only." So I will:

1. Work entirely on `feat/SASKIA-301-copy-globals` (already created, with SASKIA-207 recovery merge)
2. Open a PR when Phase 0 is done
3. After PR merge, Phase 1 etc on new branches

### D6. Test naming

Use `test_SASKIA-3NN_<slug>.py` matching the existing `test_SASKIA-205_*.py` / `test_SASKIA-206_*.py` / `test_SASKIA-207_*.py` convention. (My original plan already had this; no change.)

### D7. Migration policy: NO new migrations in Phase 0

All Phase 0 changes are string-level. No schema changes. The only `apply_stock_delta()` consumer in this phase would be in Phase 4 (inventario) and we should defer that — the sibling's SASKIA-207 work covers waste.py already; production.py changes are a separate concern.

### D8. Copy-vos.md update is part of Phase 9 (SASKIA-310)

We fix `copy-vos.md` line 15 (`Guardá` → `Guardar`) in SASKIA-310, the final phase. This way the style guide and the code converge simultaneously, and the CI gate can prevent regression.

## Phase 0 (SASKIA-301) revised scope

| Step | Work | Files | Test file |
|---|---|---|---|
| 0.1 | `₲` → `Gs.` in 4 templates (eod_print, ops_status, reportes_mermas_cost, suppliers_volatility) | 4 templates | `test_SASKIA-301_currency_gs.py` |
| 0.2 | `Loyalty` → `Fidelización` in 3 templates (inicio, cliente_detalle, ops_status) | 3 templates | (folded into 0.3) |
| 0.3 | 15+ English loan words in column headers, labels, tooltips | 12+ templates | `test_SASKIA-301_loan_words.py` |
| 0.4 | `Guardá` → `Guardar` in 11+ buttons | 11 templates | `test_SASKIA-301_register.py` |
| 0.5 | Severity pill `saludable` → `OK` in inicio.html | 1 template | `test_SASKIA-301_severity.py` |
| 0.6 | Column header `Gs` → `Gs.`, placeholder `25000` → `25.000` | 2 templates | `test_SASKIA-301_columns.py` |
| 0.7 | Redundant `aria-label="Cerrar"` on close buttons | 5 templates | `test_SASKIA-301_tooltips.py` |

**Total Phase 0: ~5-7 hours focused work. ~50 tests in 6 test files.**

## Open risks (revisited with current info)

- **Uncommitted sibling work (waste.py/herebus.py/shopping.py/.xlsx)** — my Phase 0 doesn't touch any of these. The sibling's `waste.py` imports from `app.rms.stock_ledger` (now on my branch via the recovery merge), so the import will resolve. If the sibling lands their changes AFTER I land Phase 0, there could be a merge conflict on the import statement. Mitigation: don't touch `waste.py` in Phase 0. If conflict, rebase.
- **CI coverage gate (35%)** — copy/UX tests are template-only and don't improve coverage, but also don't tank it. Test will run with the same coverage calculation as today.
- **Pre-commit hook runs `pytest-smoke`** — my new test files should be marked `pytest.mark.smoke` so they run in the pre-commit gate.
- **SASKIA-310 glossary/CI gate** is the last phase. It's the only phase that could fail at the END (if any forbidden pattern slipped through).

## Ready to start

Phase 0 step 0.1 (currency `₲` → `Gs.`) — 4 templates, ~30 min, 4 tests. Next step.

## 2026-10-07 (Phase 3-7 audit summary)

- **Phase 3 (SASKIA-304, clientes + productos + recetas)** — 3 real
  fixes landed: removed duplicate `Importar CSV` button in
  productos.html (lines 27-34), replaced broken `100 * (1 - x /
  (x/0.65))` margin formula in receta_detalle.html with honest
  `unit_cost.batch_cost_gs / unit_cost.units` reading, added Paraguay
  phone placeholder to cliente_editar.html input.

- **Phase 4-7 (SASKIA-305/306/307/308, inventario + producción +
  pedidos + proveedores + menus + reportes + insights + dashboard +
  settings + EOD + auditoria + ops)** — all templates audited and
  already meeting standards. No code changes, regression tests only
  (47 tests across 4 files).

- **Plan deviation** — the "Phase 6.5 settings field for CMV target"
  question was moot: food_cost % is already implemented at the global
  level in dashboard.html (line 131) and analisis.html (line 60), and
  per-product food_cost_pct is already in insight_price_impact.html.
  No operator-editable target needed for the simple ≤35% target.

- **Final totals** — 115 tests, 8 phases, 13 commits (78f8afab →
  01e0b7c4), all ruff clean. ~2.5 working days end-to-end.
