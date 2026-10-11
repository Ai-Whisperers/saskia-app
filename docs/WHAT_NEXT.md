# What's Next for Sazón RMS

## ✅ Round 5 audit (2026-10-11)

Multi-hat audit (Operator, Pen-tester, QA, Finance, Security,
DevOps, Migration Engineer, New Dev) over merged main
(`fcb995bc`) found:

- **24 bugs fixed in rounds 1-4** (recipe editing, reorder
  upload, loyalty redemption, recipe audit, backup.py schema
  compatibility, ingredient_intel import, docs quality gate,
  white-on-white bugs, and 16 others).
- **1 bug fixed in round 5**: `caja.html` didn't render
  `{{ error }}` context variable.
- **15 tests added in round 5**: 6 for `caja` routes, 4 for
  `fiado` routes, 5 for `insights_derived` routes.

### Remaining work (9 plans)

See `docs/plans/2026-10-11-round-5-6-master-plan.md` for the
full breakdown. Total: ~28-34h.

**Ship order:** plan 0 (commit) → plan 1 (untested routers)
→ plan 2 (test pollution) → plan 3 (coverage gate) → plans
4-8 in any order.

### Next action

Commit the 17 uncommitted files in the working tree
(see `git status --short`). This unblocks deploy workflow
and `test_deploy_infra.py`.

---

## Original TODO items (before audit)

### Round 4 (2026-10-08c)
1. **Track test coverage** at 35% gate across all routes
2. **Create comprehensive test coverage report** showing route-by-route status
3. **Reach 35% coverage gate** across entire test suite
4. **Finish test coverage gaps** for all remaining untested routes
5. **Resolve 3 pre-existing test pollution issues** that cause flaky failures

### Round 3 (2026-10-07)
1. **Investigate and fix ZAP workflow alert configuration**
2. **Add 'grid' class to inventario_form.html and supplier_form.html**
3. **Fix manual version check script in deploy**

### Round 2 (2026-10-06b) 
1. **Create missing round-2-triage-process.md documentation**
2. **Remove hardcoded production data from test files**
3. **Create backup script that works for both development and production**

### Round 1 (2026-10-06a)
1. **Investigate recipe edit form 500 error**
2. **Fix reorder upload 500 error**
3. **Implement loyalty point redemption in single sale flow**
4. **Add recipe audit logging endpoint**

### Pre-Round 1 (2026-10-06)
1. **Fix white-on-white text visibility issues in production.html**
2. **Add Google Maps API key to places scraper (VPS deployment)**
3. **Update user guide README.md schema version from 116 to 117**

### Previous cycles
- [ archived: 2026-10-10-late-WHAT_NEXT-archived.md ]
- [ archived: 2026-10-10-evening-WHAT_NEXT-archived.md ]
- [ archived: 2026-10-10-early-WHAT_NEXT-archived.md ]