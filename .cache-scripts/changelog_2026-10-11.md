## 2026-10-11

### Fixed
- `caja.html`: render `{{ error }}` context variable so 404
  responses show "Sesión no encontrada" instead of empty form.
- `app/routers/menus.py`: rate-limit integration bug - missing `session` parameter
  in `is_write_rate_limited()` calls (critical financial protection)
- `deploy/write_env_file.py`: added BWS 429 retry logic with 3-attempt exponential backoff
- `app/templates/caja.html`: added `caja_error_banner` feature flag for error display
- Schema version consistency: updated all docs references to schema v117
- Multiple white-on-white bugs: added hardcoded color `#111827` to prevent invisible text

### Tests added
- 6 caja route tests (open, close, z-ticket, 404, error display)
- 4 fiado route tests (cargar happy, cargar zero-rejected, estado toggle, audit row)
- 5 insights_derived route smoke tests
- 14 untested router test files covering critical business logic:
  - settings_runtime, customers, products, suscripciones, insights_stock, excel_io
  - analisis, copiloto, gerencia, menus, herebus, photo_credits, users, cotizador
- test_recipe_audit.py for recipe audit coverage
- test_inventory_write_path.py for ingredient/recipe mutations
- test_station_archive_tests.py for station archive/unarchive actions
- test_migration_edge_cases.py for negative test scenarios

### Plan
- 9-part master plan for remaining work:
  `docs/plans/2026-10-11-round-5-6-master-plan.md`
- Plans executed: 0 (commit), 1 (untested routers), 2 (test pollution), 3 (coverage gate), 5 (production hardening), 6 (test gaps), 7 (documentation)
- Coverage progress: 26.08% → 32.97% (+6.89pp), need 35% gate

### Documentation
- `docs/WHAT_NEXT.md`: updated with Round 5 audit results and remaining work
- `docs/operations/2026-10-11-round-5-audit.md`: comprehensive audit documentation
- `docs/operations/2026-10-11-test-coverage-strategy.md`: updated coverage strategy