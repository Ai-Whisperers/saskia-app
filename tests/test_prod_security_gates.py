"""tests/test_prod_security_gates.py — PRO-SEC + PRO-PRICE guards (2026-09-30).

Two CI gates born from the 2026-09-30 audit:

1. PRO-SEC: production once ran with SASKIA_TEST_AUTH_DISABLED=1 (the whole
   app served without login). This guard fails if the bypass var is set
   anywhere it shouldn't be (repo files) or if the runtime guard was removed
   from app/rms/main.py.

2. PRO-PRICE: no sellable product may be priced below 1.1× its full unit
   cost (ingredients + labor). Catches "loss-making menu items" before they
   reach the menu. Uses the prod-shaped seed if present; otherwise passes
   vacuously (CI fixtures have no products).
"""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# Files where the bypass var would be a production risk (deploy/runtime paths).
_DANGEROUS_FILES = (
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "app/main.py",
    "app/rms/main.py",
    "scripts/deploy.sh",
    "scripts/deploy-to-vps.sh",
)


def test_prosec_bypass_not_wired_in_deploy_paths():
    """PRO-SEC: the auth bypass must not be set in any deploy/runtime path."""
    offenders: list[str] = []
    for name in _DANGEROUS_FILES:
        p = REPO_ROOT / name
        if not p.exists():
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if "SASKIA_TEST_AUTH_DISABLED" in line and (
                "setdefault" in line or "ENV " in line or "=" in line
            ):
                offenders.append(f"{name}: {stripped[:90]}")
    assert not offenders, (
        "SASKIA_TEST_AUTH_DISABLED aparece en archivos de deploy/runtime "
        f"(solo tests pueden usarlo): {offenders}"
    )


def test_prosec_runtime_guard_present():
    """The boot-time guard must stay in app/rms/main.py (fail loud at startup)."""
    main = (REPO_ROOT / "app" / "rms" / "main.py").read_text(encoding="utf-8")
    assert "SASKIA_TEST_AUTH_DISABLED" in main, (
        "El guard de arranque contra SASKIA_TEST_AUTH_DISABLED fue removido "
        "de app/rms/main.py — restaurarlo (incidente 2026-09-30)."
    )


def test_proprice_no_sellable_product_below_110pct_of_cost():
    """PRO-PRICE: ningún producto activo vendible por debajo de costo×1,1.

    Corre contra la DB si existe (local/prod-shape). En CI sin DB de negocio
    pasa vacío (no hay productos que auditar).
    """
    db_path = os.environ.get("AIW_SASKIA_DB_PATH", "/tmp/rms-latest.sqlite")
    if not Path(db_path).exists():
        import pytest

        pytest.skip("sin DB de negocio disponible (CI limpio)")

    from decimal import Decimal

    from sqlalchemy import create_engine

    from app.rms.costing import product_unit_cost_gs
    from app.rms.db import make_session_factory
    from app.rms.models_legacy import Product

    engine = create_engine(f"sqlite:///{db_path}")
    S = make_session_factory(engine)()
    offenders = []
    for p in S.query(Product).filter(Product.is_available.is_(True)).all():
        if p.recipe_id is None or not p.sale_price_gs:
            continue
        res = product_unit_cost_gs(S, p.id)
        cost = res.batch_cost_gs
        if cost is None or cost <= 0:
            continue
        floor = int(Decimal(cost) * Decimal("1.1"))
        if p.sale_price_gs < floor:
            offenders.append(
                f"{p.name}: venta {p.sale_price_gs:,} < costo×1,1 = {floor:,} "
                f"(costo completo {cost:,})"
            )
    S.close()
    assert not offenders, (
        "Productos activos con precio < costo×1,1 (venta a pérdida o casi): " + "; ".join(offenders)
    )
