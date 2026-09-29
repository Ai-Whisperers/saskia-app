from app.rms.db import make_engine
from sqlalchemy import text

eng = make_engine()
with eng.connect() as c:
    cols = c.execute(text("PRAGMA table_info(bank_transaction)")).fetchall()
    print("bank_transaction columns:")
    for col in cols:
        print(f"  {col[1]:30} {col[2]}")
    print()
    # Schema version
    version = c.execute(text("SELECT value FROM app_meta WHERE key='schema_version'")).scalar()
    print(f"schema_version: {version}")
