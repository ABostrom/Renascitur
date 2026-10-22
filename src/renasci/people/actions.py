"""Actions (S7 spec §4): the units of agency schemes are built from.

An `Action` is a stateless class: what it `requires` and `achieves` (planner tags; exactly one achieved
tag, with `{target}` substituted), how secret it is, how long it takes, whether it's `possible` now,
its `odds`, and what happens on success or failure. The library is every subclass with a name, so
**adding an action needs only a new class** (`library()`).

`perform(ctx, action, actor, target, scheme=None)` runs one attempt:

1. not `possible` -> "impossible" (nothing happens, no event);
2. a secret action first risks **exposure**: `ctx.chance(secrecy * exposure_base * (1.5 - wits))`. If
   exposed, a public `people.action` event says so and nothing else happens -> "exposed" (what exposure
   costs the schemer is the scheme's business, #94);
3. the **odds** draw (a hinge with the action's stakes) -> a `people.action` event (secret for a secret
   action) and `succeed` or `fail` -> "success" / "failure".

Draws are owned by the scheme when there is one, else by the actor (S7 §1). Effects that follow an
attempt (a death, a marriage, a move) are caused by its `people.action` event.

**Favour** (a person's standing at court, -1..1) is what `Petition`, `CourtFavour` and `Shame` move:
`heard` is favour of at least `HEARD`, `favoured` at least `FAVOURED`. The status drive reads it.
"""

from __future__ import annotations

import math

from renasci.core.events import Cause, EventType
from renasci.people import families, life, population
from renasci.people.ambitions import trait
from renasci.people.races import age_years

ACTION = EventType("people.action", 1, roles={"actor": (1, 1), "target": (0, 1), "accomplice": (0, 1)},
                   payload={"action": "str", "outcome": "str"})
HEARD, FAVOURED = 0.2, 0.5


def _favour(ctx, person: str, delta: float) -> None:
    ctx.set(person, "favour", round(min(1.0, max(-1.0, float(ctx.get(person, "favour") or 0.0) + delta)), 2))


def _adult(ctx, person: str) -> bool:
    return age_years(ctx.calendar, ctx.get(person, "born"), ctx.today) >= 16


def _alive(ctx, person) -> bool:
    return person is not None and ctx.exists(person) and ctx.status(person) == "active"


class Action:
    name = ""
    requires: frozenset[str] = frozenset()
    achieves = ""
    secrecy = 0.0
    duration_days = 90
    retries = 1
    weight = 1.0
    stakes = 1.0
    reads: frozenset[str] = frozenset()
    writes: frozenset[str] = frozenset()

    def possible(self, ctx, actor, target, scheme) -> bool:
        return _alive(ctx, actor) and (target is None or (_alive(ctx, target) and target != actor))

    def odds(self, ctx, actor, target, scheme) -> float:
        return 0.5

    def succeed(self, ctx, actor, target, scheme, event) -> None:
        pass

    def fail(self, ctx, actor, target, scheme, event) -> None:
        pass

    def cover(self, ctx, actor, target, scheme) -> str | None:
        return None


class Recruit(Action):
    """Win someone to the scheme: `target` is the would-be accomplice."""

    name, requires, achieves, secrecy, duration_days = "Recruit", frozenset({"tie:{target}"}), "accomplice", 0.2, 60

    def odds(self, ctx, actor, target, scheme):
        return 0.4 + 0.4 * trait(ctx, actor, "charm")

    def succeed(self, ctx, actor, target, scheme, event):
        if scheme:
            ctx.set(scheme, "accomplices", sorted(set(ctx.get(scheme, "accomplices") or []) | {target}))


class Petition(Action):
    name, achieves, duration_days = "Petition", "heard", 120

    def possible(self, ctx, actor, target, scheme):
        return _alive(ctx, actor) and float(ctx.get(actor, "favour") or 0.0) < FAVOURED

    def odds(self, ctx, actor, target, scheme):
        return 0.5 + 0.3 * trait(ctx, actor, "charm")

    def succeed(self, ctx, actor, target, scheme, event):
        _favour(ctx, actor, 0.25)


class CourtFavour(Action):
    name, requires, achieves, duration_days = "CourtFavour", frozenset({"heard"}), "favoured", 180

    def possible(self, ctx, actor, target, scheme):
        return _alive(ctx, actor) and float(ctx.get(actor, "favour") or 0.0) >= HEARD

    def odds(self, ctx, actor, target, scheme):
        return 0.3 + 0.4 * trait(ctx, actor, "charm")

    def succeed(self, ctx, actor, target, scheme, event):
        _favour(ctx, actor, 0.3)


class Court(Action):
    """Win a spouse outside the yearly market: someone free nearby, or a commoner from the masses."""

    name, achieves, duration_days = "Court", "married", 120

    def possible(self, ctx, actor, target, scheme):
        return _alive(ctx, actor) and ctx.get(actor, "spouse") is None and _adult(ctx, actor)

    def odds(self, ctx, actor, target, scheme):
        return 0.5 + 0.3 * trait(ctx, actor, "charm")

    def succeed(self, ctx, actor, target, scheme, event):
        races, _, _ = life.world(ctx)
        home, sex = ctx.get(actor, "place"), ctx.get(actor, "sex")
        lo, hi = races[ctx.get(actor, "race")].marriage
        kin = families.ancestors(ctx, actor, 2)
        free = [p for p in ctx.get(home, "residents") if p != actor and ctx.get(p, "sex") != sex
                and ctx.get(p, "spouse") is None and lo <= age_years(ctx.calendar, ctx.get(p, "born"), ctx.today) <= hi
                and p not in kin and not (families.ancestors(ctx, p, 2) & kin) and actor not in families.ancestors(ctx, p, 2)]
        partner = ctx.choose("court", free, owner=scheme or actor) if free else None
        if partner is None and ctx.params.get("aggregates"):
            partner = population.promote_person(ctx, home, "spouse", sex="f" if sex == "m" else "m", ages=(lo, hi))
        if partner is None:
            return
        man, woman = (actor, partner) if sex == "m" else (partner, actor)
        families.Marriage._wed(ctx, man, woman, ctx.params.get("residence", "husband"), commoner=partner not in free)


class Poison(Action):
    name, requires, achieves, secrecy, duration_days, stakes = "Poison", frozenset({"accomplice"}), "dead:{target}", 0.5, 120, 2.0

    def odds(self, ctx, actor, target, scheme):
        return 0.35 + 0.3 * trait(ctx, actor, "wits")

    def cover(self, ctx, actor, target, scheme):
        return "a wasting illness"

    def succeed(self, ctx, actor, target, scheme, event):
        life.die(ctx, target, ctx.get(target, "place"), self.cover(ctx, actor, target, scheme),
                 causes=(Cause("event", event),))


class Assassinate(Action):
    name, requires, achieves, secrecy, duration_days, stakes = ("Assassinate", frozenset({"accomplice"}),
                                                                 "dead:{target}", 0.4, 90, 2.0)

    def odds(self, ctx, actor, target, scheme):
        return 0.3 + 0.3 * trait(ctx, actor, "wits")

    def cover(self, ctx, actor, target, scheme):
        return "found dead"

    def succeed(self, ctx, actor, target, scheme, event):
        life.die(ctx, target, ctx.get(target, "place"), self.cover(ctx, actor, target, scheme),
                 causes=(Cause("event", event),))


class Duel(Action):
    """An open challenge. Winning kills the other, by a known hand; losing kills or shames the challenger."""

    name, achieves, duration_days, stakes = "Duel", "dead:{target}", 30, 2.0

    def possible(self, ctx, actor, target, scheme):
        return super().possible(ctx, actor, target, scheme) and target is not None and _adult(ctx, actor) \
            and _adult(ctx, target)

    def odds(self, ctx, actor, target, scheme):
        edge = trait(ctx, actor, "temper") - trait(ctx, target, "temper")
        return 1.0 / (1.0 + math.exp(-3.0 * edge))

    def succeed(self, ctx, actor, target, scheme, event):
        life.die(ctx, target, ctx.get(target, "place"), "fell in a duel", killer=actor, causes=(Cause("event", event),))

    def fail(self, ctx, actor, target, scheme, event):
        if ctx.chance(0.5, "duel_loss", owner=scheme or actor):
            life.die(ctx, actor, ctx.get(actor, "place"), "fell in a duel", killer=target,
                     causes=(Cause("event", event),))
        else:
            _favour(ctx, actor, -0.2)


class Shame(Action):
    name, requires, achieves, duration_days = "Shame", frozenset({"heard"}), "shamed:{target}", 90

    def odds(self, ctx, actor, target, scheme):
        return 0.3 + 0.4 * trait(ctx, actor, "charm")

    def succeed(self, ctx, actor, target, scheme, event):
        _favour(ctx, target, -0.3)
        ctx.set(target, "wound", {"kind": "shame", "event": event, "since": ctx.today.to_json()})


class Flee(Action):
    """Leave home for another settlement of the region (S4 brings real journeys)."""

    name, achieves, duration_days = "Flee", "safe", 30

    def _elsewhere(self, ctx, actor):
        home = ctx.get(actor, "place")
        region = ctx.get(home, "region")
        return [s for s in ctx.ids("settlement") if s != home and ctx.get(s, "region") == region]

    def possible(self, ctx, actor, target, scheme):
        return _alive(ctx, actor) and bool(self._elsewhere(ctx, actor))

    def odds(self, ctx, actor, target, scheme):
        return 0.8

    def succeed(self, ctx, actor, target, scheme, event):
        home = ctx.get(actor, "place")
        new = ctx.choose("flee", self._elsewhere(ctx, actor), owner=scheme or actor)
        ctx.set(home, "residents", [p for p in ctx.get(home, "residents") if p != actor])
        ctx.set(new, "residents", sorted(ctx.get(new, "residents") + [actor]))
        ctx.set(actor, "place", new)
        population.bump(ctx, home, out=1)
        population.bump(ctx, new, **{"in": 1})


class Confess(Action):
    name, achieves, duration_days = "Confess", "absolved", 30

    def odds(self, ctx, actor, target, scheme):
        return 0.9

    def succeed(self, ctx, actor, target, scheme, event):
        _favour(ctx, actor, -0.2)
        if scheme:
            ctx.set(scheme, "state", "confessed")


def library() -> dict[str, Action]:
    """Every named Action subclass, by name (a new class joins by existing)."""
    found, todo = {}, list(Action.__subclasses__())
    while todo:
        cls = todo.pop()
        todo.extend(cls.__subclasses__())
        if cls.name:
            found[cls.name] = cls()
    return dict(sorted(found.items()))


ACTIONS = library()

READS = (life.DIE_READS | families.Marriage.reads | population.COLUMN_READS | frozenset({
    "favour", "wound", "place", "residents", "region", "accomplices", "state", "born", "traits", "race", "sex",
    "spouse", "mother", "father", "ids:settlement"}))
WRITES = (life.DIE_WRITES | families.Marriage.writes | frozenset({"favour", "wound", "accomplices", "state"}))
EVENT_TYPES = (ACTION,) + life.DIE_EVENTS + (families.MARRIAGE,) + population.LOD_TYPES


def perform(ctx, action: Action, actor: str, target: str | None, scheme: str | None = None,
            odds: float | None = None) -> str:
    """One attempt at `action`: "impossible", "exposed", "success" or "failure" (see the module doc)."""
    if not action.possible(ctx, actor, target, scheme):
        return "impossible"
    owner = scheme or actor
    roles = {"actor": (actor,), "target": (target,) if target else ()}
    if action.secrecy:
        p = min(1.0, action.secrecy * float(ctx.params.get("exposure_base", 0.15)) * (1.5 - trait(ctx, actor, "wits")))
        if ctx.chance(p, f"expose:{action.name}", owner=owner, stakes=1.0, roles={"actor": [actor]}):
            ctx.emit("people.action", roles, purpose=f"exposed:{action.name}", actor=actor,
                     payload={"action": action.name, "outcome": "exposed"})
            return "exposed"
    p = action.odds(ctx, actor, target, scheme) if odds is None else odds
    won = ctx.chance(min(1.0, max(0.0, p)), f"act:{action.name}", owner=owner, stakes=action.stakes,
                     roles={"actor": [actor], **({"target": [target]} if target else {})})
    event = ctx.emit("people.action", roles, purpose=f"act:{action.name}", actor=actor,
                     payload={"action": action.name, "outcome": "success" if won else "failure"},
                     visibility="secret" if action.secrecy else None)
    (action.succeed if won else action.fail)(ctx, actor, target, scheme, event.id)
    return "success" if won else "failure"
