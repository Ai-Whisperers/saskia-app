# Saskia RMS — Hour Log

Tracks planned vs actual hours across the engagement. Reconciles against
`docs/plans/2026-09-07-saskia-complete-epic-plan-v3.md` and the
Saskia PDF's 97h budget (70h original scope + 27h contingency).

**Bucket codes:** `scope` = original quote, `contingency` = PDF-built-in extras,
`overflow` = exceeds contingency, flagged for §7 conversation.

**Threshold reminders:**
- ≤ 27h extras → green, inside PDF contingency
- 27–31h extras → yellow, K.W. flags
- > 31h extras → orange, K.W. flags + §7 conversation likely
- > 97h total → red, §7 conversation mandatory

---

## Round 1 review — Thu 18-sep 2026

**Plan:** `.hermes/plans/2026-09-21_101320-saskia-review-18sep-round1.md`
**Deploy target:** hosted (`saskia-rms.paragu-ai.com`)
**Branch:** `feat/rms-fase1-review-round1`

### Planned vs actual

| Date       | Task     | Planned | Actual | Bucket | Status  | Notes                                |
|------------|----------|--------:|-------:|--------|---------|--------------------------------------|
| 2026-09-21 | T2       |     0.5 |    0.5 | scope  | done    | Hide auditoria + ops from topnav     |
| 2026-09-21 | T3       |     1.0 |    1.0 | scope  | done    | Ver-receta routes to recipe          |
| 2026-09-21 | T4       |     1.5 |    1.0 | scope  | done    | Pedidos status filter                |
| 2026-09-21 | T7       |     2.0 |    1.5 | scope  | done    | Settings polish + visual-noise cut   |
| 2026-09-21 | T1       |     3.0 |    2.5 | scope  | done    | Recipe line unit selector — grams input |
| 2026-09-21 | Q1-core  |     4.0 |        | scope  | pending | Schema v4 + restock write            |
| 2026-09-21 | Q2-prep  |     1.0 |        | scope  | pending | Calendar grid component shell        |
| 2026-09-21 | T5       |     2.0 |        | scope  | pending | EOD production-completed section     |
| 2026-09-21 | T6       |     2.0 |        | scope  | pending | Merma whole-batch flow               |
| 2026-09-21 | T8       |     2.0 |        | scope  | pending | Cross-page consistency               |
| 2026-09-21 | Q1-sfc   |     5.0 |        | scope  | pending | Surface + reportes/precios + insight |
| 2026-09-21 | Q2-fin   |     9.0 |        | scope  | pending | Full calendar + interactions         |
| 2026-09-21 | Q3       |     2.0 |        | scope  | pending | forecast_source label + override     |
| 2026-09-21 | T9       |     4.0 |        | scope  | pending | QA plan + tests                      |
| 2026-09-21 | DEP      |     1.0 |        | scope  | pending | Hosted deploy verification           |
| 2026-09-21 | BUF      |     2.0 |        | scope  | pending | Cross-cutting fixes from review      |

### Running totals

| Bucket        | Planned | Actual |
|---------------|--------:|-------:|
| scope         |    40.0 |    4.0 |
| contingency   |     0.0 |    0.0 |
| overflow      |     0.0 |    0.0 |
| **TOTAL**     |    40.0 |    4.0 |

| Threshold            | Limit | Current | Margin |
|----------------------|------:|--------:|-------:|
| Extras vs contingency |   27h |     4.0 |  23.0h |
| Total vs PDF         |   97h |     4.0 |  93.0h |

### Status flags

- [ ] Green: ≤ 27h extras
- [ ] Yellow: 27–31h extras (flag to K.W.)
- [x] Orange: 32–97h total (flag to K.W., no §7 yet — current state on plan sign-off)
- [ ] Red: > 97h total (§7 conversation mandatory)