"""The kin world: a small, non-Renascita world for testing people and bloodlines (S3).

Three regions of four settlements each. Two races: `k:folk` (short-lived, fertile) and `k:elder`
(long-lived, slow to breed), in the region `t:Mere`. A five-locus genome catalogue. Nothing here is
lore. Its data is `world.json`, the same shape a real world supplies; this module only casts it.

Until scenario synthesis (#73), the starting people are cast simply: each settlement gets
`people_per_settlement` people of spread ages, and neighbours in the list are married when both are
of marriageable age.
"""

from __future__ import annotations

import json
from pathlib import Path

from renasci.core.calendar import Age, Calendar, Date
from renasci.core.engine import Engine
from renasci.core.systems import Ruleset
from renasci.people.genome import Catalogue, founder, keyed
from renasci.people.families import Marriage
from renasci.people.life import Births, Life, world_params
from renasci.people.races import Race, age_years

CAL = Calendar(ages=(Age(1, "1K", "Kin Age", last_year=1000),))
START = Date(1, 1, 0)
WORLD = json.loads((Path(__file__).parent / "world.json").read_text(encoding="utf-8"))
REGIONS: dict[str, list[str]] = WORLD["regions"]
SETTLEMENTS = tuple(s for ss in REGIONS.values() for s in ss)
REGION_OF = {s: r for r, ss in REGIONS.items() for s in ss}
RACES: list[dict] = WORLD["races"]
CATALOGUE: dict = WORLD["catalogue"]


def ruleset(races=None, catalogue=None) -> Ruleset:
    return Ruleset("kin", 1, (Births(), Life(), Marriage()), params=world_params(races or RACES, catalogue or CATALOGUE))


def new_engine(seed: int = 1234, ripples=(), pins=(), people_per_settlement: int = 20, races=None,
               catalogue=None) -> Engine:
    """A fresh kin world at 1K 1, before anything runs."""
    e = Engine(CAL, seed=seed, rulesets=[(START, ruleset(races, catalogue))])
    cat = Catalogue.from_json(catalogue or CATALOGUE)
    table = {r["id"]: r for r in (races or RACES)}
    streams = keyed(seed)
    for si, s in enumerate(SETTLEMENTS):
        region = REGION_OF[s]
        race_id, group = WORLD["region_race"][region], WORLD["region_group"][region]
        race = Race.from_json(table[race_id])
        people = [f"{s}-{i:02d}" for i in range(people_per_settlement)]
        e.cast("settlement", s, {"region": region, "genome_group": group, "residents": sorted(people),
                                 "capacity": 2 * people_per_settlement})
        ages = [1 + (i * 7 + si * 3) % 50 for i in range(people_per_settlement)]
        born = [[1, 1 - ages[i], (i * 37) % CAL.days_per_year] for i in range(people_per_settlement)]
        for i, p in enumerate(people):
            sex = "f" if i % 2 else "m"
            spouse = None
            partner = i + 1 if i % 2 == 0 else i - 1
            if partner < people_per_settlement and all(race.marriage[0] <= age_years(CAL, born[k], START)
                                                       for k in (i, partner)):
                spouse = people[partner]
            genome = founder(cat, group, lambda name, p=p: streams(f"{p}:{name}"), f"f:{group}")
            e.cast("person", p, {
                "name": race.names[sex][i % len(race.names[sex])], "sex": sex,
                "born": born[i], "race": race_id, "place": s, "house": None,
                "mother": None, "father": None, "children": [], "spouse": spouse, "genome": genome,
                "traits": {}, "drives": {}, "ties": [], "last_birth": None})
    e.apply_pins(pins)
    e.apply_ripples(ripples)
    return e


def run(seed: int = 1234, years: int = 40, **kw) -> Engine:
    e = new_engine(seed, **kw)
    e.run(until=Date(1, years, CAL.days_per_year - 1))
    return e


__all__ = ["CAL", "START", "REGIONS", "SETTLEMENTS", "RACES", "CATALOGUE", "new_engine", "ruleset", "run"]
