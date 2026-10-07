"""app/rms/held_sales.py — pause/resume in-progress carts.

Ported from Hao0321/pos-pro (MIT-licensed, src/components/CartPanel.jsx
"hold" / 掛單 pattern). The web POS lets the cashier pause a
multi-line cart when a customer steps away mid-order, then resume it
(or another operator resume it) when the customer returns.

Schema (see _110_held_sale migration):
    held_sale(
        id PK, held_at TIMESTAMP, held_by VARCHAR(120),
        label VARCHAR(120), cart_json TEXT, status VARCHAR(20)
    )

Operations:
    hold_cart(session, cart_dict, held_by, label) -> HeldSale
    list_active_held(session) -> list[HeldSale]
    get_held(session, held_id) -> HeldSale | None
    resume_held(session, held_id) -> dict   (parses cart_json)
    discard_held(session, held_id) -> bool  (status=discarded)

Atomicity guarantees:
- INSERT / UPDATE of cart_json is wrapped in the same transaction as
  the row write (single SQLAlchemy session.commit).
- resume_held does NOT delete the row; it returns the parsed payload
  and the caller decides whether to commit the subsequent sale. If
  the sale creation fails, the held_sale row is preserved (operator
  can recover manually).

Cap: SAZON_MAX_HELD_SALES (default 50). When the cap is hit, the
oldest active held sale is evicted FIFO (status=auto_evicted).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from loguru import logger
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.rms.clock import ASUNCION_TZ, to_asuncion  # noqa: F401 — re-exported
from app.rms.clock import now as now_utc
from app.rms.config import SAZON_MAX_HELD_SALES


def _now_asuncion() -> datetime:
    """UTC-aware now → Asuncion-local naive (matches DB TIMESTAMP contract)."""
    return to_asuncion(now_utc()).replace(tzinfo=None)


@dataclass(frozen=True)
class HeldSaleRow:
    """In-process view of one held_sale row (not a SQLAlchemy model)."""

    id: int
    held_at: str  # ISO string (Asunción local)
    held_by: str
    label: str
    cart_json: str
    status: str

    def parse_cart(self) -> dict:
        """Return the deserialized cart payload."""
        try:
            return json.loads(self.cart_json)
        except (json.JSONDecodeError, TypeError) as exc:
            raise ValueError(f"held_sale {self.id} has invalid cart_json: {exc}") from exc


def _row_to_held(row: Any) -> HeldSaleRow:
    """Convert a SQLAlchemy Row to HeldSaleRow dataclass."""
    return HeldSaleRow(
        id=row.id,
        held_at=row.held_at,
        held_by=row.held_by,
        label=row.label,
        cart_json=row.cart_json,
        status=row.status,
    )


def _evict_oldest_if_at_capacity(session: Session) -> int:
    """Evict oldest active held sales until we have room.

    Returns the number of evictions performed. SAZON_MAX_HELD_SALES
    default is 50. When the cap is hit, we mark the oldest active
    rows as 'auto_evicted' (preserving audit trail).
    """
    cap = SAZON_MAX_HELD_SALES
    active_count = session.execute(
        text("SELECT COUNT(*) FROM held_sale WHERE status = 'active'")
    ).scalar_one()
    if active_count < cap:
        return 0
    evict_count = active_count - cap + 1  # +1 to make room for the new row
    result = session.execute(
        text(
            """
            SELECT id FROM held_sale
            WHERE status = 'active'
            ORDER BY held_at ASC
            LIMIT :n
            """
        ),
        {"n": evict_count},
    )
    evict_ids = [r[0] for r in result.fetchall()]
    if evict_ids:
        # SQLite does not accept ``IN :param`` with a tuple — expand inline.
        # Safe because the ids come from a SELECT we just issued.
        placeholders = ",".join(f":ev_id_{i}" for i in range(len(evict_ids)))
        params = {f"ev_id_{i}": v for i, v in enumerate(evict_ids)}
        session.execute(
            text(
                f"UPDATE held_sale SET status = 'auto_evicted' "  # noqa: S608 — bound params, see above
                f"WHERE id IN ({placeholders}) AND status = 'active'"
            ),
            params,
        )
        logger.info(
            "held_sale auto-evicted {count} rows (cap={cap})",
            count=len(evict_ids),
            cap=cap,
        )
    return len(evict_ids)


def hold_cart(
    session: Session,
    cart: dict[str, Any],
    *,
    held_by: str,
    label: str,
) -> HeldSaleRow:
    """Persist a paused cart and return its HeldSaleRow.

    Args:
        session: active SQLAlchemy session.
        cart: dict with at least an 'items' key (list of line dicts).
        held_by: cashier/operator name (for audit).
        label: free-text label, e.g. "Cliente Juan - fue al cajero".
    """
    if not isinstance(cart, dict):
        raise ValueError("cart must be a dict")
    if "items" not in cart:
        raise ValueError("cart must contain 'items' key")
    if not isinstance(cart["items"], list):
        raise ValueError("cart['items'] must be a list")
    label_norm = (label or "").strip()[:120] or "sin etiqueta"

    _evict_oldest_if_at_capacity(session)
    now = _now_asuncion()
    cart_json = json.dumps(cart, ensure_ascii=False, separators=(",", ":"))
    result = session.execute(
        text(
            """
            INSERT INTO held_sale (held_at, held_by, label, cart_json, status)
            VALUES (:held_at, :held_by, :label, :cart_json, 'active')
            RETURNING id, held_at, held_by, label, cart_json, status
            """
        ),
        {
            "held_at": now,
            "held_by": held_by,
            "label": label_norm,
            "cart_json": cart_json,
        },
    )
    row = result.fetchone()
    session.commit()
    return _row_to_held(row)


def list_active_held(session: Session) -> list[HeldSaleRow]:
    """Return all active held sales ordered by held_at ASC."""
    result = session.execute(
        text(
            """
            SELECT id, held_at, held_by, label, cart_json, status
            FROM held_sale
            WHERE status = 'active'
            ORDER BY held_at ASC
            """
        )
    )
    return [_row_to_held(r) for r in result.fetchall()]


def get_held(session: Session, held_id: int) -> HeldSaleRow | None:
    """Fetch one held sale by id, or None if missing/discarded."""
    result = session.execute(
        text(
            """
            SELECT id, held_at, held_by, label, cart_json, status
            FROM held_sale
            WHERE id = :id
            """
        ),
        {"id": held_id},
    )
    row = result.fetchone()
    return _row_to_held(row) if row else None


def resume_held(session: Session, held_id: int) -> dict[str, Any]:
    """Mark a held sale as resumed and return its cart payload.

    The row is preserved with status='resumed' for audit; the caller
    is expected to use the returned cart to create a new sale. If the
    subsequent sale fails, the operator can re-list active held sales
    to find the original.

    Raises KeyError if the id is missing/discarded/already-resumed.
    """
    row = session.execute(
        text(
            """
            UPDATE held_sale
            SET status = 'resumed'
            WHERE id = :id AND status = 'active'
            RETURNING id, held_at, held_by, label, cart_json, status
            """
        ),
        {"id": held_id},
    ).fetchone()
    if row is None:
        raise KeyError(f"held_sale {held_id} not active (missing or already finalized)")
    session.commit()
    return _row_to_held(row).parse_cart()


def discard_held(session: Session, held_id: int) -> bool:
    """Discard a held sale (status=discarded). Returns True if changed."""
    result = session.execute(
        text(
            """
            UPDATE held_sale
            SET status = 'discarded'
            WHERE id = :id AND status = 'active'
            """
        ),
        {"id": held_id},
    )
    session.commit()
    return result.rowcount > 0
