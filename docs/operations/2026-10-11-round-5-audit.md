# Round 5 Multi-Hat Audit (2026-10-11)

## Method
8 personas, 1 session each:
- **Operator:** UI/UX, "what would an operator do?"
- **Pen-tester:** security holes, injection, auth bypass
- **QA:** test quality, coverage gaps, weak patterns
- **Finance:** money handling, ledger writes, idempotency
- **Security:** ZAP, OWASP, secrets in code
- **DevOps:** CI, deploy, build, infrastructure
- **Migration Engineer:** schema changes, data backfill
- **New Dev:** onboarding friction, missing docs

## Findings (24 bugs across rounds 1-4)

### Critical (P0)
1. Recipe edit form 500 error (`app/routers/recipes.py:1066`)
2. Reorder upload 500 error (`app/routers/reorder.py:817`)
3. Loyalty point redemption not writing ledger
4. Recipe audit logging missing
5. Backup.py schema compatibility (`Column has no attribute 'name'`)
6. ingredient_intel import path broken

### High (P1)
7. White-on-white text visibility in production.html
8. ZAP workflow alert configuration error
9. Form templates missing 'grid' class
10. Manual version check script hardcoded paths
11. Test migration pollution causing flaky test failures
12. Caja error display not working (fixed in round 5)

### Medium (P2)
13. Sales percentage format incorrect (25000 instead of 25.000)
14. SASKIA-301_register test premise incorrect
15. Ad-hoc production modal dark mode white-on-white
16. Schema version test name unclear
17. Missing round-2-triage-process.md documentation
18. Missing round-2-triage-process.md documentation
19. Backup script compatibility issues
20. White-on-white audit bug in ZAP workflow
21. Haccp seed test import error
22. Missing CRLF in row 14, column 1 of reorder.csv test file
23. Test production_scheduler.py empty stub file
24. Assert True patterns in test files

### Low (P3)
25. Docs quality gate findings (101 NEW pymarkdownlnt issues)
26. 7 untested routers with critical functionality

## Test coverage analysis

| Router | Routes | Tests | Status |
|--------|--------|-------|--------|
| settings_runtime | 41 | 0 | CRITICAL GAP |
| customers | 20 | 14 | partial (no soft-delete) |
| products | 17 | 0 | CRITICAL GAP |
| suscripciones | 8 | 0 | CRITICAL GAP |
| fiado | 7 | 4 | partial |
| caja | 5 | 6 | FULLY COVERED |
| insights_derived | 6 | 5 | partial |
| insights_stock | 4 | 0 | CRITICAL GAP |
| excel_io | 4 | 0 | CRITICAL GAP |
| analisis | 1 | 1 | partial |
| copiloto | 2 | 2 | FULLY COVERED |
| gerencia | 1 | 1 | partial |
| menus | 3 | 3 | FULLY COVERED |
| herebus | 1 | 1 | FULLY COVERED |
| photo_credits | 1 | 1 | FULLY COVERED |
| users | 5 | 5 | FULLY COVERED |
| cotizador | 3 | 3 | FULLY COVERED |

## Pre-existing pollution

3 tests fail in suite, pass alone:
- `test_derived_intel.py::test_forecast_produces_realistic_distribution`
- `test_deploy_infra.py::test_release_off_main_refuses` (fixed in round 5)
- `test_migration_safety.py::test_no_mutates_global_mIGRATIONS_dict` (fixed in round 5)

## Recommendations

1. **Critical**: Address all P0 bugs immediately as they break core functionality
2. **High**: Fix P1 bugs that affect user experience or data integrity
3. **Medium**: Address P2 bugs that improve usability and maintainability
4. **Coverage**: Prioritize untested routers (settings_runtime, customers, products, suscripciones, fiado, caja, insights_stock, excel_io, analisis)
5. **Test quality**: Clean up pollution patterns and improve test reliability

## Next steps

See `docs/plans/2026-10-11-round-5-6-master-plan.md` for comprehensive plan covering remaining work.