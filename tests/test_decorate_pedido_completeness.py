"""tests/test_decorate_pedido_completeness.py — Phase 14 (2026-10-01) regression.

Catches the class of bug Phase 13 hit: a new Pedido column (e.g.
`delivery_preference`) was added to the ORM but the `_decorate_pedido()`
helper didn't include it, so the detail template's ventana badge silently
rendered nothing.

The fix is twofold:
1. Lock the decorator to expose ALL non-derived Pedido columns.
2. Have the helper precompute `ventana_text` so every consumer
   (list, board, recibo, pedido_publico) renders identically.
"""
import inspect
from datetime import date, time
from sqlalchemy import inspect as sqla_inspect


def _make_pedido(session_factory):
    """Insert a minimal pedido via the ORM (default values fill NOT NULLs)
    and return its id."""
    import uuid as _uuid
    from app.rms.models import Pedido
    with session_factory() as s:
        p = Pedido(
            customer_name="Fase14 Cliente",
            promised_date=date.today(),
            promised_time="15:00",  # bound as string — sqlite3 stdlib rejects time()
            channel="whatsapp",
            payment_intent="efectivo",
            public_token=_uuid.uuid4().hex[:24],
            status="pending",
            delivery_preference="window",
            delivery_window_start="14:00",
            delivery_window_end="16:00",
            address_text="Av. España 1234",
            invoice_ruc="80012345-6",
            invoice_name="Fase 14 S.A.",
        )
        s.add(p)
        s.commit()
        s.refresh(p)
        return p.id


def test_decorate_pedido_exposes_all_orm_columns(session_factory):
    """The decorated dict must include EVERY column on the Pedido model.
    Catches drift between the ORM and the helper. Derived columns
    (window_start, ventana_text) are allowed to be aliases / precomputed
    — the test only requires the original column to be addressable."""
    from app.rms.models import Pedido
    from app.routers.pedidos import _decorate_pedido

    pedido_id = _make_pedido(session_factory)

    with session_factory() as s:
        p = s.get(Pedido, pedido_id)
        assert p is not None
        decorated = _decorate_pedido(p, s)

        # All ORM columns must be present in the decorator (their values
        # may be None — that's fine; what matters is the key exists so
        # the template doesn't silently render "" for a column it expects).
        orm_cols = {col.key for col in sqla_inspect(Pedido).mapper.columns}
        decorated_keys = set(decorated.keys())
        missing = orm_cols - decorated_keys
        assert not missing, (
            f"_decorate_pedido is missing these Pedido columns:\n"
            f"  {sorted(missing)}\n"
            f"This is the Phase-13 class of regression — the detail page "
            f"silently didn't render ventana_text because delivery_preference "
            f"wasn't in the dict. Fix by adding the column to the decorator "
            f"in app/routers/pedidos.py."
        )


def test_decorate_pedido_includes_ventana_text(session_factory):
    """`ventana_text` is the precomputed helper output. Every consumer
    (list, board, recibo, pedido_publico) reads it from the decorator."""
    from app.rms.models import Pedido
    from app.routers.pedidos import _decorate_pedido

    pedido_id = _make_pedido(session_factory)
    with session_factory() as s:
        p = s.get(Pedido, pedido_id)
        decorated = _decorate_pedido(p, s)
        assert "ventana_text" in decorated, (
            "ventana_text must be in the decorator — the list/board/"
            "recibo/pedido_publico templates all read it."
        )
        # With delivery_preference='window' + start/end, the helper
        # produces a 'Ventana preferida: ...' string with the disclaimer
        assert "Ventana preferida" in decorated["ventana_text"]
        assert "no es garantía" in decorated["ventana_text"].lower()


def test_decorate_pedido_includes_payment_method_alias():
    """Phase 14: the list view reads `payment_method` (not `payment_intent`).
    Adding `payment_method` as an alias means the template shows the
    human label without a snake_case mismatch."""
    from app.routers.pedidos import _decorate_pedido
    src = inspect.getsource(_decorate_pedido)
    assert "payment_method" in src, (
        "_decorate_pedido should expose `payment_method` as an alias of "
        "`payment_intent` so the list template can render the human label."
    )


def test_decorate_pedido_includes_phase13_fk_pointers():
    """Phase 13 FK pointers to the structured address + invoice profile
    are useful for cross-navigation (pedido → address edit page)."""
    from app.routers.pedidos import _decorate_pedido
    src = inspect.getsource(_decorate_pedido)
    for k in ("customer_address_id", "customer_invoice_profile_id"):
        assert k in src, f"_decorate_pedido should expose {k}"