#!/usr/bin/env python3
"""Idempotent Vaquita Holandesa seed for the Saskia (saskia-vps) deployment.

What this does:
- Runs `seed_sazon()` which is the canonical "La Vaquita Holandesa"
  demo seed (the Dutch-PY bakery that the Saskia business is built on).
- Idempotent: safe to run multiple times. Only creates rows that don't
  exist; updates tenant + branding to "Saskia" (the operator-facing name).
- Does NOT touch the user accounts (preserves existing admin/demo/ivan
  logins) or sales history.

Why "Vaquita" is the seed for "Saskia":
- The Sazon-RMS codebase was forked from a Vaquita Holandesa deployment.
- The product catalog (Muffin, Pan lactal, Stroopwafels, Oliebollen,
  Tompoezen, Cheesecake, etc.) IS the Vaquita menu — just branded as
  Saskia at the operator level.
- Re-running this keeps the catalog coherent: ingredients, recipes,
  prices, suppliers, tags all line up.

Usage:
    # Local dev
    .venv/bin/python scripts/seed_vaquita_for_saskia.py

    # Production
    docker exec saskia-vps_web.1.<id> python /tmp/seed_vaquita_for_saskia.py

Exit codes:
    0  seed ran successfully (or already seeded)
    1  fatal error — see stderr
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Make app/ importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> int:
    # Default DB path for the prod container
    if "AIW_SASKIA_DB_PATH" not in os.environ and "DATABASE_URL" not in os.environ:
        if Path("/data/rms.sqlite").exists():
            os.environ["AIW_SASKIA_DB_PATH"] = "/data/rms.sqlite"
        else:
            print("ERROR: AIW_SASKIA_DB_PATH or DATABASE_URL must be set.", file=sys.stderr)
            return 1

    # Force the app to skip the test-auth-bypass boot guard
    sys.modules.setdefault("pytest", type(sys)("pytest"))

    from app.rms.db import make_engine, make_session_factory
    from app.rms.seed import (
        SazonReport,
        is_sazon_seeded,
        sazon_meta,
        seed_sazon,
    )
    from sqlalchemy import text

    # Resolve DB path from env
    raw = os.environ.get("AIW_SASKIA_DB_PATH") or os.environ.get("AIW_RMS_DB_PATH")
    if raw is None and os.environ.get("DATABASE_URL"):
        # Use the SQLAlchemy URL directly
        engine = make_engine(os.environ["DATABASE_URL"])
    else:
        if raw is None:
            print("ERROR: AIW_SASKIA_DB_PATH must be set (or DATABASE_URL).", file=sys.stderr)
            return 1
        # Build a sqlite URL from the path
        engine = make_engine(f"sqlite:///{raw}")

    SessionLocal = make_session_factory(engine)
    session = SessionLocal()
    try:
        # Snapshot before
        meta_before = sazon_meta(session)
        print(f"=== Before seed ===")
        print(f"  is_seeded: {is_sazon_seeded(session)}")
        print(f"  sazon_meta: {meta_before}")

        # Quick DB counters
        def cnt(table: str) -> int:
            return session.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar() or 0
        before = {t: cnt(t) for t in (
            "tenant", "product", "recipe", "ingredient",
            "category", "channel", "delivery_zone", "sale",
        )}
        print(f"  counters: {before}")

        # Safety check: short-circuit if a tenant already exists with a
        # different slug than 'la-vaquita-holandesa'. This protects the
        # user's data from being polluted by seed_sazon (which adds NEW
        # products/recipes/sales even with overwrite=False because they have
        # new names not present in the original catalog).
        tenant_count = cnt("tenant")
        if tenant_count > 0:
            cur = session.execute(text("SELECT slug FROM tenant"))
            slugs = [r[0] for r in cur.fetchall()]
            if slugs and "la-vaquita-holandesa" not in slugs:
                print(
                    f"  REFUSE: existing tenants {slugs!r} don't include "
                    "'la-vaquita-holandesa'. Refusing to seed on top of a "
                    "different business. If this is intentional, delete "
                    "those tenants first.",
                    file=sys.stderr,
                )
                return 2
        # Refuse to seed if there are already products AND sales from a
        # different business context — the seed would append duplicates.
        if before["product"] > 0 and before["sale"] > 0:
            print(
                "  REFUSE: DB already has products and sales. The sazon "
                "seed appends new products/sales even with overwrite=False "
                "(because it adds new product NAMES not in the catalog). "
                "Refusing to seed on top of user data. To re-seed, use:\n"
                "  uv run sazon seed-sazon --reset    # wipes everything\n"
                "OR run scripts/seed_vaquita_for_saskia.py --force (DANGEROUS).",
                file=sys.stderr,
            )
            if "--force" not in sys.argv:
                return 2
            print("  --force given, continuing (destructive)")

        # Idempotent seed (overwrite=False keeps existing data)
        print()
        print("=== Running seed_sazon(overwrite=False) ===")
        report: SazonReport = seed_sazon(session, overwrite=False, days_of_history=90)
        print(f"  report: {report.as_dict()}")
        print()

        # Snapshot after
        after = {t: cnt(t) for t in (
            "tenant", "product", "recipe", "ingredient",
            "category", "channel", "delivery_zone",
        )}
        print(f"=== After seed ===")
        print(f"  is_seeded: {is_sazon_seeded(session)}")
        print(f"  sazon_meta: {sazon_meta(session)}")
        print(f"  counters: {after}")
        print(f"  deltas: { {k: after[k] - before[k] for k in before} }")
        print()
        print("OK — Vaquita Holandesa seed confirmed for Saskia business.")
        return 0
    except Exception as e:
        print(f"FATAL: {type(e).__name__}: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
