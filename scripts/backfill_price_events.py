"""One-off: backfill historical ingredient price events (freshness/price-history seed).

Run inside the prod container. Creates 3 synthetic past price events per
ingredient (−60d/−40d/−20d at 0.93/0.97/0.99 × current price) so the
freshness flags and price-stat strips have data to work with. Source is
marked 'backfill' so it's distinguishable from real events.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.rms.db import make_engine
from app.rms.models_legacy import Ingredient, IngredientPriceEvent

e = make_engine()
s = sessionmaker(bind=e)()
now = datetime.now(timezone.utc)
count = 0
ings = s.scalars(select(Ingredient).where(Ingredient.purchase_price_gs.isnot(None))).all()
for ing in ings:
    base = ing.purchase_price_gs
    for days_ago, jitter in [(-60, 0.93), (-40, 0.97), (-20, 0.99)]:
        s.add(IngredientPriceEvent(
            ingredient_id=ing.id,
            price_gs=int(base * jitter),
            recorded_at=now + timedelta(days=days_ago),
            source="backfill",
        ))
        count += 1
s.commit()
total = s.scalar(select(func.count(IngredientPriceEvent.id)))
print(f"inserted {count} price events for {len(ings)} ingredients; total now {total}")
