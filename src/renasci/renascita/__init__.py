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

from renasci import geo
from renasci.core.calendar import Age, Calendar, Date
from renasci.core.engine import Engine
from renasci.people.scenario import synthesise
from renasci.people.world import people_ruleset

CAL = Calendar(ages=(Age(4, "4A", "Fourth Age", last_year=256),))
SCENARIO: dict = geo.attach(json.loads((Path(__file__).parent / "fourth_age.json").read_text(encoding="utf-8")),
                             Path(__file__).parent)
START = Date.from_json(SCENARIO["start"])


# Population, not canon: the houses stay as they are, while the named commoners (and the notable target
# that keeps their number up) grow with the masses, so a scaled world has about `scale` times the notables.
SCALED = ("masses", "commoners", "capacity", "notable_target")


POLITIES: dict = json.loads((Path(__file__).parent / "fourth_age_polities.json").read_text(encoding="utf-8"))
CRAFTS: dict = json.loads((Path(__file__).parent / "crafts_draft.json").read_text(encoding="utf-8"))
FRONTIER: dict = json.loads((Path(__file__).parent / "frontier_clans.json").read_text(encoding="utf-8"))


def _scenario(scenario: dict | None, scale: int = 1, beliefs: bool | None = None, polities: bool | str | None = None,
              crafts: bool | None = None) -> dict:
    """The scenario (the draft unless given), with every settlement's population times `scale` (#75: M1
    scale is about ten times the draft), beliefs on or off when `beliefs` says (S12 §1a: a recipe's
    `[world] beliefs = true`), and the draft polities (the Empire, its Imperial House and council blocs:
    `fourth_age_polities.json`, S8 #120) when `polities` is true; `polities = "frontier"` adds the war-prone
    draft (the Frontier Clans of `frontier_clans.json`, S8 #160: their holds, houses and roads, an old
    bitterness with the Empire, and campaigns on unless the scenario's own params say otherwise)."""
    if type(scale) is not int or scale < 1:
        raise ValueError(f"scale must be a positive int, got {scale!r}")
    if beliefs is not None and type(beliefs) is not bool:
        raise ValueError(f"beliefs must be true or false, got {beliefs!r}")
    sc = geo.attach(copy.deepcopy(SCENARIO if scenario is None else scenario), Path(__file__).parent)
    if beliefs is not None:
        sc["params"] = {**sc.get("params", {}), "beliefs": beliefs}
    if polities is not None and type(polities) is not bool and polities != "frontier":
        raise ValueError(f"polities must be true, false or \"frontier\", got {polities!r}")
    if polities:
        extra = copy.deepcopy(POLITIES)
        sc["houses"] = [*sc["houses"], *extra["houses"]]
        for key in ("polities", "factions", "offices"):
            sc[key] = [*(sc.get(key) or []), *extra.get(key, [])]
        sc["params"] = {"cadet_size": 12, **sc.get("params", {})}  # (great houses branch: S8 §3.5, #161)
    if polities == "frontier":
        war = copy.deepcopy(FRONTIER)
        known = {pl["id"] for pl in (sc.get("geography") or {}).get("places", [])} if isinstance(sc.get("geography"), dict) else set()
        missing = sorted({e for r in war["routes"] for e in r["ends"] if not e.startswith("v:draft-")} - known)
        if missing:
            raise ValueError(f"the frontier draft joins Pyrosia's map at {missing}, which this scenario's geography lacks")
        sc["settlements"] = [*sc["settlements"], *war["settlements"]]
        regions = dict(sc.get("regions") or {})
        for s in war["settlements"]:
            regions[s["region"]] = [*regions.get(s["region"], []), s["id"]]
        sc["regions"] = regions
        g = sc["geography"]
        sc["geography"] = {**g, "places": [*g["places"], *war["places"]], "routes": [*g["routes"], *war["routes"]]}
        sc["houses"] = [*sc["houses"], *war["houses"]]
        sc["polities"] = [*sc["polities"], *war["polities"]]
        sc["relations"] = [*(sc.get("relations") or []), *war["relations"]]
        sc["params"] = {**war["params"], **sc["params"]}
    if crafts is not None and type(crafts) is not bool:
        raise ValueError(f"crafts must be true or false, got {crafts!r}")
    if crafts:  # (S9 #123: the draft trades)
        sc["params"] = {**sc.get("params", {}), "crafts": copy.deepcopy(CRAFTS)}
    for s in sc["settlements"]:
        for k in SCALED:
            if s.get(k) is not None:
                s[k] = s[k] * scale
    return sc


def start_of(scenario: dict) -> Date:
    return CAL.check(Date.from_json(scenario.get("start", START.to_json())))


def ruleset(scenario: dict | None = None):
    return _with_scripts(people_ruleset("fourth_age", _scenario(scenario)))


def rulesets(scenario: dict | None = None, scale: int = 1, beliefs: bool | None = None, polities: bool | str | None = None,
             crafts: bool | None = None):
    sc = _scenario(scenario, scale, beliefs, polities, crafts)
    return [(start_of(sc), _with_scripts(people_ruleset("fourth_age", sc)))]


def _with_scripts(rs):
    """The Fourth Age's scripted injections (the ward failure, #90) as disguises of its people ruleset."""
    from renasci.core.systems import Ruleset
    from renasci.renascita.ward import WardFailure

    return Ruleset(rs.name, rs.version, rs.systems, params=rs.params, forcers=rs.forcers,
                   disguises=(*rs.disguises, WardFailure()), conservation=rs.conservation)


def new_engine(seed: int = 1234, ripples=(), pins=(), scenario: dict | None = None, canon: dict | None = None,
               end=None, scale: int = 1, beliefs: bool | None = None, polities: bool | str | None = None,
               crafts: bool | None = None) -> Engine:
    """The Fourth Age at the scenario's start, synthesised from the (draft) scenario with any canon placed
    (`renasci.people.casting`), before anything runs."""
    sc = _scenario(scenario, scale, beliefs, polities, crafts)
    e = Engine(CAL, seed=seed, rulesets=rulesets(sc))
    synthesise(e, sc, seed, canon)
    e.apply_pins(pins, end=end)  # (pins past the run's `end` are out of scope)
    e.apply_ripples(ripples)
    return e


__all__ = ["CAL", "START", "SCENARIO", "new_engine", "ruleset", "rulesets", "start_of"]
