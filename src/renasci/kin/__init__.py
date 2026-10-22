"""The kin world: a small, non-Renascita world for testing people and bloodlines (S3).

Three regions of four settlements each. Two races: `k:folk` (short-lived, fertile) and `k:elder`
(long-lived, slow to breed), in the region `t:Mere`. A five-locus genome catalogue. One house per
region, seated in its first settlement. Nothing here is lore.

It is just a scenario (`world.json`, the shape any world supplies) synthesised by
`people.scenario.synthesise`; the arguments below only override parts of it for tests.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from renasci.core.calendar import Age, Calendar, Date
from renasci.core.engine import Engine
from renasci.core.systems import Ruleset
from renasci.people.drives import Drives
from renasci.people.families import Marriage
from renasci.people.genome import Catalogue
from renasci.people.houses import Houses
from renasci.people.life import Births, Life, world_params
from renasci.people.population import Lod, Population, conservation
from renasci.people.scenario import synthesise
from renasci.people.ties import Ties

CAL = Calendar(ages=(Age(1, "1K", "Kin Age", last_year=1000),))
START = Date(1, 1, 0)
SCENARIO: dict = json.loads((Path(__file__).parent / "world.json").read_text(encoding="utf-8"))
REGIONS: dict[str, list[str]] = SCENARIO["regions"]
SETTLEMENTS = tuple(s for ss in REGIONS.values() for s in ss)
REGION_OF = {s: r for r, ss in REGIONS.items() for s in ss}
RACES: list[dict] = SCENARIO["races"]
CATALOGUE: dict = SCENARIO["catalogue"]


def scenario(people_per_settlement=None, races=None, catalogue=None, residence=None, masses=None, base=None) -> dict:
    """The kin scenario with test overrides applied."""
    sc = copy.deepcopy(base or SCENARIO)
    if races is not None:
        sc["races"] = races
    if catalogue is not None:
        sc["catalogue"] = catalogue
    if residence is not None:
        sc["params"]["residence"] = residence
    for s in sc["settlements"]:
        if people_per_settlement is not None:
            s["commoners"], s["notable_target"] = people_per_settlement, people_per_settlement
        if masses is not None:
            s["masses"] = masses
        s["capacity"] = 2 * (s["commoners"] + s["masses"])
    return sc


def ruleset(races=None, catalogue=None, residence=None, sc=None) -> Ruleset:
    sc = sc or scenario(races=races, catalogue=catalogue, residence=residence)
    params = world_params(sc["races"], sc["catalogue"], aggregates=True,
                          **{k: v for k, v in sc["params"].items() if k != "aggregates"})
    return Ruleset("kin", 1, (Population(), Births(), Life(), Marriage(), Houses(), Lod(), Ties(), Drives()),
                   params=params, conservation=conservation(Catalogue.from_json(sc["catalogue"])))


def new_engine(seed: int = 1234, ripples=(), pins=(), people_per_settlement: int | None = None, races=None,
               catalogue=None, residence: str | None = None, masses: int | None = None,
               scenario: dict | None = None) -> Engine:
    """A fresh kin world at 1K 1, before anything runs."""
    sc = globals()["scenario"](people_per_settlement, races, catalogue, residence, masses, base=scenario)
    e = Engine(CAL, seed=seed, rulesets=[(START, ruleset(sc=sc))])
    synthesise(e, sc, seed)
    e.apply_pins(pins)
    e.apply_ripples(ripples)
    return e


def run(seed: int = 1234, years: int = 40, **kw) -> Engine:
    e = new_engine(seed, **kw)
    e.run(until=Date(1, years, CAL.days_per_year - 1))
    return e


__all__ = ["CAL", "START", "REGIONS", "SETTLEMENTS", "RACES", "CATALOGUE", "SCENARIO", "new_engine", "ruleset",
           "scenario", "run"]
