#!/usr/bin/env python3
"""scripts/migrate_channels_lowercase.py — one-shot migration to lowercase channels.

Run ONCE after deploying the P39 fix to sales.py and pedidos.py.
Idempotent — running it twice is a no-op.

Fixes the 1 historical pedido row that has channel='WhatsApp' instead
of 'whatsapp' (capital W). New writes go through normalize_channel() in
pedidos.py / sales.py and will be correct from the next save onward.

Usage:
    ssh root@38.9.96.179 'docker exec -t saskia-vps_web.1.<taskid> python /tmp/migrate_channels_lowercase.py'
"""

import sqlite3

DB_PATH = "/data/rms.sqlite"


def main() -> int:
    db = sqlite3.connect(DB_PATH)
    cur = db.cursor()
    changed_pedido = cur.execute(
        "UPDATE pedido SET channel = LOWER(channel) WHERE channel != LOWER(channel)"
    ).rowcount
    changed_sale = cur.execute(
        "UPDATE sale SET channel = LOWER(channel) WHERE channel != LOWER(channel)"
    ).rowcount
    db.commit()
    print(f"pedido rows updated: {changed_pedido}")
    print(f"sale rows updated:   {changed_sale}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
