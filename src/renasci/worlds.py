"""Worlds a recipe can name. A world knows its calendar, how to build a fresh engine, and how to
rebuild its rulesets for restoring a checkpoint."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from renasci.core.calendar import Calendar, Date
from renasci.core.engine import Engine


@dataclass(frozen=True)
class World:
    name: str
    calendar: Calendar
    new_engine: Callable[..., Engine]  # (seed, ripples, pins, **params) -> Engine, cast and ready
    rulesets: Callable[..., list[tuple[Date, object]]]  # (**params) -> [(start, Ruleset)]
    params: frozenset[str] = frozenset()  # the [world] keys a recipe may set

    def restore(self, checkpoint: dict, seed: int, ripples=(), pins=(), **params) -> Engine:
        return Engine.restore(checkpoint, self.calendar, self.rulesets(**params), seed=seed, ripples=ripples, pins=pins)


def _toy() -> World:
    from renasci import toy

    def rulesets(buggy=False, people_per_village=None):
        return [(toy.START, toy.ruleset(buggy))]

    return World("toy", toy.CAL, toy.new_engine, rulesets, frozenset({"people_per_village", "buggy"}))


def _kin() -> World:
    from renasci import kin

    def rulesets(people_per_settlement=None, races=None, catalogue=None):
        return [(kin.START, kin.ruleset(races, catalogue))]

    return World("kin", kin.CAL, kin.new_engine, rulesets, frozenset({"people_per_settlement", "races", "catalogue"}))


WORLDS: dict[str, Callable[[], World]] = {"toy": _toy, "kin": _kin}


def get_world(name: str) -> World:
    if name not in WORLDS:
        raise ValueError(f"unknown world {name!r}; known worlds: {sorted(WORLDS)}")
    return WORLDS[name]()
