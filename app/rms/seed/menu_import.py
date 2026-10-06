"""Real-menu importer: client's carta CSV → Sazón products (matched to pack).

Sales-asset flow (task B): a prospect sends their carta (Excel export → CSV
with columns like nombre/producto, precio, categoria) and we produce a
reviewed import into a demo tenant seeded from their industry pack:

    from app.rms.seed.menu_import import import_menu_csv
    report = import_menu_csv(session, "carta_don_carlos.csv", dry_run=True)
    report = import_menu_csv(session, "carta_don_carlos.csv", dry_run=False)

Matching is accent/case-insensitive with difflib fallback (≥0.82). Matched
products get the client's real price; unmatched rows become new products
tagged "importado (pendiente recosteo)" — recipes are NOT invented, they are
flagged so costing follows with the client's real insumos.
"""

from __future__ import annotations

import csv
import difflib
import io
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.rms.models_legacy import Product

_MATCH_CUTOFF = 0.82


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return " ".join(ch for ch in s.split() if ch)


def _parse_price(raw: str | None) -> int | None:
    if not raw:
        return None
    cleaned = "".join(c for c in str(raw) if c.isdigit())
    if not cleaned:
        return None
    try:
        return int(Decimal(cleaned))
    except (InvalidOperation, ValueError):
        return None


@dataclass
class MenuRow:
    name: str
    price_gs: int | None
    category: str | None
    action: str = ""  # matched | price_updated | created | no_price_matched
    product_id: int | None = None
    pack_price: int | None = None


@dataclass
class MenuImportReport:
    rows: list[MenuRow] = field(default_factory=list)
    dry_run: bool = True

    @property
    def counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for r in self.rows:
            out[r.action] = out.get(r.action, 0) + 1
        return out

    def summary(self) -> str:
        c = self.counts
        return (
            f"{'[DRY-RUN] ' if self.dry_run else ''}"
            f"{len(self.rows)} filas: {c.get('matched', 0)} ya estaban, "
            f"{c.get('price_updated', 0)} precios actualizados, "
            f"{c.get('created', 0)} nuevos (recostear), "
            f"{c.get('no_price_matched', 0)} sin precio"
        )


def _load_rows(csv_text: str) -> list[MenuRow]:
    reader = csv.DictReader(io.StringIO(csv_text))
    rows: list[MenuRow] = []
    for raw in reader:
        keys = {(_norm(k) or ""): k for k in raw.keys() if k}
        name_key = next((keys[k] for k in ("nombre", "producto", "product", "name", "item") if k in keys), None)
        price_key = next((keys[k] for k in ("precio", "price", "precio gs", "precio_gs") if k in keys), None)
        cat_key = next((keys[k] for k in ("categoria", "category", "rubro") if k in keys), None)
        if not name_key or not (raw.get(name_key) or "").strip():
            continue
        rows.append(
            MenuRow(
                name=raw[name_key].strip(),
                price_gs=_parse_price(raw.get(price_key)),
                category=(raw.get(cat_key) or "").strip() or None,
            )
        )
    return rows


def import_menu_csv(session: Session, csv_text: str, *, dry_run: bool = True) -> MenuImportReport:
    """Import a real menu CSV into the current (pack-seeded) tenant."""
    report = MenuImportReport(dry_run=dry_run)
    existing = list(session.scalars(select(Product)).all())
    by_norm: dict[str, Product] = {_norm(p.name): p for p in existing}

    for row in _load_rows(csv_text):
        key = _norm(row.name)
        product = by_norm.get(key)
        if product is None:
            close = difflib.get_close_matches(key, list(by_norm), n=1, cutoff=_MATCH_CUTOFF)
            product = by_norm[close[0]] if close else None
        if product is not None:
            row.product_id = product.id
            row.pack_price = product.sale_price_gs
            if row.price_gs is None:
                row.action = "no_price_matched"
            elif product.sale_price_gs != row.price_gs:
                row.action = "price_updated"
                if not dry_run:
                    product.sale_price_gs = row.price_gs
            else:
                row.action = "matched"
        else:
            row.action = "created"
            if not dry_run:
                product = Product(
                    name=row.name,
                    sale_price_gs=row.price_gs or 0,
                    portion_label="1 unidad",
                    category=row.category,
                    notes="Importado de carta real — pendiente recosteo",
                    tags="importado",
                )
                session.add(product)
                session.flush()
                by_norm[key] = product
                row.product_id = product.id
        report.rows.append(row)

    if not dry_run:
        session.commit()
    return report
