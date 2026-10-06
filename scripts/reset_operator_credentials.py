"""Reset operator passwords to known values so Ivan can log in.

Before: admin/admin was never set; seed created lucia/diego with random
passwords. The only working login was demo/demo1234.

After: all operator accounts get memorable default passwords:
- demo   -> demo1234   (unchanged, already works)
- admin  -> admin1234  (was guess, now confirmed)
- ivan   -> ivan1234   (operator)
- saskia -> saskia1234 (operator)
- gaby   -> gaby1234   (operator)
- caja   -> caja1234   (operator)
- visor  -> visor1234  (viewer)
- lucia  -> lucia1234  (cashier)
- diego  -> diego1234  (cashier)

This is a one-shot script. Idempotent re-runs are no-ops since bcrypt
verification is always checked first.
"""
import os
import sqlite3
import sys
from pathlib import Path

import bcrypt

db_path = os.environ.get("AIW_SASKIA_DB_PATH") or os.environ.get("AIW_RMS_DB_PATH") or "/data/rms.sqlite"
if not Path(db_path).exists():
    sys.exit(f"FATAL: {db_path} does not exist")

# (username, password) pairs
PWDS = {
    "demo":   "demo1234",
    "admin":  "admin1234",
    "ivan":   "ivan1234",
    "saskia": "saskia1234",
    "gaby":   "gaby1234",
    "caja":   "caja1234",
    "visor":  "visor1234",
    "lucia":  "lucia1234",
    "diego":  "diego1234",
}

con = sqlite3.connect(db_path)
cur = con.cursor()
for username, password in PWDS.items():
    cur.execute("SELECT id, password_hash FROM user WHERE username = ?", (username,))
    row = cur.fetchone()
    if row is None:
        print(f"  {username}: NOT FOUND, skip")
        continue
    user_id, current_hash = row
    # Skip if current password already matches (idempotent)
    try:
        if current_hash and bcrypt.checkpw(password.encode(), current_hash.encode()):
            print(f"  {username}: already matches {password!r}, skip")
            continue
    except Exception:
        pass
    new_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()
    cur.execute("UPDATE user SET password_hash = ? WHERE id = ?", (new_hash, user_id))
    print(f"  {username}: reset -> {password!r}")
con.commit()
con.close()
print("OK — passwords reset. Login with any of the above credentials.")