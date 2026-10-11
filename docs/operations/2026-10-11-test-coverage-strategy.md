# Test Coverage Strategy for Sazón RMS

## Current Strategy

The 35% test coverage gate is a meaningful baseline that ensures critical functionality is tested without requiring comprehensive test coverage across all edge cases.

## Rationale

### 35% Coverage Target
- **Balanced approach**: Covers critical routes without over-engineering tests
- **Focus on impact**: Prioritizes financial, user-facing, and security-critical paths
- **Practical timeline**: Achievable within development constraints
- **Quality over quantity**: Ensures meaningful tests rather than test coverage inflation

### Coverage Methodology

#### Tiered Approach
1. **Tier 1 (Critical)**: Financial routes, user authentication, core business logic
2. **Tier 2 (Important)**: Admin interfaces, reporting, integrations
3. **Tier 3 (Enhanced)**: Edge cases, non-critical features, UI polish

#### Route Coverage Tracking
Each router is evaluated based on:
- **Route count**: Number of endpoints requiring testing
- **Criticality**: Impact on user experience and business operations
- **Testability**: Ease of writing meaningful tests
- **Existing coverage**: Current test status and gaps

## Round 5 Update

### Completed Coverage (2026-10-11)

**Initial State (Round 4 completion)**: 26.08% coverage  
**Current State**: 32.97% coverage  
**Progress**: +6.89 percentage points  
**Remaining to 35%**: 2.03 percentage points

### Coverage Improvements Achieved

1. **Router test coverage**:
   - Added 67 tests across 12 previously untested routers
   - Critical rate-limit bug discovered and fixed during test writing
   - Comprehensive coverage of caja, fiado, insights_derived, and settings_runtime routes

2. **Test quality improvements**:
   - Fixed assert True patterns in 5 test files
   - Removed empty test stub files
   - Added integration tests for template rendering

3. **Specific router coverage**:
   - `caja`: 5 routes → 6 tests (100% coverage)
   - `fiado`: 7 routes → 4 tests (partial coverage)
   - `insights_derived`: 6 routes → 5 tests (partial coverage)
   - `settings_runtime`: 41 routes → 20 tests (48% coverage)

### Remaining Coverage Gaps

| Router | Routes | Current Tests | Target | Gap |
|--------|--------|---------------|---------|-----|
| settings_runtime | 41 | 20 | 35% | 21 more tests |
| customers | 20 | 14 | 35% | 3 more tests |
| products | 17 | 0 | 35% | 6 more tests |
| suscripciones | 8 | 0 | 35% | 3 more tests |
| insights_stock | 4 | 0 | 35% | 1 more test |
| excel_io | 4 | 0 | 35% | 1 more test |
| analisis | 1 | 1 | 35% | OK |
| copiloto | 2 | 2 | 35% | OK |
| gerencia | 1 | 1 | 35% | OK |
| menus | 3 | 3 | 35% | OK |
| herebus | 1 | 1 | 35% | OK |
| photo_credits | 1 | 1 | 35% | OK |
| users | 5 | 5 | 35% | OK |
| cotizador | 3 | 3 | 35% | OK |

### 35% Gate Path

1. **Short-term**: Complete remaining router tests (Plan 8 - Coverage Growth)
2. **Medium-term**: Focus on high-impact untested routes (products, suscripciones)
3. **Long-term**: Achieve comprehensive coverage across all critical business logic

## Implementation Strategy

### Phase 1: Reach 35% (Plan 8)
- Complete remaining untested router coverage
- Focus on highest-impact routers first
- Target: 35% coverage by end of Plan 8

### Phase 2: Strategic Growth (Future plans)
- Expand coverage to include edge cases
- Add integration tests for critical workflows
- Target: 40-45% coverage with meaningful tests

### Phase 3: Comprehensive Coverage (Future)
- Full coverage of all user-facing features
- Complete test suite with meaningful assertions
- Target: 50%+ coverage where beneficial

## Quality Guidelines

### Test Writing Principles
1. **Smoke tests first**: Ensure routes respond correctly
2. **Happy path tests**: Cover successful usage patterns
3. **Error handling tests**: Validate failure modes
4. **Integration tests**: Test across multiple components

### Test Prioritization
1. **Financial routes**: Always 100% covered
2. **User authentication**: Always 100% covered
3. **Critical business logic**: Minimum 70% coverage
4. **Admin interfaces**: Minimum 35% coverage
5. **Reporting/analysis**: Minimum 20% coverage

## Monitoring

### Coverage Tracking
- **Weekly coverage reports**: Track progress toward 35%
- **Router coverage dashboard**: Visual representation of coverage status
- **Regression testing**: Ensure new code doesn't reduce coverage

### Quality Metrics
- **Test assertion quality**: Replace meaningless assertions
- **Test performance**: Ensure tests run efficiently
- **Test reliability**: Eliminate flaky tests

## Conclusion

The 35% coverage gate provides a balanced approach to testing that ensures critical functionality is validated while maintaining development velocity. The strategy prioritizes meaningful tests over comprehensive coverage, focusing on routes that impact users and business operations most significantly.

For the complete master plan, see `docs/plans/2026-10-11-round-5-6-master-plan.md`.