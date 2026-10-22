"""Renascita's Fourth Age, as a scenario for the people systems (S3, #73).

`fourth_age.json` is a **provisional draft** (regenerate it with `scripts/fourth_age_draft.py`). The
names, the houses' seats and the races of Lion's Rest and Magnus' Rest come from the vault; every
number is a placeholder and none of it is canon. S2's vault bridge (#58-#63) will supply the canon
parts (houses' members, the Emperors, settlements' sizes) and cast them into the synthesised world.

The calendar is the Fourth Age alone: 4A 1 (the Psychic Schism) to 4A 256 (the campaign present). A
scenario names its own start date within it.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from renasci.core.calendar import Age, Calendar, Date
from renasci.core.engine import Engine
from renasci.people.scenario import synthesise
from renasci.people.world import people_ruleset

CAL = Calendar(ages=(Age(4, "4A", "Fourth Age", last_year=256),))
SCENARIO: dict = json.loads((Path(__file__).parent / "fourth_age.json").read_text(encoding="utf-8"))
START = Date.from_json(SCENARIO["start"])


def _scenario(scenario: dict | None) -> dict:
    return copy.deepcopy(SCENARIO if scenario is None else scenario)


def start_of(scenario: dict) -> Date:
    return CAL.check(Date.from_json(scenario.get("start", START.to_json())))


def ruleset(scenario: dict | None = None):
    return people_ruleset("fourth_age", _scenario(scenario))


def rulesets(scenario: dict | None = None):
    sc = _scenario(scenario)
    return [(start_of(sc), people_ruleset("fourth_age", sc))]


def new_engine(seed: int = 1234, ripples=(), pins=(), scenario: dict | None = None) -> Engine:
    """The Fourth Age at the scenario's start, synthesised from the (draft) scenario, before anything runs."""
    sc = _scenario(scenario)
    e = Engine(CAL, seed=seed, rulesets=rulesets(sc))
    synthesise(e, sc, seed)
    e.apply_pins(pins)
    e.apply_ripples(ripples)
    return e


__all__ = ["CAL", "START", "SCENARIO", "new_engine", "ruleset", "rulesets", "start_of"]
