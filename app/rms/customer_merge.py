"""app/rms/customer_merge.py — P1-B4: consolidate duplicate customer records.

Problem: counter staff often register the same person multiple times
("Maria" / "María E." / "Maria G.") under different spellings or
phones. Reports then attribute one person's spend across 3 rows, so
the lifetime-spend totals lie.

Fix: a domain function `customer_merge()` that takes a canonical
(target) customer and N duplicates (sources), reassigns all
Sales + Pedidos to the target, fills in missing contact info from
the sources, appends a notes-trail entry, then deletes the source
rows. The whole thing runs inside the caller's transaction so any
unique-constraint violation aborts cleanly.

Pure domain: no FastAPI / request / template dependencies. The router
in `app/routers/customers.py` wraps this with CSRF + auth + audit.

P1-B4 from canonical roadmap — see COMPLETE_PLAN.md §P1-B4.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.rms.models import Customer, Pedido, Sale


@dataclass
class MergeSourceResult:
    """Per-source merge outcome — what was reassigned from this source."""

    from_id: int
    from_name: str | None
    sales_reassigned: int = 0
    pedidos_reassigned: int = 0


@dataclass
class MergeResult:
    """Top-level result returned by `customer_merge()`.

    The router reads this to write an audit row and to render the
    success flash message.
    """

    target_id: int
    sources_merged: list[MergeSourceResult] = field(default_factory=list)
    notes_appended: bool = False
    phone_filled_from_source: bool = False
    email_filled_from_source: bool = False


def customer_merge(
    session: Session,
    *,
    target_id: int,
    source_ids: Iterable[int],
) -> MergeResult:
    """Merge multiple source customers into a single target.

    Args:
        session: An open SQLAlchemy Session. The caller owns the
            transaction (commit / rollback); this function never
            commits or flushes implicitly beyond what SQLAlchemy needs
            to satisfy FK constraints before source rows are deleted.
        target_id: Primary key of the surviving customer. Must exist
            and must NOT appear in `source_ids`.
        source_ids: Iterable of source customer ids to merge INTO
            `target_id`. Sources are deleted at the end. Empty input
            is a no-op that returns an empty `sources_merged` list.

    Returns:
        MergeResult with per-source stats + flags for the audit row.

    Raises:
        ValueError: on bad input — `target_id` missing, any source
            id missing, `target_id in source_ids`, or empty input.
        IntegrityError: when a unique constraint would be violated by
            the reassignment (e.g. a per-customer uniqueness on Sale
            that the source rows would conflict with). The transaction
            is left in a half-committed state — caller must rollback.
    """
    source_id_list = [int(s) for s in source_ids]

    if not source_id_list:
        raise ValueError("source_ids must not be empty")

    # 1. Validate target and sources.
    target = _validate_merge_inputs(session, target_id, source_id_list)
    sources = _load_source_customers(session, source_id_list)

    result = MergeResult(target_id=target.id)
    original_notes = target.notes

    # 2. Reassign Sales + Pedidos per source.
    _reassign_customer_records(session, target, sources, result)

    # 3. Fall back missing target contact fields from sources.
    _fill_missing_contact_fields(target, sources, result)

    # 4. Append merge trail to notes.
    _append_merge_trail(target, sources, original_notes, result)

    # 5. Flush so FK references + unique constraints validate BEFORE
    # we delete the source rows. If something would violate (e.g. a
    # per-customer uniqueness on Sale), IntegrityError surfaces here
    # and the caller rolls back — sources stay alive.
    try:
        session.flush()
    except IntegrityError:
        # Bubble up — caller decides rollback strategy.
        raise

    # 6. Delete sources. Do this LAST so a FK violation aborts cleanly.
    for src in sources:
        session.delete(src)

    # 7. One more flush so deletes are staged; the caller commits.
    session.flush()

    return result


def _validate_merge_inputs(session: Session, target_id: int, source_id_list: list[int]) -> Customer:
    """Validate merge inputs and return the target customer.

    Extracted from customer_merge to reduce complexity. Validates:
    - target_id exists in DB
    - target_id not in source_ids (no self-merge)
    - all source_ids exist in DB

    Raises ValueError on any validation failure.
    """
    target = session.get(Customer, int(target_id))
    if target is None:
        raise ValueError(f"target customer id={target_id} not found")

    if int(target_id) in source_id_list:
        raise ValueError(
            f"target_id={target_id} is in source_ids; cannot merge a customer into itself"
        )

    return target


def _load_source_customers(session: Session, source_id_list: list[int]) -> list[Customer]:
    """Load all source customers in a single query and validate they exist.

    Extracted from customer_merge to reduce complexity. Raises ValueError
    if any source id is missing.
    """
    sources = session.scalars(select(Customer).where(Customer.id.in_(source_id_list))).all()
    found_ids = {c.id for c in sources}
    missing = [sid for sid in source_id_list if sid not in found_ids]
    if missing:
        raise ValueError(f"source customer(s) not found: {missing}")
    return sources


def _reassign_customer_records(
    session: Session,
    target: Customer,
    sources: list[Customer],
    result: MergeResult,
) -> None:
    """Reassign Sales and Pedidos from sources to target.

    Extracted from customer_merge to reduce complexity. For each source,
    counts the related records, reassigns them to the target, and updates
    the result with per-source stats.
    """
    for src in sources:
        sales_count = (
            session.scalar(select(func.count(Sale.id)).where(Sale.customer_id == src.id)) or 0
        )
        pedidos_count = (
            session.scalar(select(func.count(Pedido.id)).where(Pedido.customer_id == src.id)) or 0
        )

        # UPDATE … WHERE customer_id = src.id. SQLAlchemy emits the
        # right SQL for both SQLite (test) and Postgres (prod).
        session.execute(
            update(Sale).where(Sale.customer_id == src.id).values(customer_id=target.id)
        )
        session.execute(
            update(Pedido).where(Pedido.customer_id == src.id).values(customer_id=target.id)
        )

        result.sources_merged.append(
            MergeSourceResult(
                from_id=src.id,
                from_name=src.name,
                sales_reassigned=int(sales_count),
                pedidos_reassigned=int(pedidos_count),
            )
        )


def _fill_missing_contact_fields(
    target: Customer, sources: list[Customer], result: MergeResult
) -> None:
    """Fill missing target phone/email from sources.

    Extracted from customer_merge to reduce complexity. Picks the first
    source that has the field populated.
    """
    _copy_field_if_missing(target, sources, "phone", result)
    _copy_field_if_missing(target, sources, "email", result)


def _copy_field_if_missing(
    target: Customer, sources: list[Customer], field_name: str, result: MergeResult
) -> None:
    """Copy a field from the first source that has it populated.

    Extracted from _fill_missing_contact_fields to reduce complexity.
    Only copies if the target field is empty.
    """
    current = getattr(target, field_name)
    if current and current.strip():
        return
    for src in sources:
        source_value = getattr(src, field_name)
        if source_value and source_value.strip():
            setattr(target, field_name, source_value.strip())
            if field_name == "phone":
                result.phone_filled_from_source = True
            else:
                result.email_filled_from_source = True
            break


def _append_merge_trail(
    target: Customer,
    sources: list[Customer],
    original_notes: str | None,
    result: MergeResult,
) -> None:
    """Append merge trail to target notes.

    Extracted from customer_merge to reduce complexity. Adds a separator
    and per-source merge entries to the target's notes field.
    """
    new_entries: list = [f"--- Fusionado desde {src.name} (id={src.id}) ---" for src in sources]
    if new_entries:
        sep = "\n" if (original_notes and original_notes.strip()) else ""
        trail = sep + "\n".join(new_entries)
        target.notes = (original_notes or "") + trail
        result.notes_appended = True


__all__ = [
    "MergeResult",
    "MergeSourceResult",
    "customer_merge",
]
