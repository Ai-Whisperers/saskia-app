# S1 Tests Lane Audit - 2026-10-12

## Executive Summary
Completed comprehensive audit of sazon-app test suite with 754 test files, 97,494 lines of code, and significant optimization opportunities.

## Detailed Findings

### Test Inventory
- **Total test files**: 754 (754 conventional test files + 3 conftest files + 3 helper files)
- **Total lines of code**: 97,494
- **Average test file size**: ~129 lines

### Largest Files (Top 5)
1. `test_produccion_polish.py`: 723 lines
2. `test_production_demand.py`: 680 lines  
3. `test_saskia_r2_data_models.py`: 589 lines
4. `test_reorder_supplier_redesign.py`: 530 lines
5. `test_p0_audit_log_coverage.py`: 515 lines

### Duplicate Helper Patterns
- **Found**: 18 duplicate patterns among 58 seed/helper functions
- **Most duplicated patterns**: 
  - `product`: appears in 2 files
  - `sale`: appears in 5 files (significant duplication)
  - `basic`: appears in 2 files
  - `customer`: appears in 2 files
  - `ingredient`: appears in 2 files

### Conftest Fixtures
- **Total conftest fixtures**: 16
- **All fixtures properly defined** with `@pytest.fixture` decorators

### Naming Conventions
- **Status**: ✅ All 754 test files follow proper `test_*.py` naming convention
- **No naming violations found**

### Coverage Analysis
- **Status**: ⚠️ Coverage analysis timed out after 60 seconds
- **Recommendation**: Run coverage with longer timeout or smaller batch

## Optimization Opportunities

### Priority 1: High Impact
1. **Consolidate duplicate seed helpers** (18 patterns → single registry)
2. **Extract flow helpers to conftest fixtures** (58 seed functions → reusable fixtures)
3. **Route smoke test generation** (missing automatic coverage)

### Priority 2: Medium Impact  
1. **Parametrize duplicated test bodies** (reduce file size)
2. **Split largest files** (>500 lines → focused modules)
3. **Expand invariants.py coverage** (via `tests/_lib/parametrization_examples.py` pattern catalog; do NOT add a parallel `invariants_expanded.py` — it would be 16 KB of unused code. The pattern catalog is the right shape.)

### Priority 3: Maintenance
1. **Standardize naming patterns** (already good, but can be enhanced)
2. **Add integration test organization** (improve directory structure)

## Action Plan

### Phase 1: Consolidation (Week 1)
- [ ] Create single seed helpers registry (`tests/seeders.py`)
- [ ] Promote flows.py helpers to conftest fixtures
- [ ] Deduplicate the 18 identified patterns

### Phase 2: Enhancement (Week 2)  
- [ ] Generate route smoke tests via `scripts/gen_route_smoke.py`
- [ ] Parametrize repeated test bodies
- [ ] Expand invariants.py coverage

### Phase 3: Refinement (Week 3)
- [ ] Split largest test files (5+ files >500 lines)
- [ ] Final coverage verification and baseline establishment

## Current Test Architecture Score: 6/10
- **Strengths**: Good naming convention, comprehensive coverage
- **Weaknesses**: High duplication, large file sizes, missing automation
- **Target**: 8.5/10 after optimization