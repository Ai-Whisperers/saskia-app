# Plan 3 — Boost coverage to 35% gate (6h, P0)

> **Master plan:** `docs/plans/2026-10-11-round-5-6-master-plan.md`

## Scope
Current measured coverage is **26.12%**; gate is **35%** per
`pyproject.toml:65` (`--cov-fail-under=35`). Need ~9 percentage
points (~1,800 lines of test coverage on ~20k statements).

## Why this is P0 (and not a "stretch" goal)

The 35% gate IS enforced — `pyproject.toml` has it. CI fails
locally if coverage drops below 35%. **Today it's below the gate
and CI still passes** because the full test suite never completes
in the 240s terminal budget (the gate only fires on a full run).

This means **any future PR that adds a new function with no test
will silently break the gate** once the suite gets fast enough
to complete. Better to fix the floor now.

## Strategy (per `docs/plans/2026-10-01-phase14-coverage-strategy.md`)

### Sub-task 3.1 — Template-render integration tests (3h)

`app/services/template_render.py` is at 21% coverage — the
biggest single gap. The fix: render the top 30 most-used
templates with a minimal fixture set and assert no
`{{ undefined }}` exceptions.

**File:** `tests/test_template_render.py`

**Pattern:**

```python
import pytest
from app.services.template_render import render_template

TEMPLATES_TO_TEST = [
    ("base.html", {"request": fake_request, "user": fake_admin}),
    ("inicio.html", {"request": fake_request, "user": fake_admin}),
    # ... 28 more
]

@pytest.mark.parametrize("template_name,context", TEMPLATES_TO_TEST)
def test_template_renders(template_name, context):
    """Top 30 templates render without undefined variable errors."""
    html = render_template(template_name, **context)
    assert html  # non-empty
    assert "{{" not in html or "}}" not in html  # no leaked jinja
```

**How to find the top 30:** `grep -rh "TemplateResponse\\|return templates" app/routers/ | sort | uniq -c | sort -rn | head -30`

**Acceptance:** +2 percentage points (~400 lines of coverage).

### Sub-task 3.2 — Parametrized CRUD roundtrip tests (2h)

`tests/test_crud_roundtrips_parametrized.py` — for ingredient,
product, recipe, customer, supplier, sale, pedido, merma, station:
POST → GET → verify → DELETE (where supported).

**Pattern:**

```python
import pytest

@pytest.fixture(params=["ingredient", "product", "recipe", "customer", "supplier"])
def model_factory(request, session_factory):
    s = session_factory()
    try:
        if request.param == "ingredient":
            yield lambda s: make_ingredient(s, name=f"CRUD-test-{uuid.uuid4().hex[:6]}")
        # ... 4 more
    finally:
        s.close()


def test_crud_create_then_get(model_factory, authed_client):
    """POST /<model>/new → 303; GET /<model>/{id} → 200 with the new row."""
    s = session_factory()
    obj = model_factory(s)
    s.commit()
    obj_id = obj.id
    s.close()

    r = authed_client.get(f"/<model>s/{obj_id}")
    assert r.status_code == 200
    assert obj.name in r.text


def test_crud_edit_then_verify(model_factory, authed_client):
    """POST /<model>/{id}/edit → 303; GET /<model>/{id} → 200 with new name."""
    # ...


def test_crud_delete_marks_soft_deleted(model_factory, authed_client):
    """POST /<model>/{id}/delete → 303; subsequent GET → 404 or 'deleted'."""
    # ...
```

**Acceptance:** +2 percentage points.

### Sub-task 3.3 — Fiado end-to-end (1h)

`tests/test_fiado_end_to_end.py` — extend the round-5 work to
a full happy path: open fiado account → charge to debt → partial
payment → close. ~10 tests. Adds ~10% to `app/rms/fiado.py` coverage.

**Acceptance:** +1 percentage point.

## Total: ~5-6h, +5pp, gate passes (35%+).

## Acceptance criteria
- `pytest --cov=app --cov-fail-under=35` passes locally
- Coverage report shows ≥35% overall
- No new test pollution

## How to verify

```bash
uv run pytest --cov=app --cov-report=term-missing
# Expected: "Required test coverage of 35% reached. Total coverage: 35.X%"
```

## Ship-blocked-by
Plans 0, 1, 2.

## Risk
Medium. Template-render tests can be flaky if templates have
hidden dependencies. Mitigation: use the `_template_safe` helper
that already exists in conftest.
