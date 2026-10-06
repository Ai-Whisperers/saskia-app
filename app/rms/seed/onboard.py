"""One-command tenant onboarding: pack + demo life + credentials.

    from app.rms.seed.onboard import onboard_tenant
    report = onboard_tenant(session, "Pizzería Don Carlos", pack="Pizzería")

Creates: Tenant (business_name, PYG), admin user (bcrypt password,
default "cambiar1234" — force a change on first login), the full market
pack (products/recipes/ingredients/suppliers/payments/zones/production
templates) and 90 days of demo life (customers, pedidos, sales, stock).

NO OP called automatically by import — onboarding is always explicit.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.rms.seed.pack_demo import seed_pack_demo
from app.rms.seed.packs import PACKS, seed_pack


def onboard_tenant(
    session: Session,
    tenant_name: str,
    pack: str,
    days_of_history: int = 90,
    seed: int | None = None,
) -> dict:
    """Create a fully seeded tenant in one call. Idempotent per pack data."""
    if pack not in PACKS:
        raise ValueError(f"pack desconocido: {pack!r}. Válidos: {', '.join(sorted(PACKS))}")
    pack_report = seed_pack(session, pack, tenant_name=tenant_name)
    demo_report = seed_pack_demo(
        session, days_of_history=days_of_history, seed=seed, customers_total=42
    )
    return {
        "tenant": tenant_name,
        "pack": pack,
        "pack_report": pack_report,
        "demo": demo_report,
        "login": {"usuario": "admin", "password_inicial": "cambiar1234"},
    }


def onboarding_summary(report: dict) -> str:
    pr = report["pack_report"]
    d = report["demo"]
    lines = [
        f"✅ Tenant: {report['tenant']} (pack {report['pack']})",
        f"   Productos: {pr.products} · Recetas: {pr.recipes} · Ingredientes: {pr.ingredients}",
        f"   Clientes demo: {d['customers']} · Pedidos: {d['pedidos']} · Ventas 90d: {d['sales']}",
        f"   Login: {report['login']['usuario']} / {report['login']['password_inicial']} (cambiar en 1er login)",
    ]
    return "\n".join(lines)
