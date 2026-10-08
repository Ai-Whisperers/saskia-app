"""# allow-hardcoded-dates: fixtures intentionally pin fixed dates (calendar edges, tz math, far-future sentinels); asserted relative to frozen or explicit anchors.
tests/test_reclassify_sale_channels.py — SASKIA-204 channel normalization + reclassify.

Covers:
1. _normalize_channel (in scripts/import_herebus_data.py) maps raw values
   to canonical Channel enum values, including the new HEREBUS channels.
2. The reclassify script's reclassify() function reads a VENTAS CSV
   and produces correct stats + applies updates (smoke test using an
   in-memory SQLite DB seeded with minimal rows).
3. End-to-end: a sale with channel="mostrador" in DB + "Retail" in CSV
   gets re-classified to "retail".
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

# Make scripts/ available
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

# SASKIA-204 imports
from scripts.import_herebus_data import _normalize_channel
from scripts.reclassify_sale_channels import normalize_channel, reclassify

# ── _normalize_channel in import_herebus_data.py ──────────────────────────


class TestImportScriptNormalizeChannel:
    """The import script's _normalize_channel helper must agree with the
    reclassify script's normalize_channel — both consume the same raw
    values, and mismatches would silently skew future imports."""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            # Front-of-house
            ("mostrador", "mostrador"),
            ("Mostrador", "mostrador"),
            ("MOSTRADOR", "mostrador"),
            ("mostrador-encargo", "mostrador-encargo"),
            ("whatsapp", "whatsapp"),
            ("WhatsApp", "whatsapp"),
            ("WPP", "whatsapp"),
            ("WA", "whatsapp"),
            ("PedidosYa", "pedidosya"),
            ("pedidosya", "pedidosya"),
            ("Monchis", "monchis"),
            # HEREBUS channels (SASKIA-204)
            ("Retail", "retail"),
            ("RETAIL", "retail"),
            ("minorista", "retail"),
            ("Wholesale", "wholesale"),
            ("mayorista", "wholesale"),
            ("Distributor", "distributor"),
            ("Distribuidor", "distributor"),
            ("Eventual", "eventual"),
            ("Feria", "eventual"),
            # Fallback
            ("Other", "other"),
            ("Otro", "other"),
        ],
    )
    def test_normalize_case(self, raw, expected):
        assert _normalize_channel(raw) == expected

    def test_normalize_empty_returns_none(self):
        """Empty/None raw → None (caller applies the mostrador fallback)."""
        assert _normalize_channel(None) is None
        assert _normalize_channel("") is None
        assert _normalize_channel("   ") is None

    def test_normalize_unknown_returns_none(self):
        """Unknown values → None (NOT silently mapped to mostrador)."""
        # This is the bug fix: import_herebus_data used to do
        # `channel or "mostrador"` which silently collapsed
        # unknown raw values to mostrador. Now unknown values map
        # to None so the caller can decide.
        assert _normalize_channel("completely_unknown") is None


# ── reclassify_sale_channels.normalize_channel ───────────────────────────


class TestReclassifyScriptNormalizeChannel:
    """The reclassify script's normalize_channel must behave the same as
    the import script's _normalize_channel, but return Channel values
    (not None for empty input) since the reclassify script applies its
    own fallback at the SQL layer."""

    def test_normalize_unknown_returns_other(self):
        """Unknown raw values → Channel.OTHER (NOT silently mapped to
        mostrador, which was the bug we just fixed)."""
        assert normalize_channel("completely_unknown") == "other"

    def test_normalize_empty_returns_mostrador(self):
        """Empty/None raw → mostrador (the legacy fallback)."""
        assert normalize_channel(None) == "mostrador"
        assert normalize_channel("") == "mostrador"


# ── End-to-end reclassify ────────────────────────────────────────────────


class TestReclassifyEndToEnd:
    """Smoke test: build a minimal SQLite DB with one sale channel=mostrador,
    feed the reclassify script a CSV that says the row's channel is
    "Retail", confirm the script updates the row to channel=retail."""

    def test_reclassify_updates_mostrador_to_retail(self, tmp_path, monkeypatch):
        """The exact bug from SASKIA-204: a sale was imported as
        channel=mostrador when the CSV actually said "Retail". After
        running the reclassify script, the row should flip to retail."""
        # 1. Build the DB. We bypass the full app.rms.db bootstrap
        #    (which requires a Tenant + ~20 seed rows) by creating
        #    only the Sale + tenant + customer + product tables we
        #    need. To do that, monkeypatch the engine used by the
        #    reclassify script to point at our tmp DB.
        db_path = tmp_path / "reclassify_test.sqlite"
        csv_path = tmp_path / "VENTAS.csv"
        csv_path.write_text(
            "Fecha,Canal de Venta,Unidades,Total (₲)\n2026-10-01,Retail,2.0,50000\n",
            encoding="utf-8",
        )

        # Build minimal schema matching what Sale model expects
        conn = sqlite3.connect(str(db_path))
        conn.executescript("""
            CREATE TABLE tenant (
                id INTEGER PRIMARY KEY,
                name TEXT,
                slug TEXT UNIQUE,
                primary_color TEXT
            );
            INSERT INTO tenant (id, name, slug, primary_color)
                VALUES (1, 'Test', 'test', '#000000');

            CREATE TABLE product (
                id INTEGER PRIMARY KEY,
                tenant_id INTEGER,
                name TEXT,
                sku TEXT,
                unit_price_gs INTEGER,
                is_active INTEGER DEFAULT 1
            );
            INSERT INTO product (id, tenant_id, name, sku, unit_price_gs)
                VALUES (1, 1, 'Test Product', 'TEST-001', 25000);

            CREATE TABLE customer (
                id INTEGER PRIMARY KEY,
                tenant_id INTEGER,
                name TEXT,
                phone TEXT
            );
            INSERT INTO customer (id, tenant_id, name, phone)
                VALUES (1, 1, 'Walk-in', NULL);

            CREATE TABLE sale (
                id INTEGER PRIMARY KEY,
                tenant_id INTEGER,
                product_id INTEGER,
                customer_id INTEGER,
                qty REAL,
                unit_price_gs INTEGER,
                channel TEXT,
                sold_at TEXT,
                notes TEXT,
                voided_at TEXT,
                FOREIGN KEY (product_id) REFERENCES product(id),
                FOREIGN KEY (customer_id) REFERENCES customer(id)
            );
            INSERT INTO sale (tenant_id, product_id, customer_id, qty,
                             unit_price_gs, channel, sold_at)
                VALUES (1, 1, 1, 2.0, 25000, 'mostrador', '2026-10-01 00:00:00');
        """)
        conn.commit()
        conn.close()

        # 2. Monkeypatch the reclassify script's engine to point at our DB
        from sqlalchemy import create_engine

        test_engine = create_engine(f"sqlite:///{db_path}")

        import scripts.reclassify_sale_channels as rsc

        monkeypatch.setattr(rsc, "make_engine", lambda: test_engine)

        # 3. Run the reclassify (NOT dry_run — we want the actual update)
        stats = reclassify(csv_path, dry_run=False)

        # 4. Verify the row was updated
        conn = sqlite3.connect(str(db_path))
        row = conn.execute("SELECT channel FROM sale WHERE id = 1").fetchone()
        conn.close()

        assert row[0] == "retail", f"Expected retail, got {row[0]!r}"
        assert stats["rows_updated"] >= 1

    def test_reclassify_dry_run_does_not_update(self, tmp_path, monkeypatch):
        """--dry-run (default) must not mutate the DB."""
        db_path = tmp_path / "reclassify_test.sqlite"
        csv_path = tmp_path / "VENTAS.csv"
        csv_path.write_text(
            "Fecha,Canal de Venta,Unidades,Total (₲)\n2026-10-01,Wholesale,3.0,75000\n",
            encoding="utf-8",
        )

        conn = sqlite3.connect(str(db_path))
        conn.executescript("""
            CREATE TABLE tenant (id INTEGER PRIMARY KEY, name TEXT, slug TEXT UNIQUE, primary_color TEXT);
            INSERT INTO tenant VALUES (1, 'Test', 'test', '#000');
            CREATE TABLE product (id INTEGER PRIMARY KEY, tenant_id INTEGER, name TEXT, sku TEXT, unit_price_gs INTEGER, is_active INTEGER DEFAULT 1);
            INSERT INTO product VALUES (1, 1, 'P', 'S', 25000, 1);
            CREATE TABLE customer (id INTEGER PRIMARY KEY, tenant_id INTEGER, name TEXT, phone TEXT);
            INSERT INTO customer VALUES (1, 1, 'Walk-in', NULL);
            CREATE TABLE sale (id INTEGER PRIMARY KEY, tenant_id INTEGER, product_id INTEGER, customer_id INTEGER, qty REAL, unit_price_gs INTEGER, channel TEXT, sold_at TEXT, notes TEXT, voided_at TEXT);
            INSERT INTO sale (tenant_id, product_id, customer_id, qty, unit_price_gs, channel, sold_at) VALUES (1, 1, 1, 3.0, 25000, 'mostrador', '2026-10-01 00:00:00');
        """)
        conn.commit()
        conn.close()

        from sqlalchemy import create_engine

        test_engine = create_engine(f"sqlite:///{db_path}")

        import scripts.reclassify_sale_channels as rsc

        monkeypatch.setattr(rsc, "make_engine", lambda: test_engine)

        stats = reclassify(csv_path, dry_run=True)
        assert stats["rows_updated"] == 0

        # DB is unchanged
        conn = sqlite3.connect(str(db_path))
        row = conn.execute("SELECT channel FROM sale WHERE id = 1").fetchone()
        conn.close()
        assert row[0] == "mostrador"
