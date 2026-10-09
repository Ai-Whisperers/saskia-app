"""app/rms/menu_ocr.py — Fase 3: OCR de carta-foto vía GLM vision.

parse_menu_image(bytes) → lista de líneas {name, price_gs, category}
leídas del menú (prompt anti-alucinación: solo lo que se ve).
match_to_catalog(lines, session) → fuzzy-match contra Product
(reusa _norm + cutoff de menu_import) → {nuevos, matcheados, dudosos}.

Guardarraíl: el preview es OBLIGATORIO — la confirmación que inserta
la hace el router llamando import_menu_csv con las filas checkeadas.
"""

from __future__ import annotations

import base64
import difflib
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.rms.llm import MAX_IMAGE_BYTES, LLMError, chat_json

# noqa: arch-rule — reuses _norm + _MATCH_CUTOFF constants; should be moved to menu_normalize.py
from app.rms.seed.menu_import import _MATCH_CUTOFF, _norm

_OCR_PROMPT = """Leés la foto de una carta/menú de un negocio de comida en Paraguay.
Devolvé EXCLUSIVAMENTE un JSON con este formato (sin texto extra):
{"items": [{"name": "nombre del ítem", "price_gs": 15000, "category": "seccion o null"}]}
Reglas:
- Transcribí SOLO lo que se lee en la imagen. NO inventes ítems ni precios.
- price_gs es el precio en guaraníes como entero (15.000 → 15000). Si el
  ítem no tiene precio legible, price_gs = null.
- category es la sección del menú si se ve (Pizzas, Bebidas...), si no null.
- Mantené el nombre tal cual está escrito en la carta.
- Si la imagen no es una carta/menú, devolvé {"items": []}."""


@dataclass
class MenuLine:
    name: str
    price_gs: int | None = None
    category: str | None = None
    product_id: int | None = None  # set by match_to_catalog


@dataclass
class MatchResult:
    matched: list[MenuLine] = field(default_factory=list)  # con product_id
    nuevos: list[MenuLine] = field(default_factory=list)
    dudosos: list[MenuLine] = field(default_factory=list)  # match ambiguo
    product_ids: dict[int, int] = field(default_factory=dict)  # line idx→product_id


def parse_menu_image(image_bytes: bytes, *, mime: str = "image/jpeg") -> list[MenuLine]:
    """Imagen → líneas de menú vía GLM vision. Raises LLMError."""
    if not image_bytes:
        raise LLMError("Imagen vacía")
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise LLMError("Imagen demasiado grande (máximo 8MB)")
    b64 = base64.b64encode(image_bytes).decode()
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                {"type": "text", "text": _OCR_PROMPT},
            ],
        }
    ]
    data = chat_json(messages, max_tokens=4000, temperature=0.1)
    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise LLMError("Respuesta OCR sin lista de ítems")
    lines: list[MenuLine] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        name = str(it.get("name") or "").strip()
        if not name:
            continue
        price = it.get("price_gs")
        price_gs: int | None
        try:
            price_gs = int(price) if price is not None else None
        except (TypeError, ValueError):
            price_gs = None
        cat = it.get("category")
        lines.append(MenuLine(name=name, price_gs=price_gs, category=str(cat) if cat else None))
    return lines


def match_to_catalog(lines: list[MenuLine], session: Session) -> MatchResult:
    """Fuzzy-match de líneas OCR contra Product existentes."""
    from app.rms.models_legacy import Product

    res = MatchResult()
    existing = list(session.scalars(select(Product)).all())
    by_norm: dict[str, Product] = {_norm(p.name): p for p in existing}

    for line in lines:
        key = _norm(line.name)
        product = by_norm.get(key)
        if product is None:
            close = difflib.get_close_matches(key, list(by_norm), n=2, cutoff=_MATCH_CUTOFF)
            if len(close) == 1:
                product = by_norm[close[0]]
            elif len(close) > 1:
                res.dudosos.append(line)  # ambiguo: 2 candidatos
                continue
        if product is not None:
            line.product_id = product.id
            res.matched.append(line)
            res.product_ids[id(line)] = product.id
        else:
            res.nuevos.append(line)
    return res
