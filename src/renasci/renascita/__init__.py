"""Renascita's Fourth Age, as a scenario for the people systems (S3, #73).

`fourth_age.json` is a **provisional draft**: the names come from the vault (the 12 Great Houses,
Pyrosia's cities and provinces), but every number is a placeholder and none of it is canon. S2's
vault bridge (#58-#63) will supply the canon parts (houses' members, the Emperors, settlements'
sizes) and cast them into the synthesised world.

The calendar is the Fourth Age alone: 4A 1 (the Psychic Schism) to 4A 256 (the campaign present).
"""

from __future__ import annotations

import json
from pathlib import Path

from renasci.core.calendar import Age, Calendar, Date
from renasci.core.engine import Engine
from renasci.people.scenario import synthesise
from renasci.people.world import people_ruleset

CAL = Calendar(ages=(Age(4, "4A", "Fourth Age", last_year=256),))
START = Date(4, 1, 0)
SCENARIO: dict = json.loads((Path(__file__).parent / "fourth_age.json").read_text(encoding="utf-8"))


def ruleset(scenario: dict | None = None):
    return people_ruleset("fourth_age", scenario or SCENARIO)


def new_engine(seed: int = 1234, ripples=(), pins=(), scenario: dict | None = None) -> Engine:
    """The Fourth Age at 4A 1, synthesised from the (draft) scenario, before anything runs."""
    sc = scenario or SCENARIO
    e = Engine(CAL, seed=seed, rulesets=[(START, ruleset(sc))])
    synthesise(e, sc, seed)
    e.apply_pins(pins)
    e.apply_ripples(ripples)
    return e


__all__ = ["CAL", "START", "SCENARIO", "new_engine", "ruleset"]
