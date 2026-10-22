"""Life cycle (S3 spec §4.1-4.2): people are born, and die.

Both systems walk settlements, each in `ctx.scope(settlement)`, over its `residents`. Nothing lists
every person in the world: one birth anywhere would then touch every decision everywhere.

- `people.births` (seasonal, before deaths): a married woman of fertile age, past her birth
  spacing, may have a child (or twins). The child's genome comes from both parents (one keyed
  meiosis stream per birth, sub-keyed per locus), its traits from the genome. A copy that mutated
  is given the birth event as its origin.
- `people.life` (seasonal): each resident may die, by the race's hazard for their sex and age band.
  A person canon needs (a pin) or a ripple protects survives as a near miss instead.

World data arrives as ruleset params (JSON): `races` (a list of `people.races.Race` tables),
`catalogue` (a `people.genome.Catalogue`) and `house_from` ("father" or "mother"). Systems keep no
state; `world(ctx)` parses the params once per distinct value and caches the result.
"""

from __future__ import annotations

import functools
import json

from renasci.core.canon import canonical
from renasci.core.events import EventType
from renasci.core.systems import System
from renasci.people.genome import Catalogue, inherit, keyed, phenotype
from renasci.people.races import Race, age_years, band, days_since, quarterly

BIRTH = EventType("people.birth", 1, roles={"mother": (1, 1), "father": (0, 1), "child": (1, 2)},
                  payload={"twin": "bool", "mutations": "int"})
DEATH = EventType("people.death", 1, roles={"deceased": (1, 1)}, payload={"age": "int", "cause": "str"})
NEAR_MISS = EventType("people.near_miss", 1, roles={"survivor": (1, 1)}, payload={"would_have": "str"})
EVENT_TYPES = (BIRTH, DEATH, NEAR_MISS)

WORLD_PARAMS = ("races", "catalogue", "house_from")


@functools.lru_cache(maxsize=8)
def _parse(text: str):
    data = json.loads(text)
    races = {r.id: r for r in (Race.from_json(x) for x in data["races"])}
    house_from = data.get("house_from", "father")
    if house_from not in ("father", "mother"):
        raise ValueError(f"house_from is father or mother, got {house_from!r}")
    return races, Catalogue.from_json(data["catalogue"]), house_from


def world(ctx) -> tuple[dict[str, Race], Catalogue, str]:
    """The world's races, genome catalogue and house rule, from the ruleset params (parsed once)."""
    return _parse(canonical({k: ctx.params[k] for k in WORLD_PARAMS if k in ctx.params}))


def world_params(races: list, catalogue: dict, house_from: str = "father") -> dict:
    """Ruleset params for these systems, checked now rather than at the first activation."""
    params = {"races": races, "catalogue": catalogue, "house_from": house_from}
    _parse(canonical(params))
    return params


def die(ctx, person: str, settlement: str, cause: str) -> None:
    """A death and what it undoes: the record, the settlement's roster, the spouse's marriage."""
    ctx.emit("people.death", {"deceased": (person,)}, purpose="death", actor=person, place=settlement,
             payload={"age": age_years(ctx.calendar, ctx.get(person, "born"), ctx.today), "cause": cause})
    ctx.set_status(person, "dead")
    ctx.set(settlement, "residents", [p for p in ctx.get(settlement, "residents") if p != person])
    spouse = ctx.get(person, "spouse")
    if spouse:
        ctx.set(spouse, "spouse", None)


class Life(System):
    name, cadence = "people.life", "seasonal"
    reads = frozenset({"ids:settlement", "residents", "born", "sex", "race", "spouse", "status"})
    writes = frozenset({"status", "residents", "spouse"})
    event_types = (DEATH, NEAR_MISS)

    def run(self, ctx):
        races, _, _ = world(ctx)
        for settlement in ctx.ids("settlement"):
            with ctx.scope(settlement):
                for person in ctx.get(settlement, "residents"):
                    race = races[ctx.get(person, "race")]
                    age = age_years(ctx.calendar, ctx.get(person, "born"), ctx.today)
                    q = quarterly(race.mortality[ctx.get(person, "sex")][band(age)])
                    if not ctx.chance(q, "death", owner=person, stakes=1.0, roles={"deceased": [person]}):
                        continue
                    cause = "old age" if age >= 60 else "infancy" if age < 5 else "illness"
                    if ctx.guarded(person):
                        ctx.emit("people.near_miss", {"survivor": (person,)}, purpose="near_miss", actor=person,
                                 place=settlement, payload={"would_have": cause})
                    else:
                        die(ctx, person, settlement, cause)


class Births(System):
    name, cadence = "people.births", "seasonal"
    priority = -1  # before deaths on the same day, so a mother who dies this season may still give birth
    reads = frozenset({"ids:settlement", "residents", "born", "sex", "race", "spouse", "last_birth", "genome",
                       "house", "status", "children"})
    writes = frozenset({"new:person", "residents", "children", "last_birth"})
    event_types = (BIRTH,)

    def run(self, ctx):
        races, catalogue, house_from = world(ctx)
        for settlement in ctx.ids("settlement"):
            with ctx.scope(settlement):
                for mother in ctx.get(settlement, "residents"):
                    father = ctx.get(mother, "spouse")
                    if ctx.get(mother, "sex") != "f" or father is None:
                        continue
                    race = races[ctx.get(mother, "race")]
                    age = age_years(ctx.calendar, ctx.get(mother, "born"), ctx.today)
                    if not race.fertile[0] <= age <= race.fertile[1]:
                        continue
                    last = ctx.get(mother, "last_birth")
                    if last is not None and days_since(ctx.calendar, last, ctx.today) < race.spacing_days:
                        continue
                    p = quarterly(race.fertility[band(age)])
                    if p and ctx.chance(p, "birth", owner=mother, stakes=0.5, roles={"mother": [mother]}):
                        self._birth(ctx, settlement, mother, father, race, catalogue, house_from)

    def _birth(self, ctx, settlement: str, mother: str, father: str, race: Race, catalogue: Catalogue,
               house_from: str) -> None:
        twins = ctx.chance(race.twins, "twins", owner=mother)
        birth = ctx.peek_event_id(mother, "birth")  # a mutated copy's origin is this birth
        children, mutated, names = [], [], []
        for _ in range(2 if twins else 1):
            sex = "m" if ctx.chance(race.male, "sex", owner=mother) else "f"
            pool = [n for n in race.names[sex] if n not in names] or list(race.names[sex])  # twins differ
            name = pool[ctx.rng("name", mother).choice_index([1.0] * len(pool))]
            names.append(name)
            seed = int(ctx.rng("meiosis", mother).integers(0, 2**62))  # one stream per child, sub-keyed per locus
            genome, mutations = inherit(catalogue, ctx.get(mother, "genome"), ctx.get(father, "genome"),
                                        keyed(seed), birth)
            mutated.append(len(mutations))
            parent = mother if house_from == "mother" else father
            children.append(("person", {
                "name": name, "sex": sex, "born": ctx.today.to_json(), "race": race.id, "place": settlement,
                "house": ctx.get(parent, "house"), "mother": mother, "father": father, "children": [],
                "spouse": None, "genome": genome, "traits": phenotype(catalogue, genome, {}),
                "drives": {}, "ties": [], "last_birth": None}))
        event = ctx.emit("people.birth", {"mother": (mother,), "father": (father,)}, purpose="birth", actor=mother,
                         place=settlement, payload={"twin": twins, "mutations": sum(mutated)},
                         creates={"child": children})
        assert event.id == birth
        born = list(event.roles["child"])
        # Spouses always live in the same settlement (marriage moves one of them), so the father's
        # `children` is read and written inside this settlement's scope.
        for parent in (mother, father):
            ctx.set(parent, "children", ctx.get(parent, "children") + born)
        ctx.set(mother, "last_birth", ctx.today.to_json())
        ctx.set(settlement, "residents", sorted(ctx.get(settlement, "residents") + born))
