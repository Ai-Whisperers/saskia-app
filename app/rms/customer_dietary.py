"""app/rms/customer_dietary.py — customer dietary profile helpers (P3).

A customer has:
- RESTRICTIONS: canonical dietary tags they must NEVER have violated
  (CSV of CANONICAL_DIETARY_TAGS). Any employee sees these as a red
  warning at order time.
- PREFERENCES: approved substitutes/choices with a preference order
  (JSON [{tag, rank, note}]). Rank 1 = offer first. E.g. a lactose-free
  customer may approve "leche de almendra" first, "leche de coco" second.
- CONFIRM_ALWAYS: if set, the employee must confirm the choice with the
  customer on EVERY order (the warning says "preguntar siempre").

Vocabulary comes from tagging.vocabulary (CANONICAL_DIETARY_TAGS +
normalize) so customer tags, recipe tags, and product tags all speak
the same language.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from app.rms.tagging.vocabulary import CANONICAL_DIETARY_TAGS


@dataclass
class DietaryPreference:
    """One approved choice in the customer's preference order."""

    tag: str  # canonical dietary tag OR free-text product choice
    rank: int = 1  # 1 = offer first
    note: str = ""  # "leche de almendra", "marca X", etc.


@dataclass
class DietaryProfile:
    """Parsed view of a customer's dietary columns."""

    restrictions: list[str] = field(default_factory=list)
    preferences: list[DietaryPreference] = field(default_factory=list)
    confirm_always: bool = False

    @property
    def has_alerts(self) -> bool:
        return bool(self.restrictions) or bool(self.preferences)


def parse_restrictions(raw: str | None) -> list[str]:
    """CSV -> list of canonical tags. Unknown tokens pass through (they
    may be newer vocabulary); display code shows them verbatim."""
    if not raw:
        return []
    seen: list[str] = []
    for tok in raw.split(","):
        t = tok.strip()
        if t and t not in seen:
            seen.append(t)
    return seen


def format_restrictions(tags: list[str]) -> str:
    return ",".join(tags)


def parse_preferences(raw: str | None) -> list[DietaryPreference]:
    """JSON list -> ordered preferences (sorted by rank, stable)."""
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return []
    if not isinstance(data, list):
        return []
    out: list[DietaryPreference] = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            continue
        tag = str(item.get("tag", "")).strip()
        if not tag:
            continue
        try:
            rank = int(item.get("rank", i + 1))
        except (TypeError, ValueError):
            rank = i + 1
        out.append(
            DietaryPreference(
                tag=tag,
                rank=rank,
                note=str(item.get("note", "")).strip(),
            )
        )
    out.sort(key=lambda p: p.rank)
    return out


def format_preferences(prefs: list[DietaryPreference]) -> str:
    return json.dumps(
        [{"tag": p.tag, "rank": p.rank, "note": p.note} for p in prefs],
        ensure_ascii=False,
    )


def load_profile(
    restrictions_raw: str | None,
    preferences_raw: str | None,
    confirm_always: bool | int | None,
) -> DietaryProfile:
    return DietaryProfile(
        restrictions=parse_restrictions(restrictions_raw),
        preferences=parse_preferences(preferences_raw),
        confirm_always=bool(confirm_always),
    )


def is_canonical_tag(tag: str) -> bool:
    return tag.strip().lower() in CANONICAL_DIETARY_TAGS
