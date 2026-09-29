"""tests/e2e/test_migration_archaeology.py — boot at every schema version,
upgrade to head, data must survive.

The suite historically tested only: (a) the registry is contiguous, (b) a
fresh DB reaches head. Missing: a DB that was BUILT at version N (real
history, real data) upgrading to head with its rows intact. Two migration
renumbering collisions this month (039-042 → 050-053) and the Phase-2B
half-refactor incident both shipped past the old tests.

Strategy per version N in the sample set:
  1. Fresh SQLite DB; set app_meta.schema_version = N-1 and let init_db
     run migration N and everything after. (init_db creates ALL tables
     from the current models first — migrations are additive columns, so
     an "old DB" here is really "new tables + migration bookkeeping". A
     true historical-shape DB can't be reconstructed without old model
     code; the invariant we CAN enforce is: the full chain v_start→head
     runs clean on a populated DB and sentinel rows survive.)
  2. Insert sentinels (ingredient/recipe/product/sale rows) at v_start.
  3. Run init_db again (the boot path — what prod does on deploy).
  4. Assert schema_version == CURRENT_SCHEMA_VERSION and sentinels intact.

The whole-chain run (v0 → head) is covered by every other test file's
fresh DB; what this adds is the REPLAY over live data.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from app.rms.config import CURRENT_SCHEMA_VERSION

# Sample versions exercising distinct migration eras. Full sweep of all 54
# costs ~54 × 0.3s ≈ 16s — acceptable nightly, too slow for every-commit.
# The parametrized set below hits each era boundary (incl. both renumbered
# stack migrations and the tag-algebra tail).
SAMPLE_VERSIONS = [1, 20, 38, 49, 50, 51, 52, 53, 54]

pytestmark = [pytest.mark.crud]


def _set_version(conn, v: int) -> None:
    from datetime import datetime, timezone

    ts = datetime.now(timezone.utc).isoformat()
    conn.execute(text(
        "INSERT INTO app_meta (key, value, updated_at) "
        "VALUES ('schema_version', :v, :ts) "
        "ON CONFLICT(key) DO UPDATE SET value = :v, updated_at = :ts"
    ), {"v": f'"{v}"', "ts": ts})
    conn.commit()


def _sentinels(factory) -> dict:
    from tests.factories import ing_line, make_ingredient, make_product, make_recipe

    with factory() as s:
        ing = make_ingredient(s, purchase_price_gs=12345, stock_qty=7.5)
        rec = make_recipe(s, lines=[ing_line(ing, qty=0.25)])
        prod = make_product(s, recipe=rec, sale_price_gs=99000)
        s.commit()
        return {"ing": ing.id, "rec": rec.id, "prod": prod.id,
                "ing_price": 12345, "ing_stock": 7.5, "prod_price": 99000}


@pytest.mark.parametrize("start_v", SAMPLE_VERSIONS)
def test_upgrade_from_populated_version_reaches_head(
    tmp_db_path, session_factory, app_engine, start_v
):
    """DB populated at start_v upgrades to head with sentinels intact."""
    from app.rms.db import init_db

    # app_engine already created tables + ran to head; rewind the version
    # marker so init_db replays the chain from start_v over the data.
    with app_engine.connect() as conn:
        _set_version(conn, start_v)

    sent = _sentinels(session_factory)

    # Boot path: init_db must run every migration start_v+1..head cleanly.
    # (Re-running additive migrations over existing columns must no-op via
    # the _add_column_if_missing guards.)
    init_db(app_engine)

    with app_engine.connect() as conn:
        from app.rms.db import schema_version as sv
        assert sv(conn) == CURRENT_SCHEMA_VERSION

    with session_factory() as s:
        from app.rms.models import Ingredient, Product, Recipe

        ing = s.get(Ingredient, sent["ing"])
        rec = s.get(Recipe, sent["rec"])
        prod = s.get(Product, sent["prod"])
        assert ing is not None and rec is not None and prod is not None
        assert ing.purchase_price_gs == sent["ing_price"]
        assert abs(ing.stock_qty - sent["ing_stock"]) < 1e-9
        assert prod.sale_price_gs == sent["prod_price"]
        assert len(rec.lines) == 1


def test_migration_registry_is_contiguous():
    """Every version 1..CURRENT_SCHEMA_VERSION has exactly one migration."""
    from app.rms.db import MIGRATIONS

    for v in range(1, CURRENT_SCHEMA_VERSION + 1):
        assert v in MIGRATIONS, f"missing migration for v{v}"
    extra = set(MIGRATIONS) - set(range(1, CURRENT_SCHEMA_VERSION + 1))
    assert not extra, f"migrations beyond head: {sorted(extra)}"
