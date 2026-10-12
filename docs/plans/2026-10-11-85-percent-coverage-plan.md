# 85% Coverage Plan - Multi-Phase Strategy (2026-10-11)

## Current Status
- **Coverage**: 26% (6,919/26,212 statements)
- **Target**: 85% (22,280/26,212 statements)
- **Gap**: 59 percentage points (15,361 statements need coverage)

## Multi-Phase Approach

### Phase 1: Critical Business Logic (Target: 40% coverage)
**Focus**: Test core business operations
- Sales processing
- Inventory management
- Customer management
- Recipe/costing
- Caja/cash operations
- Database models
**Effort**: ~3,000 statements to cover
**Files**: ~30 critical files

### Phase 2: Router & API Endpoints (Target: 55% coverage)
**Focus**: Test all HTTP endpoints
- All router modules in app/routers/
- Request/response handling
- Authentication flows
**Effort**: ~4,000 statements to cover
**Files**: ~40 router files

### Phase 3: Services & Utilities (Target: 70% coverage)
**Focus**: Test service layer
- Backup/restore
- Export/import (CSV, XLSX)
- Reports generation
- Template rendering
- Validation utilities
**Effort**: ~3,500 statements to cover
**Files**: ~25 service files

### Phase 4: Business Modules (Target: 80% coverage)
**Focus**: Test domain-specific logic
- Forecasting
- Analytics
- Insights
- Loyalty programs
- Reorder logic
**Effort**: ~2,500 statements to cover
**Files**: ~20 business module files

### Phase 5: Integration & Edge Cases (Target: 85% coverage)
**Focus**: Test complex workflows
- Multi-step processes
- Error handling
- Edge cases
- Integration points
**Effort**: ~2,000 statements to cover
**Files**: Final cleanup across all modules

## Strategy
1. **Create focused test files** for each module
2. **Use actual function calls** to exercise code paths
3. **Test happy paths + error cases**
4. **Verify coverage increases** after each phase
5. **Iterate** until 85% is reached

## Progress Tracking
- Each phase adds measurable coverage
- Tests are committed incrementally
- Coverage reports show progress
- Stop at any point to check status

## Estimated Timeline
- Phase 1: 2-3 hours
- Phase 2: 3-4 hours
- Phase 3: 2-3 hours
- Phase 4: 2-3 hours
- Phase 5: 2-3 hours
- **Total: 11-16 hours of focused work**

## Success Criteria
- ✅ 85% coverage achieved
- ✅ All critical paths tested
- ✅ CI gate passes
- ✅ No regression in existing tests
