"""Causal ids: an id is derived from what created it, never from a global counter.

The same cause in the same place gives the same id in another run, which is what makes runs
comparable entity by entity and event by event.
"""

from __future__ import annotations

from renasci.core.calendar import Date
from renasci.core.canon import digest

CAST_PREFIXES = ("v", "t")  # v: vault canon, t: toy/test fixtures


def event_id(system: str, actor: str, purpose: str, date: Date, occurrence: int) -> str:
    """`occurrence` is the n-th event for this (system, actor, purpose, date)."""
    return "x" + digest(["event", system, actor, purpose, date, occurrence])


def entity_id(creator_event: str, role: str, ordinal: int) -> str:
    """An entity created by an event, in a role ("child"), with an ordinal for twins etc."""
    return "e" + digest(["entity", creator_event, role, ordinal])


def cast_id(prefix: str, name: str) -> str:
    """An entity placed by casting rather than born in the sim."""
    if prefix not in CAST_PREFIXES:
        raise ValueError(f"cast prefix must be one of {CAST_PREFIXES}, got {prefix!r}")
    if not name:
        raise ValueError("cast id needs a name")
    return f"{prefix}:{name}"
