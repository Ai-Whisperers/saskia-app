# Round 1 Review — Saskia RMS

> **For Saskia and Kiki.** This is the working agreement for the **first review round** of Fase 1, per `docs/plans/2026-08-31-rms-fase-1-dev-plan.md §9 Task 10` and the v2 plan milestone gates.
>
> **Period:** 5-7 days of daily use after the first successful login.
> **Focus:** does the app do what she needs day-to-day? What breaks? What's confusing?
>
> **Generated:** 2026-09-02 by AIW operator.

---

## How this round works

1. **Saskia** uses the app daily for 5-7 days (already started 2026-09-01 with local install; will continue on hosted once deployed).
2. She sends feedback via WhatsApp at any time. Operator (or Kiki) captures each item as a row below.
3. **Round 1** accepts any in-scope feedback (blockers + majors + minors + cosmetic). Items that turn out to be Fase 2 / Fase 3 features get marked `OUT-OF-SCOPE` and re-queued.
4. Items get a status. Items get fixed in PRs. PRs get committed with `Refs #NNN`.
5. When Round 1 closes, this file becomes the diff against the v0.1 deploy.

## Status legend

| Status | Meaning |
|---|---|
| `OPEN` | Not yet reviewed by dev team |
| `ACCEPTED` | In scope, will fix in this round |
| `OUT-OF-SCOPE` | Fase 2 / Fase 3 / separate quote |
| `DEFERRED` | Fase 1.5 or later (post-Round 1) |
| `FIXED` | Implemented; commit SHA noted |
| `WONT-FIX` | Explicitly rejected with reason |
| `NEEDS-INFO` | Can't reproduce or unclear; asked Saskia for more |

## Severity ladder

| Severity | Meaning | Example |
|---|---|---|
| `blocker` | Cannot use the app | "Sale entry crashes when qty is 0" |
| `major` | Significant friction | "Costo column always shows '—' even when prices are set" |
| `minor` | Polish / UX | "Tab order in sale entry skips qty field" |
| `cosmetic` | Spanish copy / wording | "'Guardá' should be 'Guardar' in this context" |
| `data` | Real bug, not UX | "Stock went negative after a void" |
| `perf` | Slow / freezes | "Excel import takes 30s for 100 rows" |

## In-scope for Round 1

Per `docs/operations/2026-09-fase-1-specs.md`:

- Inventory CRUD (Ingredient + RecipeLine + Recipe)
- Recipe costing (with sub-recipes, cycle detection)
- Products CRUD + sale price management
- Sales entry + void + stock drop
- Excel import + export (xlsx)
- Monthly close report
- Stockout report
- R2 encrypted backup (auto, daily)
- Spanish Paraguayan copy
- Bcrypt / Supabase auth
- Login / logout / password reset

## Out-of-scope for Round 1 (will be Fase 2 / 3, separate quote)

- WhatsApp order integration (Fase 2, Milestone 5)
- Customer directory (Fase 2, Milestone 6)
- Multi-tenant (Fase 2, Milestone 7)
- Producción del día (Fase 2, Milestone 3)
- Lista de compras (Fase 2, Milestone 3)
- Calendario Paraguay holidays (Fase 2, Milestone 4)
- Merma / waste tracking (Fase 2, Milestone 4)
- Inventory auto-reorder (Fase 3)
- Multi-user / RBAC (Fase 3)

---

## Round 1 items

<!--
Copy this template for each new item:

### #NNN — <short title>

**Severity:** blocker | major | minor | cosmetic | data | perf
**Status:** OPEN
**Reported:** YYYY-MM-DD
**Reporter:** Saskia (via WhatsApp) | Kiki (captured) | auto-detected (logs/monitoring)

**What:** <one-paragraph description, in Saskia's words where useful>

**Repro:**
1. <step 1>
2. <step 2>
3. <expected vs actual>

**Screenshot:** <attached or linked>

**Saskia says:** <verbatim quote if useful>

**Build team:** <response, including commit SHA when fixed>

**Closed at:** <date>

---

### #001 — Initial deploy on Saskia's laptop (2026-09-01)

**Severity:** milestone (not a defect)
**Status:** FIXED
**Reported:** 2026-09-01
**Reporter:** Operator (Ivan)

**What:** Local install on Saskia's Windows laptop. `installer/run.bat` from desktop shortcut launches uvicorn on 127.0.0.1:8765, opens browser, login works (`saskia` / `Saskia2026!`), 6 protected routes return 200 with session cookie. 324/325 tests pass, 81% coverage. 2 backup files in `~\Documents\AIW-Saskia\backups\`. PID 10760 (uvicorn.exe).

**4 launcher bugs noted:**
1. Bash-launched uvicorn (`proc_a730f02380d1`) was killed but its python.exe child lingered → operator had to `taskkill` it. The .bat-launched PID 10760 is the live one.
2. `installer/run.bat` didn't set `PYTHONPATH` — added during install session
3. `installer/run.bat` didn't set `HTTPS_ONLY=false` (Saskia's local doesn't have TLS) — added
4. `installer/run.bat` didn't set `AIW_SASKIA_*_DIR` overrides for her user profile — added

**2 unfixed governance issues:**
1. The .bat edits were made live on her machine, not pushed back to repo. Operator needs to commit the patched `run.bat` so the next install doesn't repeat the bugs.
2. `installer/ROUND-1-NOTES.md` (this file) didn't exist on disk — was referenced in handoff message but never created. (FIXED 2026-09-02.)

**Build team:** Local install stable as of 2026-09-01 18:05 UTC. Hosted pivot planned per `docs/operations/2026-09-02-saskia-decision-hosted-pivot.md`.

**Closed at:** 2026-09-02

---

### #002 — <next item here>

**Severity:** ...
**Status:** OPEN
**Reported:** YYYY-MM-DD

...

-->

---

## Round 1 review summary

When the round closes, fill this in:

- **Items raised:** N
- **Items fixed:** M (status `FIXED`)
- **Items out of scope:** K (status `OUT-OF-SCOPE` or `DEFERRED`)
- **Items rejected:** J (status `WONT-FIX`)
- **Items needs-info:** L (status `NEEDS-INFO`, escalated)
- **Total clock-time on Round 1:** X hours (vs. the 200h plan budget)

## Sign-off

When Saskia is satisfied:

> *Written OK — Round 1 closed. Fase 1 accepted.*
> Saskia Weiss Vander: ___________________________ date: ___________
> AI Whisperers (operator): ___________________________ date: ___________

---

*Generated 2026-09-02 per `docs/operations/2026-09-02-saskia-decision-hosted-pivot.md` §6 and `docs/plans/2026-09-rms-fase-1-dev-plan-v2.md` milestone gates. Stored at `installer/ROUND-1-NOTES.md` (this file). Companion: `docs/operations/2026-09-02-saskia-team-tasks.md`.*