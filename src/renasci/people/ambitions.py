"""Ambitions (S7 spec §3): what notables want, and how wanting ends.

An `Ambition` is a stateless class; a live ambition is a store record (kind `ambition`) naming it:
`owner`, `class`, `target`, `formed`, `state` (active, fulfilled, thwarted, abandoned, died_unfulfilled;
`status` is the store's own field), `resolved`, `scheme`, `born_of`. The owner lists their
active ambitions in `ambitions` and keeps `cooldowns` ({class: the year it may form again}).

`people.ambitions` (yearly, per settlement scope, after drives) for each adult resident:

1. **resolves** each active ambition: `satisfied` -> fulfilled; `moot` or no longer `eligible` ->
   abandoned (eligibility is deterministic, so no draw ever abandons an ambition by chance);
2. **forms** each class (in name order) that is eligible, past its cooldown and not already held, with
   a keyed chance of its `urge` (`owner=person`, `purpose=form:<class>`). The formation event is caused
   by what the ambition was born of (a drive, an event, a wound).

Death resolves every active ambition as `died_unfulfilled` (`on_death`, called by `life.die`).

**Traits by role:** classes read `wits`, `temper` and `charm` through the ruleset param `traits`
({role: trait name in the world's catalogue}); a role the world doesn't map reads 0.5 (§12).
"""

from __future__ import annotations

from dataclasses import dataclass

from renasci.core.events import Cause, EventType
from renasci.core.systems import System
from renasci.people.races import age_years

FORMED = EventType("people.ambition_formed", 1, roles={"owner": (1, 1), "ambition": (1, 1), "target": (0, 1)},
                   payload={"class": "str", "text": "str"})
RESOLVED = EventType("people.ambition_resolved", 1, roles={"owner": (1, 1), "ambition": (1, 1)},
                     payload={"status": "str"}, dead_roles=("owner",))
EVENT_TYPES = (FORMED, RESOLVED)
ADULT = 16


def trait(ctx, person: str, role: str) -> float:
    """A trait by its role (wits, temper, charm), through the world's mapping; 0.5 if unmapped."""
    name = (ctx.params.get("traits") or {}).get(role)
    if not name:
        return 0.5
    return float((ctx.get(person, "traits") or {}).get(name, 0.5))


@dataclass(frozen=True)
class Formation:
    target: str | None
    born_of: tuple[str, str]  # a cause: ("drive", "belonging"), ("event", id), ("wound", kind)


class Ambition:
    name = ""
    cooldown_years = 5
    reads: frozenset[str] = frozenset()

    def eligible(self, ctx, person) -> Formation | None:
        raise NotImplementedError

    def urge(self, ctx, person) -> float:
        return 0.3

    def subgoals(self, ctx, amb) -> list[frozenset[str]]:
        return []

    def satisfied(self, ctx, amb) -> bool:
        return False

    def moot(self, ctx, amb) -> bool:
        target = ctx.get(amb, "target")
        return target is not None and ctx.status(target) != "active"

    def text(self, ctx, owner, target) -> str:
        return self.name.lower()


class Marry(Ambition):
    name, cooldown_years = "Marry", 3
    reads = frozenset({"spouse", "drives", "race", "born"})

    def eligible(self, ctx, person):
        from renasci.people.life import world

        races, _, _ = world(ctx)
        lo, hi = races[ctx.get(person, "race")].marriage
        age = age_years(ctx.calendar, ctx.get(person, "born"), ctx.today)
        belonging = (ctx.get(person, "drives") or {}).get("belonging", 1.0)
        if ctx.get(person, "spouse") is None and lo <= age <= hi and belonging < 0.5:
            return Formation(None, ("drive", "belonging"))
        return None

    def urge(self, ctx, person):
        return 0.6

    def subgoals(self, ctx, amb):
        return [frozenset({"married"})]

    def satisfied(self, ctx, amb):
        return ctx.get(ctx.get(amb, "owner"), "spouse") is not None

    def text(self, ctx, owner, target):
        return "find a spouse"


class Standing(Ambition):
    name, cooldown_years = "Standing", 6
    reads = frozenset({"house", "drives", "favour", "name"})

    def eligible(self, ctx, person):
        if ctx.get(person, "house") is None:
            return None
        status = (ctx.get(person, "drives") or {}).get("status", 1.0)
        if status < 0.6:
            return Formation(None, ("drive", "status"))
        return None

    def urge(self, ctx, person):
        return 0.1 + 0.3 * trait(ctx, person, "charm")

    def subgoals(self, ctx, amb):
        return [frozenset({"favoured"})]

    def satisfied(self, ctx, amb):
        return float(ctx.get(ctx.get(amb, "owner"), "favour") or 0.0) >= 0.5

    def text(self, ctx, owner, target):
        house = ctx.get(owner, "house")
        return f"raise House {ctx.get(house, 'name') or house} high at court"


STARTER = (Marry(), Standing())


LIBRARY: dict[str, Ambition] = {a.name: a for a in STARTER}


def classes(ctx) -> dict[str, Ambition]:
    """The ambition classes this world uses (the ruleset param `ambitions`, or every known class)."""
    names = ctx.params.get("ambitions")
    if not names:
        return dict(sorted(LIBRARY.items()))
    unknown = sorted(set(names) - set(LIBRARY))
    if unknown:
        raise ValueError(f"unknown ambition classes {unknown}; known: {sorted(LIBRARY)}")
    return {n: LIBRARY[n] for n in sorted(names)}


def resolve(ctx, amb: str, status: str, causes=()) -> None:
    """End an ambition: the event, the record, the owner's list and the cooldown."""
    owner = ctx.get(amb, "owner")
    event = ctx.emit("people.ambition_resolved", {"owner": (owner,), "ambition": (amb,)},
                     purpose=f"resolve:{status}", actor=amb, payload={"status": status},
                     causes=(Cause("ambition", amb), *causes))
    ctx.set(amb, "state", status)
    ctx.set(amb, "resolved", [ctx.today.to_json(), event.id])
    ctx.set(amb, "scheme", None)
    ctx.set(owner, "ambitions", [a for a in ctx.get(owner, "ambitions") or [] if a != amb])
    cls = ctx.get(amb, "class")
    known = classes(ctx)
    cooldown = known[cls].cooldown_years if cls in known else 5
    ctx.set(owner, "cooldowns", {**(ctx.get(owner, "cooldowns") or {}), cls: ctx.today.year + cooldown})


def on_death(ctx, person: str, death_event: str) -> None:
    """Every active ambition of the dead ends, caused by the death: unfulfilled, unless the world had
    already met it before the yearly pass noticed (married, then died, the same day)."""
    known = classes(ctx)
    for amb in list(ctx.get(person, "ambitions") or []):
        cls = known.get(ctx.get(amb, "class"))
        won = cls is not None and cls.satisfied(ctx, amb)
        resolve(ctx, amb, "fulfilled" if won else "died_unfulfilled", causes=(Cause("event", death_event),))


READS = frozenset({"ambitions", "cooldowns", "owner", "class", "target", "status", "state", "scheme"})
WRITES = frozenset({"ambitions", "cooldowns", "state", "resolved", "scheme", "new:ambition"})


class Ambitions(System):
    name, cadence = "people.ambitions", "yearly"
    priority = 6  # after drives (5)
    reads = READS | frozenset({"ids:settlement", "residents", "born", "formed", "traits"}).union(
        *(a.reads for a in STARTER))
    writes = WRITES
    event_types = EVENT_TYPES

    def run(self, ctx):
        library = classes(ctx)
        for s in ctx.ids("settlement"):
            with ctx.scope(s):
                for p in ctx.get(s, "residents"):
                    if age_years(ctx.calendar, ctx.get(p, "born"), ctx.today) < ADULT:
                        continue
                    self._resolve(ctx, p, library)
                    self._form(ctx, p, library)

    @staticmethod
    def _resolve(ctx, person, library):
        for amb in list(ctx.get(person, "ambitions") or []):
            cls = library.get(ctx.get(amb, "class"))
            if cls is None:
                resolve(ctx, amb, "abandoned")  # its class is no longer part of this world
            elif cls.satisfied(ctx, amb):
                resolve(ctx, amb, "fulfilled")
            elif cls.moot(ctx, amb) or cls.eligible(ctx, person) is None:
                resolve(ctx, amb, "abandoned")

    @staticmethod
    def _form(ctx, person, library):
        held = {ctx.get(a, "class") for a in ctx.get(person, "ambitions") or []}
        cooldowns = ctx.get(person, "cooldowns") or {}
        for name, cls in library.items():
            if name in held or cooldowns.get(name, 0) > ctx.today.year:
                continue
            formation = cls.eligible(ctx, person)
            if formation is None or not ctx.chance(cls.urge(ctx, person), f"form:{name}", owner=person):
                continue
            fields = {"owner": person, "class": name, "target": formation.target, "formed": ctx.today.to_json(),
                      "state": "active", "resolved": None, "scheme": None, "born_of": list(formation.born_of)}
            event = ctx.emit("people.ambition_formed",
                             {"owner": (person,), "target": (formation.target,) if formation.target else ()},
                             purpose=f"form:{name}", actor=person,
                             payload={"class": name, "text": cls.text(ctx, person, formation.target)},
                             causes=(Cause(*formation.born_of),), creates={"ambition": [("ambition", fields)]})
            amb = event.roles["ambition"][0]
            ctx.set(person, "ambitions", sorted((ctx.get(person, "ambitions") or []) + [amb]))
