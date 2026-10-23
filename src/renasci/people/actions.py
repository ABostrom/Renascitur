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
   action) and `succeed` or `fail` -> "success" / "failure"; "foiled" when the attempt succeeded but the
   world wouldn't have it (a guarded target survives: a near miss follows).

Draws are owned by the scheme when there is one, else by the actor (S7 §1). Effects that follow an
attempt (a death, a marriage, a move) are caused by its `people.action` event.

**Favour** (a person's standing at court, -1..1) is what `Petition`, `CourtFavour` and `Shame` move:
`heard` is favour of at least `HEARD`, `favoured` at least `FAVOURED`. The status drive reads it.
"""

from __future__ import annotations

import math

from renasci.core.events import Cause, EventType
from renasci import geo
from renasci.people import beliefs, families, life, minds, population, travel
from renasci.people.ambitions import trait
from renasci.people.races import age_years

ACTION = EventType("people.action", 1, roles={"actor": (1, 1), "target": (0, 1), "accomplice": (0, 1)},
                   payload={"action": "str", "outcome": "str"})
HEARD, FAVOURED = 0.2, 0.5
SHAMED = -0.25  # in disgrace: below this (a lost duel or an exposed plot alone isn't enough)


def _favour(ctx, person: str, delta: float) -> None:
    ctx.set(person, "favour", round(min(1.0, max(-1.0, float(ctx.get(person, "favour") or 0.0) + delta)), 2))


def _adult(ctx, person: str) -> bool:
    return age_years(ctx.calendar, ctx.get(person, "born"), ctx.today) >= 16


def _knew(ctx, actor: str, scheme: str | None) -> tuple[str, ...]:
    """Who knows the truth of a secret act: the actor and the scheme's accomplices."""
    return (actor, *(ctx.get(scheme, "accomplices") or [] if scheme else []))


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
    present = False  # the actor must go where the target lives (S4 §6)

    def road(self, ctx, actor, target) -> int | None:
        """The days to the target's settlement for an action done in person: 0 when there's no need (or no
        geography), None when there's no way there."""
        if not self.present or target is None or not travel.has_routes(ctx):
            return 0
        here, there = ctx.get(actor, "place"), ctx.get(target, "place")
        if here == there:
            return 0
        found = geo.path(ctx, here, there)
        return None if found is None else found[0]

    def duration(self, ctx, actor, target) -> int:
        """How long a step of this action takes: its own time plus, in person, the road there."""
        return self.duration_days + (self.road(ctx, actor, target) or 0)

    def feasible(self, ctx, actor, target, scheme) -> bool:
        """Possible now, and (in person) there's a road to the target: what the planner and `perform` ask."""
        return self.possible(ctx, actor, target, scheme) and self.road(ctx, actor, target) is not None

    def possible(self, ctx, actor, target, scheme) -> bool:
        return _alive(ctx, actor) and (target is None or (_alive(ctx, target) and target != actor))

    def odds(self, ctx, actor, target, scheme) -> float:
        return 0.5

    def succeed(self, ctx, actor, target, scheme, event) -> bool | None:
        """Do what success does; return False if the world foiled it (a guarded target survived)."""

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

    def succeed(self, ctx, actor, target, scheme, event):  # heard, even if shamed before
        ctx.set(actor, "favour", round(max(float(ctx.get(actor, "favour") or 0.0) + 0.25, HEARD), 2))


class CourtFavour(Action):
    name, requires, achieves, duration_days = "CourtFavour", frozenset({"heard"}), "favoured", 180

    def possible(self, ctx, actor, target, scheme):
        return _alive(ctx, actor) and float(ctx.get(actor, "favour") or 0.0) >= HEARD

    def odds(self, ctx, actor, target, scheme):
        return 0.3 + 0.4 * trait(ctx, actor, "charm")

    def succeed(self, ctx, actor, target, scheme, event):  # favoured
        ctx.set(actor, "favour", round(max(float(ctx.get(actor, "favour") or 0.0) + 0.3, FAVOURED), 2))


class Court(Action):
    """Win a spouse outside the yearly market: someone free nearby, or a commoner from the masses."""

    name, achieves, duration_days = "Court", "married", 120

    def _free(self, ctx, actor):
        """Unmarried, unrelated people of age and the other sex at home."""
        races, _, _ = life.world(ctx)
        home, sex = ctx.get(actor, "place"), ctx.get(actor, "sex")
        lo, hi = races[ctx.get(actor, "race")].marriage
        kin = families.ancestors(ctx, actor, 2)
        return [p for p in ctx.get(home, "residents") if p != actor and ctx.get(p, "sex") != sex
                and ctx.get(p, "spouse") is None and not ctx.get(p, "journey") and lo <= age_years(ctx.calendar, ctx.get(p, "born"), ctx.today) <= hi
                and p not in kin and not (families.ancestors(ctx, p, 2) & kin) and actor not in families.ancestors(ctx, p, 2)]

    def _masses_can(self, ctx, actor) -> bool:
        if not ctx.params.get("aggregates"):
            return False
        races, _, _ = life.world(ctx)
        lo, hi = races[ctx.get(actor, "race")].marriage
        other = "f" if ctx.get(actor, "sex") == "m" else "m"
        cols = [population.band_column(other, b) for b in range(lo // 5, min(hi // 5, 19) + 1)]
        return any(int(v) > 0 for v in ctx.read_columns(ctx.get(actor, "place"), cols).values())

    def possible(self, ctx, actor, target, scheme):  # only when someone could be won: success means married
        return (_alive(ctx, actor) and ctx.get(actor, "spouse") is None and _adult(ctx, actor)
                and not ctx.get(actor, "journey") and (bool(self._free(ctx, actor)) or self._masses_can(ctx, actor)))

    def odds(self, ctx, actor, target, scheme):
        return 0.5 + 0.3 * trait(ctx, actor, "charm")

    def succeed(self, ctx, actor, target, scheme, event):
        races, _, _ = life.world(ctx)
        home, sex = ctx.get(actor, "place"), ctx.get(actor, "sex")
        lo, hi = races[ctx.get(actor, "race")].marriage
        free = self._free(ctx, actor)
        partner = ctx.choose("court", free, owner=scheme or actor) if free else None
        if partner is None:
            partner = population.promote_person(ctx, home, "spouse", sex="f" if sex == "m" else "m", ages=(lo, hi))
        man, woman = (actor, partner) if sex == "m" else (partner, actor)
        families.Marriage._wed(ctx, man, woman, ctx.params.get("residence", "husband"), commoner=partner not in free)


class Poison(Action):
    name, requires, achieves, secrecy, duration_days, stakes = "Poison", frozenset({"accomplice"}), "dead:{target}", 0.5, 120, 2.0
    present = True

    def odds(self, ctx, actor, target, scheme):
        return 0.35 + 0.3 * trait(ctx, actor, "wits")

    def cover(self, ctx, actor, target, scheme):
        return "a wasting illness"

    def succeed(self, ctx, actor, target, scheme, event):
        return life.die(ctx, target, ctx.get(target, "place"), self.cover(ctx, actor, target, scheme),
                        causes=(Cause("event", event),), cover=True, knew=_knew(ctx, actor, scheme))


class Assassinate(Action):
    name, requires, achieves, secrecy, duration_days, stakes = ("Assassinate", frozenset({"accomplice"}),
                                                                 "dead:{target}", 0.4, 90, 2.0)
    present = True

    def odds(self, ctx, actor, target, scheme):
        return 0.3 + 0.3 * trait(ctx, actor, "wits")

    def cover(self, ctx, actor, target, scheme):
        return "found dead"

    def succeed(self, ctx, actor, target, scheme, event):
        return life.die(ctx, target, ctx.get(target, "place"), self.cover(ctx, actor, target, scheme),
                        causes=(Cause("event", event),), cover=True, knew=_knew(ctx, actor, scheme))


class Duel(Action):
    """An open challenge. Winning kills the other, by a known hand; losing kills or shames the challenger."""

    name, achieves, duration_days, stakes = "Duel", "dead:{target}", 30, 2.0
    present = True

    def possible(self, ctx, actor, target, scheme):
        return super().possible(ctx, actor, target, scheme) and target is not None and _adult(ctx, actor) \
            and _adult(ctx, target)

    def odds(self, ctx, actor, target, scheme):
        edge = trait(ctx, actor, "temper") - trait(ctx, target, "temper")
        return 1.0 / (1.0 + math.exp(-3.0 * edge))

    def succeed(self, ctx, actor, target, scheme, event):
        return life.die(ctx, target, ctx.get(target, "place"), "fell in a duel", killer=actor,
                        causes=(Cause("event", event),))

    def fail(self, ctx, actor, target, scheme, event):
        if ctx.chance(0.5, "duel_loss", owner=scheme or actor):
            life.die(ctx, actor, ctx.get(actor, "place"), "fell in a duel", killer=target,
                     causes=(Cause("event", event),))
        else:
            _favour(ctx, actor, -0.2)


class Shame(Action):
    name, requires, achieves, duration_days = "Shame", frozenset({"heard"}), "shamed:{target}", 90

    def possible(self, ctx, actor, target, scheme):  # only the heard are listened to
        return super().possible(ctx, actor, target, scheme) and target is not None \
            and float(ctx.get(actor, "favour") or 0.0) >= HEARD

    def odds(self, ctx, actor, target, scheme):
        return 0.3 + 0.4 * trait(ctx, actor, "charm")

    def succeed(self, ctx, actor, target, scheme, event):
        _favour(ctx, target, -0.3)
        minds.wound(ctx, target, "shame", event)


class Flee(Action):
    """Leave home: by road to any settlement within `flee_days` (S4 §5), else, in a world without routes,
    at once to another settlement of the region. The step is the decision; the journey takes the road's days."""

    name, achieves, duration_days = "Flee", "safe", 30  # at once, in a world without routes
    deciding_days = 7  # with routes: the decision; the journey carries the road's days

    def duration(self, ctx, actor, target) -> int:
        return self.deciding_days if travel.has_routes(ctx) else self.duration_days

    def _elsewhere(self, ctx, actor):
        home = ctx.get(actor, "place")
        if travel.has_routes(ctx):
            return list(travel.destinations(ctx, home, int(ctx.params.get("flee_days", travel.FLEE_DAYS))))
        region = ctx.get(home, "region")
        return [s for s in ctx.ids("settlement") if s != home and ctx.get(s, "region") == region]

    def possible(self, ctx, actor, target, scheme):  # not the married, nor those who hold office (S4: families travel)
        return (_alive(ctx, actor) and ctx.get(actor, "spouse") is None and not ctx.get(actor, "offices")
                and not ctx.get(actor, "journey") and bool(self._elsewhere(ctx, actor)))

    def odds(self, ctx, actor, target, scheme):
        return 0.8

    def succeed(self, ctx, actor, target, scheme, event):
        home = ctx.get(actor, "place")
        if travel.has_routes(ctx):
            options = travel.destinations(ctx, home, int(ctx.params.get("flee_days", travel.FLEE_DAYS)))
            new = ctx.choose("flee", list(options), owner=scheme or actor, weights=[1.0 / d for d in options.values()])
            travel.depart(ctx, actor, new, "flee", causes=(Cause("event", event),) if event else ())
            return
        new = ctx.choose("flee", self._elsewhere(ctx, actor), owner=scheme or actor)
        ctx.set(home, "residents", [p for p in ctx.get(home, "residents") if p != actor])
        ctx.set(new, "residents", sorted(ctx.get(new, "residents") + [actor]))
        ctx.set(actor, "place", new)
        population.bump(ctx, home, out=1)
        population.bump(ctx, new, **{"in": 1})


class Confess(Action):
    name, achieves, duration_days = "Confess", "absolved", 30

    def possible(self, ctx, actor, target, scheme):
        return _alive(ctx, actor) and (scheme is None or ctx.exists(scheme))

    def odds(self, ctx, actor, target, scheme):
        return 0.9

    def succeed(self, ctx, actor, target, scheme, event):
        _favour(ctx, actor, -0.2)
        if scheme:
            ctx.set(scheme, "state", "confessed")


def library() -> dict[str, Action]:
    """Every Action subclass that names itself, by name: a new class joins by existing. A subclass that
    doesn't set its own `name` is a variant, not a new action. Two classes with one name are refused.
    Simulation code uses the frozen `ACTIONS`, so classes defined later (in tests) never leak into a run."""
    found: dict[str, type] = {}
    todo = list(Action.__subclasses__())
    while todo:
        cls = todo.pop()
        todo.extend(cls.__subclasses__())
        if "name" in vars(cls) and cls.name:
            if cls.name in found and found[cls.name] is not cls:
                raise ValueError(f"two actions are named {cls.name!r}")
            found[cls.name] = cls
    return {n: found[n]() for n in sorted(found)}


ACTIONS = library()

READS = (life.DIE_READS | families.Marriage.reads | population.COLUMN_READS | frozenset({
    "favour", "wound", "place", "residents", "region", "accomplices", "state", "born", "traits", "race", "sex",
    "spouse", "mother", "father", "ids:settlement", "offices", "plan", "step"}) | travel.READS)
WRITES = (life.DIE_WRITES | families.Marriage.writes | travel.WRITES
          | frozenset({"favour", "wound", "need", "accomplices", "state"}))
EVENT_TYPES = (ACTION,) + life.DIE_EVENTS + (families.MARRIAGE,) + population.LOD_TYPES + travel.EVENT_TYPES


def perform(ctx, action: Action, actor: str, target: str | None, scheme: str | None = None,
            odds: float | None = None) -> str:
    """One attempt at `action`: "impossible", "exposed", "success" or "failure" (see the module doc)."""
    if not action.feasible(ctx, actor, target, scheme):
        return "impossible"
    owner = scheme or actor
    roles = {"actor": (actor,), "target": (target,) if target else ()}
    if action.secrecy:
        p = min(1.0, action.secrecy * float(ctx.params.get("exposure_base", 0.15)) * (1.5 - trait(ctx, actor, "wits")))
        plan = ctx.get(scheme, "plan") if scheme else None
        stakes = 1.0 + (ctx.get(scheme, "step") / len(plan) if plan else 0.0)  # the further along, the more to lose
        if ctx.chance(p, f"expose:{action.name}", owner=owner, stakes=stakes, roles={"actor": [actor]}):
            ctx.emit("people.action", roles, purpose=f"exposed:{action.name}", actor=actor,
                     payload={"action": action.name, "outcome": "exposed"})
            return "exposed"
    p = action.odds(ctx, actor, target, scheme) if odds is None else odds
    won = ctx.chance(min(1.0, max(0.0, p)), f"act:{action.name}", owner=owner, stakes=action.stakes,
                     roles={"actor": [actor], **({"target": [target]} if target else {})})
    event = ctx.emit("people.action", roles, purpose=f"act:{action.name}", actor=actor,
                     payload={"action": action.name, "outcome": "success" if won else "failure"},
                     visibility="secret" if action.secrecy else None)
    if not won:
        action.fail(ctx, actor, target, scheme, event.id)
        return "failure"
    if action.succeed(ctx, actor, target, scheme, event.id) is False:
        return "foiled"  # the blow landed and the target lived (a near miss follows the action event)
    if beliefs.enabled(ctx) and action.secrecy and action.achieves.startswith("dead:") and target \
            and ctx.status(target) == "dead":  # (S6: those in a secret killing know who did it)
        beliefs.perceive(ctx, event.id, None, _knew(ctx, actor, scheme),
                         beliefs.claim("killed", victim=target, by=actor), secret=True)
    return "success"
