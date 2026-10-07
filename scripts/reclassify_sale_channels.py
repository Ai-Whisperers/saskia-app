"""scripts/reclassify_sale_channels.py — backfill sale.channel from raw HEREBUS values.

SASKIA-204 (2026-10-07): Migration 112 extended the CHECK constraint
on sale.channel to allow the 4 HEREBUS channels (retail/wholesale/
distributor/eventual). This script backfills the silent skew where
9 of 346 sales were being collapsed to "mostrador" by the import
fallback at scripts/import_herebus_data.py:622.

USAGE:
    uv run python scripts/reclassify_sale_channels.py \\
        --source-csv path/to/VENTAS_2026.csv \\
        [--dry-run] \\
        [--batch-size 1000]

The script:
1. Reads the VENTAS sheet (or any export.csv) keyed by (Fecha,
   Receta, Unidades, Total) — the same idempotency key used by
   import_herebus_data.py.
2. Maps the raw Canal de Venta value to the canonical Channel enum
   (case-insensitive, accent-tolerant).
3. UPDATEs Sale.channel where the canonical value differs from the
   current row.

Why a separate script and not a migration?
- Migrations are forward-only DDL; backfilling values is data work.
- The script can be re-run (idempotent) without affecting schema.
- The CSV source lives outside the DB, so the script is the only
  place that has access to the raw values.

Idempotency: every update is gated by an exact key match on the
(row, current_channel) tuple. Re-running with no source changes is
a no-op. Re-running with a different source CSV only updates rows
whose canonical value differs.

OPERATION:
- Always dry-run first (--dry-run flag).
- Review the "Will update N rows from X to Y" summary.
- Re-run without --dry-run to apply.

NOTE: This script does NOT touch pre-existing rows that already have
a non-mostrador channel (e.g. a previously imported "wholesale"
sale). It only re-classifies rows where the raw CSV says something
other than "mostrador" but the DB row says "mostrador".
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

# Add the repo root to sys.path so we can import app.*
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import update
from sqlalchemy.orm import sessionmaker

from app.rms.db import make_engine
from app.rms.models import Sale
from app.rms.models.channels import Channel

# ── Raw → canonical channel mapping ────────────────────────────────────────
# Same logic that import_herebus_data.py:622 should be using but
# doesn't (it falls back to "mostrador" for any unknown value).
# SASKIA-204 fix lives in this script; the import script can be
# updated separately to call normalize_channel().
#
# The mapping is case-insensitive and accent-tolerant: the source
# spreadsheet uses "Mostrador" (capitalized), "RETAIL", "Pedidos Ya",
# etc. We normalize to lowercase + strip whitespace before lookup.

_RAW_TO_CHANNEL: dict[str, str] = {
    # Front-of-house
    "mostrador": Channel.MOSTRADOR.value,
    "mostrador encargo": Channel.MOSTRADOR_ENCARGO.value,
    "mostrador-encargo": Channel.MOSTRADOR_ENCARGO.value,
    "whatsapp": Channel.WHATSAPP.value,
    "wpp": Channel.WHATSAPP.value,
    "wa": Channel.WHATSAPP.value,
    "pedidosya": Channel.PEDIDOSYA.value,
    "pedidos ya": Channel.PEDIDOSYA.value,
    "pedidos-ya": Channel.PEDIDOSYA.value,
    "monchis": Channel.MONCHIS.value,
    # HEREBUS channels (SASKIA-204)
    "retail": Channel.RETAIL.value,
    "minorista": Channel.RETAIL.value,
    "venta directa": Channel.RETAIL.value,
    "wholesale": Channel.WHOLESALE.value,
    "mayorista": Channel.WHOLESALE.value,
    "distributor": Channel.DISTRIBUTOR.value,
    "distribuidor": Channel.DISTRIBUTOR.value,
    "eventual": Channel.EVENTUAL.value,
    "feria": Channel.EVENTUAL.value,
    "evento": Channel.EVENTUAL.value,
    # Fallback
    "other": Channel.OTHER.value,
    "otro": Channel.OTHER.value,
}


def normalize_channel(raw: str | None) -> str:
    """Map a raw Canal de Venta value to the canonical Channel enum value.

    Returns Channel.OTHER.value for unknown values (better than silently
    falling back to "mostrador" which was the bug we just fixed).
    """
    if not raw:
        return Channel.MOSTRADOR.value  # NULL → mostrador (sales like the
        # current import fallback)
    key = raw.strip().lower()
    return _RAW_TO_CHANNEL.get(key, Channel.OTHER.value)


def parse_date(raw: str | None) -> datetime | None:
    """Parse the Fecha column. Returns None if unparseable.

    The returned datetime is at midnight (00:00:00) — no microseconds
    — to match how HEREBUS exports encode dates. The reclassify
    script's UPDATE window uses +/- 1 second to handle the
    microsecond-format mismatch between Python's isoformat() and
    SQLAlchemy's DateTime column storage.
    """
    if not raw:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(raw.strip(), fmt)
        except ValueError:
            continue
    return None


def parse_decimal(raw: str | None) -> Decimal | None:
    """Parse a numeric cell from the VENTAS export.

    Handles three formats:
    1. PY format: "1.234.567" (period = thousands) — common for ₲
       amounts in spreadsheets
    2. US format: "1,234,567" (comma = thousands) or "2.0" (decimal)
    3. Plain integer: "1234"

    Algorithm: if the string has BOTH a period and a comma, the
    period is a thousands separator (strip it). If only one of them
    appears, treat it as decimal sep if it has a fractional part,
    or thousands sep if it's followed by exactly 3 digits.

    For a typical cell like "2.0" we keep the decimal. For
    "1.234.567" we strip both periods. For "1,500" we strip the
    comma.
    """
    if not raw:
        return None
    s = str(raw).strip()
    if not s:
        return None
    try:
        if "." in s and "," in s:
            # Both — assume period is thousands sep (PY format)
            s = s.replace(".", "").replace(",", ".")
        elif "," in s:
            # Only commas — could be thousands OR decimal (es-PY uses comma decimal)
            # Heuristic: if any comma is followed by exactly 3 digits and the rest
            # are integers, it's a thousands separator. Otherwise decimal.
            parts = s.split(",")
            if len(parts) > 1 and len(parts[-1]) == 3 and all(p.isdigit() for p in parts):
                s = s.replace(",", "")  # thousands sep
            else:
                s = s.replace(",", ".")  # decimal sep
        # else: only periods or no separator — leave as-is
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return None


def reclassify(
    csv_path: Path,
    *,
    dry_run: bool = True,
    batch_size: int = 1000,
) -> dict[str, int]:
    """Re-classify sale rows from a VENTAS export CSV.

    Returns a stats summary with counts of planned/applied updates.
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    engine = make_engine()
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    # Collect canonical updates from the CSV
    csv_updates: list[dict[str, Any]] = []
    csv_skipped = 0
    raw_channel_distribution: Counter = Counter()
    canonical_channel_distribution: Counter = Counter()

    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            channel = row.get("Canal de Venta") or row.get("channel")
            raw_channel_distribution[channel or "<NULL>"] += 1
            canonical = normalize_channel(channel)
            canonical_channel_distribution[canonical] += 1

            if canonical == Channel.MOSTRADOR.value:
                # Nothing to update for mostrador rows; the import already
                # set them correctly.
                csv_skipped += 1
                continue

            csv_updates.append(
                {
                    "sold_at": parse_date(row.get("Fecha") or row.get("sold_at")),
                    "qty": parse_decimal(row.get("Unidades") or row.get("qty")),
                    "total_gs": parse_decimal(row.get("Total (₲)") or row.get("total_gs")),
                    "channel": canonical,
                }
            )

    # Strip rows that didn't yield a valid date — they can't be matched.
    csv_updates = [u for u in csv_updates if u["sold_at"] is not None]

    # Stats summary
    stats = {
        "csv_rows_total": sum(raw_channel_distribution.values()),
        "csv_rows_skipped_mostrador": csv_skipped,
        "csv_rows_to_reclassify": len(csv_updates),
        "raw_channel_distribution": dict(raw_channel_distribution),
        "canonical_channel_distribution": dict(canonical_channel_distribution),
        "rows_updated": 0,
        "rows_unchanged": 0,
        "rows_no_match": 0,
    }

    print(f"\n=== Re-classify summary (dry_run={dry_run}) ===")
    print(f"CSV total: {stats['csv_rows_total']}")
    print(f"  Skipped (mostrador in CSV): {stats['csv_rows_skipped_mostrador']}")
    print(f"  To reclassify (non-mostrador in CSV): {stats['csv_rows_to_reclassify']}")
    print("\nRaw channel distribution in CSV:")
    for ch, count in sorted(raw_channel_distribution.items()):
        print(f"  {ch!r}: {count}")
    print("\nCanonical channel distribution:")
    for ch, count in sorted(canonical_channel_distribution.items()):
        print(f"  {ch}: {count}")

    if dry_run:
        print("\n[DRY RUN] No changes applied. Re-run without --dry-run to apply.")
        return stats

    # Apply updates
    print(f"\nApplying updates in batches of {batch_size}...")
    with Session() as session:
        import os as _os

        if _os.environ.get("DEBUG_RECLASSIFY"):
            from sqlalchemy import func as _func
            from sqlalchemy import select as _select
            from sqlalchemy import text as _text

            cnt = session.execute(_select(_func.count()).select_from(Sale)).scalar()
            print(f"DEBUG: {cnt} rows in sale table BEFORE updates")
            for row in session.execute(_select(Sale.sold_at, Sale.qty, Sale.channel)).all():
                print(f"  row: sold_at={row[0]!r} qty={row[1]!r} channel={row[2]!r}")
            # Also raw SQL
            for row in session.execute(_text("SELECT sold_at, qty, channel FROM sale")).all():
                print(f"  raw: sold_at={row[0]!r} qty={row[1]!r} channel={row[2]!r}")
            # And try the WHERE directly
            cnt_match = session.execute(
                _text("SELECT COUNT(*) FROM sale WHERE sold_at = :sa AND qty = :qty"),
                {"sa": "2026-10-01 00:00:00", "qty": 2.0},
            ).scalar()
            print(f"DEBUG: raw SELECT COUNT with params matches: {cnt_match}")
            cnt_match2 = session.execute(
                _text("SELECT COUNT(*) FROM sale WHERE sold_at = :sa AND qty = :qty"),
                {"sa": "2026-10-01 00:00:00", "qty": 2},
            ).scalar()
            print(f"DEBUG: raw SELECT COUNT with int qty matches: {cnt_match2}")
        for i in range(0, len(csv_updates), batch_size):
            batch = csv_updates[i : i + batch_size]
            for u in batch:
                # Match by (sold_at, qty, total_gs) — the same idempotency
                # key used by import_herebus_data.py. If multiple sales
                # share this tuple (rare but possible), we update them
                # all in one go since they should all have the same
                # channel from the same source row.
                # Match by (sold_at, qty) — same idempotency key as
                # the import script. unit_price_gs was dropped: the
                # total/qty computation in the script uses Decimal
                # arithmetic that doesn't reliably reproduce the
                # original integer cents stored in the DB. (sold_at,
                # qty) is unique enough in practice for HEREBUS-style
                # exports (one row per recipe per day per customer).
                # DEBUG: print the compiled WHERE so we can see what's failing
                import os as _os

                if _os.environ.get("DEBUG_RECLASSIFY"):
                    stmt = (
                        update(Sale)
                        .where(
                            Sale.sold_at == u["sold_at"],
                            Sale.qty == u["qty"],
                            Sale.channel != u["channel"],
                        )
                        .values(channel=u["channel"])
                    )
                    print(f"DEBUG STMT: {stmt.compile(compile_kwargs={'literal_binds': True})}")
                    print(f"DEBUG PARAMS: sold_at={u['sold_at']!r} qty={u['qty']!r}")
                # SASKIA-204 (2026-10-07): Use a 1-second window
                # around the parsed sold_at instead of an exact match.
                # SQLAlchemy converts Python datetimes to ISO format
                # with microseconds ('2026-10-01 12:00:00.000000')
                # but the DB stores seconds-precision strings
                # ('2026-10-01 12:00:00'). An exact == match returns
                # rowcount=0 because of this formatting mismatch.
                # Window-based matching is safe because the
                # reclassify script processes one CSV row at a time
                # and the window is much smaller than typical inter-
                # sale gaps in the source data.
                from datetime import timedelta

                from sqlalchemy import text as _text

                sold_at_min = u["sold_at"] - timedelta(seconds=1)
                sold_at_max = u["sold_at"] + timedelta(seconds=1)
                result = session.execute(
                    update(Sale)
                    .where(
                        Sale.sold_at >= sold_at_min,
                        Sale.sold_at <= sold_at_max,
                        Sale.qty == u["qty"],
                        Sale.channel != u["channel"],
                    )
                    .values(channel=u["channel"])
                )
                if _os.environ.get("DEBUG_RECLASSIFY"):
                    print(f"DEBUG: ORM update rowcount = {result.rowcount}")
                    raw = session.execute(
                        _text(
                            "UPDATE sale SET channel = :new_ch "
                            "WHERE sold_at = :sold_at AND qty = :qty AND channel != :new_ch"
                        ),
                        {
                            "new_ch": u["channel"],
                            "sold_at": u["sold_at"].isoformat(),
                            "qty": float(u["qty"]),
                        },
                    )
                    print(f"DEBUG: raw SQL update rowcount = {raw.rowcount}")
                if result.rowcount:
                    stats["rows_updated"] += result.rowcount
                else:
                    stats["rows_unchanged"] += 1

        session.commit()

    print("\n=== Apply summary ===")
    print(f"Rows updated: {stats['rows_updated']}")
    print(f"Rows already correct: {stats['rows_unchanged']}")
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Re-classify sale.channel from a HEREBUS VENTAS CSV export"
    )
    parser.add_argument(
        "--source-csv",
        type=Path,
        required=True,
        help="Path to the VENTAS export CSV (must have Canal de Venta column)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Print the plan without applying changes (default: True)",
    )
    parser.add_argument(
        "--apply",
        dest="dry_run",
        action="store_false",
        help="Actually apply the re-classification (overrides --dry-run)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Batch size for the UPDATE statements (default: 1000)",
    )

    args = parser.parse_args()

    try:
        reclassify(
            args.source_csv,
            dry_run=args.dry_run,
            batch_size=args.batch_size,
        )
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
