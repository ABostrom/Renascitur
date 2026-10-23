"""Causal ids: an id is derived from what created it, never from a global counter.

The same cause in the same place gives the same id in another run, which is what makes runs
comparable entity by entity and event by event.
"""

from __future__ import annotations

from renasci.core.calendar import Date
from renasci.core.canon import digest

CAST_PREFIXES = ("v", "t", "s")  # v: vault canon, t: toy/test fixtures, s: synthesised by a scenario
# (g: ids are a geography's own places, regions and routes: cast at the start, never pinned)
CAST_STARTS = tuple(f"{p}:" for p in CAST_PREFIXES)  # what a cast id starts with


def _name(label: str, value) -> str:
    if not isinstance(value, str) or not value:
        raise TypeError(f"{label} must be a non-empty string, got {value!r}")
    return value


def _count(label: str, value) -> int:
    if type(value) is not int or value < 0:
        raise TypeError(f"{label} must be a non-negative int, got {value!r}")
    return value


def event_id(system: str, actor: str, purpose: str, date: Date, occurrence: int, activation: str = "") -> str:
    """`occurrence` is the n-th event for this (system, actor, purpose) within one activation.

    Counting per activation (and keying by it) means skipping one event never shifts the ids of
    the others: one person's fate can't renumber everyone else's.
    """
    for label, value in (("system", system), ("actor", actor), ("purpose", purpose)):
        _name(label, value)
    if not isinstance(date, Date):
        raise TypeError(f"date must be a Date, got {date!r}")
    _count("occurrence", occurrence)
    if not isinstance(activation, str):
        raise TypeError(f"activation must be a string, got {activation!r}")
    return "x" + digest(["event", system, actor, purpose, date, occurrence, activation])


def entity_id(creator_event: str, role: str, ordinal: int) -> str:
    """An entity created by an event, in a role ("child"), with an ordinal for twins etc."""
    if not _name("creator_event", creator_event).startswith("x"):
        raise ValueError(f"creator_event must be an event id, got {creator_event!r}")
    _name("role", role)
    _count("ordinal", ordinal)
    return "e" + digest(["entity", creator_event, role, ordinal])


def cast_id(prefix: str, name: str) -> str:
    """An entity placed by casting rather than born in the sim."""
    if prefix not in CAST_PREFIXES:
        raise ValueError(f"cast prefix must be one of {CAST_PREFIXES}, got {prefix!r}")
    if not name:
        raise ValueError("cast id needs a name")
    return f"{prefix}:{name}"
