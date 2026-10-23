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
from renasci.core.ripples import Disguise
from renasci.core.systems import System
from renasci.people import houses, population, ties
from renasci.people.genome import Catalogue, inherit, keyed, phenotype
from renasci.people.races import Race, age_years, band, days_since, quarterly

BIRTH = EventType("people.birth", 1, roles={"mother": (1, 1), "father": (0, 1), "child": (1, 2)},
                  payload={"twin": "bool", "mutations": "int"})
DEATH = EventType("people.death", 1, roles={"deceased": (1, 1), "killer": (0, 1)}, payload={"age": "int", "cause": "str"})
NEAR_MISS = EventType("people.near_miss", 1, roles={"survivor": (1, 1)}, payload={"would_have": "str"})
EVENT_TYPES = (BIRTH, DEATH, NEAR_MISS)
from renasci.people.ambitions import RESOLVED as _RESOLVED  # noqa: E402  (die resolves ambitions)
from renasci.people import minds  # noqa: E402  (die and near misses strike wounds)

WORLD_PARAMS = ("races", "catalogue", "house_from")  # (families.py also reads kin_degree, residence, market_rate)


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


def world_params(races: list, catalogue: dict, house_from: str = "father", kin_degree: int = 2,
                 residence: str = "husband", market_rate: float = 0.35, aggregates: bool = False,
                 traits: dict | None = None, ambitions: list | None = None,
                 married_share: float = 0.7, demote_rate: float = 0.2, commoner_after: int = 6,
                 commoner_rate: float = 0.3, tie_rate: float = 0.08, scheme_rate: float = 0.5,
                 exposure_base: float = 0.15, wound_years: int = 10, needs: dict | None = None) -> dict:
    """Ruleset params for the people systems, checked now rather than at the first activation."""
    if type(kin_degree) is not int or kin_degree < 0:
        raise ValueError("kin_degree must be a non-negative int")
    if residence not in ("husband", "wife"):
        raise ValueError(f"residence is husband or wife, got {residence!r}")
    if type(market_rate) not in (int, float) or not 0 <= market_rate <= 1:
        raise ValueError(f"market_rate must be a probability, got {market_rate!r}")
    for name, p in (("married_share", married_share), ("demote_rate", demote_rate), ("commoner_rate", commoner_rate),
                    ("tie_rate", tie_rate), ("scheme_rate", scheme_rate), ("exposure_base", exposure_base)):
        if type(p) not in (int, float) or not 0 <= p <= 1:
            raise ValueError(f"{name} must be a probability, got {p!r}")
    if type(aggregates) is not bool:
        raise ValueError("aggregates must be true or false")
    if type(commoner_after) is not int or commoner_after < 0:
        raise ValueError("commoner_after must be a non-negative int")
    if type(wound_years) is not int or wound_years < 1:
        raise ValueError("wound_years must be a positive int")
    params = {"races": races, "catalogue": catalogue, "house_from": house_from, "kin_degree": kin_degree,
              "residence": residence, "market_rate": market_rate, "aggregates": aggregates,
              "married_share": married_share, "demote_rate": demote_rate, "commoner_after": commoner_after,
              "commoner_rate": commoner_rate, "tie_rate": tie_rate, "scheme_rate": scheme_rate,
              "exposure_base": exposure_base, "wound_years": wound_years}
    if traits is not None:  # {role: trait name}: wits, temper, charm (S7 §12)
        if not isinstance(traits, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in traits.items()):
            raise ValueError("traits maps roles to trait names")
        unknown = sorted(set(traits.values()) - set(catalogue.get("traits", {})))
        if unknown:
            raise ValueError(f"traits names {unknown}, which the catalogue doesn't have: {sorted(catalogue.get('traits', {}))}")
        params["traits"] = traits
    if ambitions is not None:
        params["ambitions"] = list(ambitions)
    if needs is not None:  # {wound kind: phrase} (world data, S7 §7)
        if not isinstance(needs, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in needs.items()):
            raise ValueError("needs maps wound kinds to phrases")
        params["needs"] = dict(needs)
    _parse(canonical({k: params[k] for k in WORLD_PARAMS}))
    return params


def grieving(ctx, person: str) -> list[str]:
    """A person's living close kin: spouse, parents, children (sorted)."""
    kin = {ctx.get(person, "spouse"), ctx.get(person, "mother"), ctx.get(person, "father"),
           *(ctx.get(person, "children") or [])}
    return sorted(k for k in kin if k and ctx.exists(k) and ctx.status(k) == "active")


def add_grievance(ctx, holder: str, against: str, event: str, kind: str) -> None:
    """`holder` holds `event` against `against` (attributed harm only: S7 §7)."""
    grievances = list(ctx.get(holder, "grievances") or [])
    grievances.append({"against": against, "event": event, "kind": kind, "since": ctx.today.to_json()})
    ctx.set(holder, "grievances", grievances)


def die(ctx, person: str, settlement: str, cause: str, *, killer: str | None = None, causes=()) -> bool:
    """A death and what it undoes: the record, the settlement's roster, the spouse's marriage.

    Someone guarded (a protect ripple, a pin) survives instead: a near miss, and terror (S7 §7).
    Returns whether they died."""
    if ctx.guarded(person):
        miss = ctx.emit("people.near_miss", {"survivor": (person,)}, purpose="near_miss", actor=person,
                        place=settlement, causes=causes, payload={"would_have": cause})
        minds.wound(ctx, person, "terror", miss.id)
        return False
    death = ctx.emit("people.death", {"deceased": (person,), "killer": (killer,) if killer else ()}, purpose="death",
                     actor=person, place=settlement, causes=causes,
                     payload={"age": age_years(ctx.calendar, ctx.get(person, "born"), ctx.today), "cause": cause})
    ctx.set_status(person, "dead")
    ctx.set(settlement, "residents", [p for p in ctx.get(settlement, "residents") if p != person])
    spouse = ctx.get(person, "spouse")
    if spouse:
        ctx.set(spouse, "spouse", None)
    houses.vacate(ctx, person)
    population.bump(ctx, settlement, died=1)  # explained by the death itself
    if killer:  # an attributed killing: the victim's close kin hold it against the killer (S7 §7)
        for kin in grieving(ctx, person):
            if kin != killer:  # (a son who kills his father in a duel holds nothing against himself)
                add_grievance(ctx, kin, killer, death.id, "killed")
                minds.wound(ctx, kin, "grief", death.id)
    ties.end_ties(ctx, person, "death")
    from renasci.people import ambitions

    ambitions.on_death(ctx, person, death.id)
    return True


def crowding(people: int, capacity) -> float:
    """Fertility's response to a settlement filling up: 1.5x when nearly empty, 1x at half its
    capacity, nothing when full. No capacity: no limit (1x)."""
    if capacity is None:
        return 1.0
    if capacity <= 0:
        return 0.0  # nowhere to raise a child
    return max(0.0, min(1.5, 2.0 * (1.0 - people / capacity)))


_crowding = crowding  # (the name tests used first)

# What `die` touches. Every system (or forcer) that calls `die` declares these, and handles the
# succession follow-ups `die` schedules through `houses.handle_succession`.
_AMBITION_READS = frozenset({"ambitions", "cooldowns", "owner", "class", "state", "scheme", "spouse", "favour",
                             "target", "house", "headship", "holder"})  # (and whatever any `satisfied` reads)
_AMBITION_WRITES = frozenset({"ambitions", "cooldowns", "state", "resolved", "scheme"})
DIE_EVENTS = (DEATH, NEAR_MISS, _RESOLVED) + houses.EVENT_TYPES + (ties.TIE_ENDED,)
DIE_READS = (frozenset({"born", "residents", "spouse", "status", "flow:*", "mother", "father", "children", "grievances",
                         "need"})
             | houses.READS | ties.READS | _AMBITION_READS)
DIE_WRITES = frozenset({"status", "residents", "spouse", "flow:*", "grievances", "wound", "need"}) | houses.WRITES | ties.WRITES | _AMBITION_WRITES


class Life(System):
    name, cadence = "people.life", "seasonal"
    reads = frozenset({"ids:settlement", "residents", "born", "sex", "race"}) | DIE_READS
    writes = DIE_WRITES
    event_types = DIE_EVENTS

    def handle(self, ctx, activation):
        houses.handle_succession(ctx, activation)

    def run(self, ctx):
        races, _, _ = world(ctx)
        for settlement in ctx.ids("settlement"):
            with ctx.scope(settlement):
                for person in ctx.get(settlement, "residents"):
                    race = races[ctx.get(person, "race")]
                    age = age_years(ctx.calendar, ctx.get(person, "born"), ctx.today)
                    q = quarterly(race.mortality[ctx.get(person, "sex")][band(age)])
                    stakes = 1.0 + len(ctx.get(person, "ambitions") or [])  # a life with plans in it (S7 §8)
                    if not ctx.chance(q, "death", owner=person, stakes=stakes, roles={"deceased": [person]}):
                        continue
                    die(ctx, person, settlement, "old age" if age >= 60 else "infancy" if age < 5 else "illness")


class Illness(Disguise):
    """doom, disguised: a sudden illness (the means a latch point suggests for a near miss)."""

    name, handles = "people.illness", "doom"
    reads = DIE_READS | frozenset({"place"})
    writes = DIE_WRITES
    event_types = DIE_EVENTS

    def apply(self, ctx, ripple):
        if not ctx.exists(ripple.target) or ctx.status(ripple.target) != "active":
            return False
        die(ctx, ripple.target, ctx.get(ripple.target, "place"), "a sudden illness")
        return True  # (a guarded target survives it: a near miss is still the doom's outcome)

    def handle(self, ctx, activation):
        houses.handle_succession(ctx, activation)


class Births(System):
    name, cadence = "people.births", "seasonal"
    priority = -1  # before deaths on the same day, so a mother who dies this season may still give birth
    reads = frozenset({"ids:settlement", "residents", "born", "sex", "race", "spouse", "last_birth", "genome",
                       "house", "status", "children", "capacity", "pop:*", "flow:*"})
    writes = frozenset({"new:person", "residents", "children", "last_birth", "flow:*"})
    event_types = (BIRTH,)

    def run(self, ctx):
        races, catalogue, house_from = world(ctx)
        for settlement in ctx.ids("settlement"):
            with ctx.scope(settlement):
                people = len(ctx.get(settlement, "residents"))
                if ctx.params.get("aggregates"):
                    people += population.masses(ctx, settlement)
                damp = crowding(people, ctx.get(settlement, "capacity"))
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
                    p = quarterly(race.fertility[band(age)]) * damp
                    if p and ctx.chance(p, "birth", owner=mother, stakes=0.5, roles={"mother": [mother]}):
                        self._birth(ctx, settlement, mother, father, race, catalogue, house_from)

    def _birth(self, ctx, settlement: str, mother: str, father: str, race: Race, catalogue: Catalogue,
               house_from: str) -> None:
        give_birth(ctx, settlement, mother, father, race, catalogue, house_from)


def give_birth(ctx, settlement: str, mother: str, father: str | None, race: Race, catalogue: Catalogue,
               house_from: str, sex: str | None = None) -> list[str]:
    """A birth to `mother` (and `father`, if known) in `settlement`: the child or twins, their genomes,
    and everything a birth updates. `sex` fixes the child's sex (a pinned heir); the draw is still made."""
    twins = ctx.chance(race.twins, "twins", owner=mother)
    birth = ctx.peek_event_id(mother, "birth")  # a mutated copy's origin is this birth
    children, mutated, names = [], [], []
    for _ in range(2 if twins else 1):
        drawn = "m" if ctx.chance(race.male, "sex", owner=mother) else "f"
        child_sex = sex or drawn
        pool = [n for n in race.names[child_sex] if n not in names] or list(race.names[child_sex])  # twins differ
        name = pool[ctx.rng("name", mother).choice_index([1.0] * len(pool))]
        names.append(name)
        seed = int(ctx.rng("meiosis", mother).integers(0, 2**62))  # one stream per child, sub-keyed per locus
        genome, mutations = inherit(catalogue, ctx.get(mother, "genome"),
                                    ctx.get(father, "genome") if father else None, keyed(seed), birth,
                                    unknown=None if father else _settlement_stock(ctx, settlement, catalogue))
        mutated.append(len(mutations))
        parent = mother if house_from == "mother" or father is None else father
        children.append(("person", {
            "name": name, "sex": child_sex, "born": ctx.today.to_json(), "race": race.id, "place": settlement,
            "house": ctx.get(parent, "house"), "mother": mother, "father": father, "children": [],
            "spouse": None, "genome": genome, "traits": phenotype(catalogue, genome, {}),
            "drives": {}, "ties": [], "last_birth": None, "offices": []}))
    event = ctx.emit("people.birth", {"mother": (mother,), "father": (father,) if father else ()}, purpose="birth",
                     actor=mother,
                     place=settlement, payload={"twin": twins, "mutations": sum(mutated)},
                     creates={"child": children})
    assert event.id == birth
    born = list(event.roles["child"])
    # Spouses always live in the same settlement (marriage moves one of them), so the father's
    # `children` is read and written inside this settlement's scope.
    for parent in (mother, father):
        if parent:
            ctx.set(parent, "children", ctx.get(parent, "children") + born)
    ctx.set(mother, "last_birth", ctx.today.to_json())
    ctx.set(settlement, "residents", sorted(ctx.get(settlement, "residents") + born))
    population.bump(ctx, settlement, born=len(born))
    return born


def _settlement_stock(ctx, settlement: str, catalogue: Catalogue):
    """An unknown father's copies come from the settlement's masses (or the catalogue's first group)."""
    if ctx.params.get("aggregates"):
        from renasci.people.population import allele_column

        freqs = {}
        for lo in catalogue.loci:
            counts = ctx.read_columns(settlement, [allele_column(lo.id, v) for v in lo.variants])
            total = sum(counts.values())
            if total:
                freqs[lo.id] = {v: counts[allele_column(lo.id, v)] / total for v in lo.variants}
        if len(freqs) == len(catalogue.loci):
            return freqs, f"f:{settlement}"
    group = sorted(catalogue.groups)[0]
    return catalogue.groups[group], f"f:{group}"
