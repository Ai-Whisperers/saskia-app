# Sazón — Second Review Execution Plan

**Date:** 2026-09-23
**Source specs:**
- `/opt/data/profiles/ivan/attachments/the operator 2nd review-2.txt` (transcript)
- `/opt/data/profiles/ivan/attachments/2026-09-23-second-review-stories-2.docx` (11 user stories across 4 epics)
**Repo:** `/opt/data/work/sazon-app` (clone of `Ai-Whisperers/sazon-app`)
**HEAD:** `9831ea4` (matches `origin/main` — clean tree)
**Test baseline:** 1753 tests across 207 files

---

## 0. Findings that change the scope

Before I write a plan, three things I learned from the prior sessions that the 11 stories don't show on their own:

1. **Yesterday (2026-09-22)** I delivered `docs/operations/2026-09-22-review-tickets-analysis.md` — an analysis of the **first** review's 18 tickets. **Most are still unfixed.** The "PRO-04 (Ver receta link)", "PRO-02 (fractional qty)", "MER-01 (unit selector)", "PRO-01 (weekly template doesn't persist)" are exactly the same bugs the operator is hitting in the second review. The second-review docx is the second pass; the first-review tickets were never closed.

2. **The v3 epic plan already scopes this work** — E21 = Production Plans (covers US 3.3 templates), E8.S2 = days-of-stock forecast (covers US 2.3), and several stories from E8/E18 cover US 2.2 price history. The 11 stories aren't new epics; they're real-world acceptance criteria for planned-but-unbuilt (or partially-built) epics.

3. **The `flour / multi-package` modeling decision (item 3b in the first analysis) is the gate.** US 2.2 ("show fluctuation") is half-built — `IngredientPriceEvent` records events but a single ingredient has one `purchase_price_gs`. the operator's "harina 1kg / 250g / supplier X" needs a schema decision before the history chart is meaningful.

---

## 1. The plan — 7 sprints, ~32h of code + 8h ops

I split the 11 stories + yesterday's 18-ticket carryover into 7 sprints with strict dependencies. Each sprint ships as **one branch + one commit + CHANGELOG entry + tests green + ruff clean**. No mega-PRs.

| Sprint | Stories | Est | Branch | Why in this order |
|---|---|---|---|---|
| **S1 — UI cleanup** | US 1.1 (Spanish + image modal) | 3 h | `fix/sazon-r2-ui-spanish-images` | First-impression fix; unblocks everything else by clearing noise. |
| **S2 — Link/href fixes** | First-review PRO-04 (Ver receta) + PRO-02 (whole-number qty) + MER-03 (English on Merma) | 2 h | `fix/sazon-r2-small-href-copy` | Tiny, isolated, all on existing templates. Closes carryover from yesterday. |
| **S3 — Inventory + categories** | US 2.1 (labels/categories on-the-fly) + INV-03 (negative-stock clamp, Spanish urgency label) | 6 h | `feat/sazon-r2-labels-and-stock-display` | The two stories share the inventory form & template. |
| **S4 — Recipe polish** | US 3.1 (sub-recipe UI verify) + US 3.2 (reverse ingredient filter in template) | 4 h | `feat/sazon-r2-recipe-filters` | Backend exists; wiring UI only. Fast wins. |
| **S5 — Sales split + Quick-Sell** | US 4.3 (history vs nueva-venta tab) + US 4.2 (Quick-Sell panel + multi-field customer search) | 8 h | `feat/sazon-r2-pos-split` | POS-focused; biggest UX win. |
| **S6 — Pedidos → Production** | US 4.4 (encargos to production auto-suggest) + CIE-01 (overlay completions in /produccion) | 5 h | `feat/sazon-r2-pedidos-production-bridge` | Closes the day's two flagship workflows. |
| **S7 — Schema decisions** | US 2.2 (price history chart) + US 2.3 (predictive forecast) + US 3.3 (production templates) + US 4.1 (packaging at sale) | 12 h + modeling decision | `feat/sazon-r2-data-models` | **Blocked on operator decisions** for flour / multi-package + forecast horizon. |

**S7 is the hardest sprint and the one I cannot start without your decisions.** S1-S6 can ship without them.

Total: **30 h code + 2 h modeling discussion + 8 h ops (branching, tests, deploy, smoke)** = ~40 h wall time. Realistic for solo work: **two full sessions + two follow-ups**.

---

## 2. What I'm doing RIGHT NOW — concrete first actions

Per your instruction "make a complete plan first and then implement it" — here is the literal sequence I will run as soon as you say **go**:

1. `git checkout -b fix/sazon-r2-ui-spanish-images` (S1)
2. `cd /opt/data/work/sazon-app && uv sync --all-extras`
3. `uv run pytest tests/ -q` (baseline 1753)
4. Edit `app/templates/producto_form.html` and `productos.html`: Portuguese→Spanish, image → modal trigger
5. New test: `tests/test_product_image_modal.py` (asserts image starts hidden, modal opens on click)
6. `uv run pytest tests/test_product_image_modal.py -q && uv run ruff check . && uv run ruff format --check .`
7. `app/CHANGELOG.md` entry under `[Unreleased]` — one line, no narrative
8. Commit `fix(sazon-r2): Spanish + image modal on producto form` (one commit)
9. `git push origin fix/sazon-r2-ui-spanish-images`
10. Open draft PR with the CHANGELOG line and the test summary

Then S2 → S3 → ... → S6. **S7 waits for the schema decisions.**

---

## 3. The 3 decisions I need from you BEFORE I touch S7

These are blocking, not "nice to have." Without them I'll be guessing the data model.

### Decision A — Flour / multi-package modeling
the operator wants one ingredient `harina` with sub-rows `harina 1kg`, `harina 250g`, `harina proveedor X`. Three options:

- **A1.** Add `supplier_variant` table: `(ingredient_id, package_size, package_unit, purchase_price_gs, supplier_id, preferred)` — price history ties to variant, not ingredient. (Recommended — cleanest, matches price_event model.)
- **A2.** Parent/child ingredient rows with FK — heavier, recurses forever, breaks the current cost math.
- **A3.** Treat each package as its own Ingredient (current behavior) — keeps things simple, but you lose "what's my total harina stock across all packages?"

### Decision B — Forecast horizon for US 2.3
"How many days until I run out" needs a horizon. Options: 7 / 14 / 30 / configurable.

### Decision C — Production templates for US 3.3
"Semana estándar", "Semana navideña", etc. Do you want:
- **C1.** Blank-template + apply (she creates from scratch each new template) — simpler.
- **C2.** Fork-current-week (she can clone last week as a starting point) — matches her workflow better.
- **C3.** Both (blank + fork buttons).

---

## 4. What I am NOT doing (out of scope)

- **Not touching the v3 epic plan.** The 11 stories are real-world AC for already-planned epics. I'm not adding E26-E35 work.
- **Not redesigning the nav** (NAV-01 in yesterday's 18-ticket list). It's a 1.5h task but it deserves its own ticket and a separate commit; I'll file a `SASKIA-NNN-nav-01.md` ticket and do it after S6.
- **Not adding new dependencies.** All work uses what's already in `pyproject.toml`.
- **Not migrating the live Neon DB or changing production.** Local-only until each branch passes CI locally.
- **Not writing to `docs/wishlist/`.** These are committed work items, not backlog ideas.
- **Not building Phase 2/3 features** (WhatsApp bot, multi-tenant, Guaraní, etc.). Deferred per existing wishlist discipline.

---

## 5. Risks I'm tracking

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| The "updated Excel" arrives mid-sprint and changes recipe IDs | Medium | Medium | S4 stays as filter-only UI; doesn't touch recipes data |
| `uv sync` fails (PEP 668, lock drift) | Low | High | Use the same `uv sync` flags the install README uses; tests gate |
| MER-01 unit math wrong → test passes but stock is wrong | Medium | High | Property-based test using `hypothesis` (already in dev deps) |
| Schema decision A takes >1 turn to decide | High | Medium | I default to **A1** if you don't respond within one turn; reversible via migration |
| `/ventas` 500 (per yesterday's ticket A.2) still broken on real Neon | High | High | Add `tests/test_ventas_200_with_real_neon.py` (skip-on-no-docker) before touching S5 |
| Coverage gate (80%) trips on the new tests | Low | Medium | Add tests with the feature; never lower the gate |
| the operator sends the old Excel by mistake → recipe dropdown goes stale | Medium | Low | Document in CHANGELOG: "import path unchanged; awaiting operator to refresh" |

---

## 6. Definition of done — for the whole plan

- [ ] 11 second-review stories have explicit, test-backed acceptance criteria
- [ ] 4 first-review carryover bugs (PRO-04, PRO-02, MER-03, INV-03) are closed
- [ ] 1753 tests still passing + ≥40 new tests added
- [ ] Coverage stays ≥80%
- [ ] `ruff check .` + `ruff format --check .` clean
- [ ] `app/CHANGELOG.md` updated for each sprint
- [ ] Each sprint = one branch + one commit + draft PR
- [ ] No PR auto-merged; you review + merge
- [ ] No schema change to live Neon DB without your explicit "ship to prod" on each PR

---

## 7. What happens after the plan completes

Once S1-S6 are merged:

- **S7** becomes its own plan after the schema decisions are in (separate document).
- **Carryover tickets** (NAV-01, NAV-02, MER-01, PRO-01, CIE-02, BUG-00, etc.) get filed as `SASKIA-NNN-*.md` tickets in `docs/tickets/` — separate from this plan's PRs.
- **A new round of analysis** runs: re-audit all 11 stories + the carryover against the merged main, produce a `2026-09-24-second-review-followup.md` to check nothing regressed.

---

## 8. Confirmation needed

Pick one for each, or just say **"go, defaults"** and I'll use my recommendations.

1. **Plan execute order:** S1→S6 first (S7 blocked on decisions), or do you want S7 first?
2. **Branch strategy:** draft PR per sprint, you merge (default), or one mega-PR with all 6 sprints (not recommended)?
3. **S7 default decisions if you don't respond:** A1 (supplier_variant) + horizon 14d + C2 (fork-current-week)?
4. **Pause at end of each sprint to show you the diff, or chain S1→S6 without stopping?**
