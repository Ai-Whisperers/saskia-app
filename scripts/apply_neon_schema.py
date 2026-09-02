"""Apply schema to Neon. Standalone helper script."""

import os

from sqlalchemy import inspect

from app.rms.db_dialect import get_metadata, make_engine

raw = os.environ["DATABASE_URL"]
print(f"raw DATABASE_URL: {raw[:25]}...")
engine = make_engine(raw)
print(f"engine driver: {engine.url.drivername}")
metadata = get_metadata()
print(f"tables in metadata: {len(metadata.tables)}")
metadata.create_all(engine)
print("schema applied")
insp = inspect(engine)
created = sorted(insp.get_table_names(schema="public"))
print(f"verified: {len(created)} tables in DB")
for t in created:
    print(f"  - {t}")
