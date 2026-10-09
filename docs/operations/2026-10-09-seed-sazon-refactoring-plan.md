# seed_sazon Refactoring Plan — 2026-10-09

## Status: Deferred (Requires Context Object Pattern)

## Current State
- **Complexity**: 232 (B-grade violation, exceeds 15 limit by 15.5x)
- **Location**: `app/rms/seed/sazon.py:4179-5519` (1340 lines)
- **Test status**: 24/25 tests pass; 1 test fails (`test_idempotent_rerun`)
- **Attempted**: 2026-10-09 — extracted 30 sections into helpers, but reverted due to interdependencies

## Why It's Hard
The function has **10+ shared variables** that sections reference:
- `rng` (random.Random instance)
- `report` (SazonReport counter object)
- `seed_anchor_date` (datetime anchor for historical data)
- `supplier_objs` (list of created suppliers)
- `ingredient_objs_by_name` (dict of ingredient name → object)
- `recipe_objs_by_name` (dict of recipe name → object)
- `product_objs_by_name` (dict of product name → object)
- `customer_objs` (list of created customers)
- `pedido_objs` (list of created pedidos)
- `sale_objs_by_date` (dict of date → list of sales)

## Recommended Approach: Context Object Pattern

### Step 1: Create a SeedContext dataclass
```python
@dataclass
class SeedContext:
    session: Session
    report: SazonReport
    rng: random.Random
    anchor_date: datetime.date

    # Populated as seed progresses
    suppliers: list[Supplier] = field(default_factory=list)
    ingredients_by_name: dict[str, Ingredient] = field(default_factory=dict)
    recipes_by_name: dict[str, Recipe] = field(default_factory=dict)
    products_by_name: dict[str, Product] = field(default_factory=dict)
    customers: list[Customer] = field(default_factory=list)
    pedidos: list[Pedido] = field(default_factory=list)
    sales_by_date: dict[date, list[Sale]] = field(default_factory=dict)
```

### Step 2: Refactor seed_sazon to use context
```python
def seed_sazon(
    session: Session, *, overwrite: bool = False, days_of_history: int = 90
) -> SazonReport:
    """Idempotent comprehensive seed for La Vaquita Holandesa."""
    ctx = SeedContext(
        session=session,
        report=SazonReport(),
        rng=random.Random(42),
        anchor_date=datetime.now(ASUNCION_TZ).date(),
    )

    if overwrite:
        _delete_sazon_data(session)

    # Each helper takes ctx instead of (session, report, rng, anchor_date, ...)
    _seed_tenants_and_users(ctx)
    _seed_branding_settings(ctx)
    _seed_categories(ctx)
    _seed_payment_methods(ctx)
    _seed_margin_tiers(ctx)
    _seed_stock_status_config(ctx)
    _seed_storage_types(ctx)
    _seed_storage_keywords(ctx)
    _seed_date_presets(ctx)
    _seed_message_templates(ctx)
    _seed_delivery_zones(ctx)
    _seed_channels(ctx)
    _seed_compliance_info(ctx)
    _seed_suppliers(ctx)  # populates ctx.suppliers
    _seed_ingredients_with_variants(ctx)  # populates ctx.ingredients_by_name
    _seed_recipes_and_lines(ctx)  # populates ctx.recipes_by_name
    _seed_products(ctx)  # populates ctx.products_by_name
    _seed_tags(ctx)
    _seed_customers_and_addresses(ctx)  # populates ctx.customers
    _seed_production_plan_templates(ctx)
    _seed_production_completions(ctx)  # uses ctx.products_by_name
    _seed_pedidos_and_lines(ctx)  # populates ctx.pedidos
    _seed_sales_history(ctx, days_of_history)  # uses ctx.products_by_name
    _seed_special_sales(ctx)
    _seed_waste_log(ctx)  # uses ctx.ingredients_by_name
    _seed_shopping_list(ctx)  # uses ctx.ingredients_by_name
    _seed_haccp_log(ctx)  # uses ctx.anchor_date
    _seed_market_benchmarks(ctx)  # uses ctx.ingredients_by_name
    _seed_audit_log(ctx)
    _seed_appmeta_pins(ctx)
    _seed_bank_transactions(ctx)  # uses ctx.anchor_date

    session.commit()
    return ctx.report
```

### Step 3: Each helper signature becomes simple
```python
def _seed_suppliers(ctx: SeedContext) -> None:
    """Seed suppliers and populate ctx.suppliers."""
    for name, contact, phone, email, notes in SUPPLIERS:
        existing = ctx.session.execute(
            select(Supplier).where(Supplier.name == name)
        ).scalar_one_or_none()
        if existing is None:
            s = Supplier(
                name=name, contact=contact, phone=phone, email=email, notes=notes, is_active=True
            )
            ctx.session.add(s)
            ctx.session.flush()
            ctx.suppliers.append(s)
            ctx.report.suppliers += 1
```

## Benefits
1. **Each helper has 1-2 parameters** instead of 5-6
2. **Shared state is explicit** in the context object
3. **Main function becomes pure orchestration** (CC: 0-1)
4. **Helpers can be tested independently** with a mock context
5. **Easier to add new sections** without changing signatures

## Estimated Effort
- **Step 1** (create SeedContext): 30 min
- **Step 2** (refactor main function): 15 min
- **Step 3** (refactor 30 helpers): 2-3 hours
- **Testing & verification**: 1 hour
- **Total**: ~4 hours

## Alternative: Minimal Extraction
If the full context object refactor is too disruptive, a **minimal extraction** approach:
1. Extract only the 10-12 **self-contained sections** (no shared variables)
2. Leave the 18-20 **interdependent sections** in the main function
3. Expected result: 232 → ~120 (still over 15, but 50% reduction)

## Recommendation
**Do the full SeedContext refactor** — it's the right architectural fix and will make the code much more maintainable. The 4-hour investment will pay off in:
- Easier debugging (clear data flow)
- Better testability (mock contexts)
- Future-proofing (easy to add new sections)
- Compliance with AGENTS.md rule #29

## Next Steps
1. Create a feature branch: `git checkout -b refactor/seed-sazon-context`
2. Add SeedContext dataclass to sazon.py
3. Refactor helpers one section at a time, testing after each
4. Commit incrementally (one section per commit for easy review)
5. Merge to main after all tests pass

## Files to Modify
- `app/rms/seed/sazon.py` — add SeedContext, refactor seed_sazon + 30 helpers
- `tests/test_sazon_seed.py` — may need updates if any helpers are exposed

## Risk Assessment
- **Low risk**: Changes are internal to seed_sazon, no public API changes
- **Medium risk**: 30 sections to refactor, high chance of typos
- **Mitigation**: Commit after each section, run tests frequently
