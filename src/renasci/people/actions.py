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
from renasci.people import beliefs, courts, families, houses, life, minds, population, travel
from renasci import lines, relations, war
from renasci.people.ambitions import governed, ruled, throne, trait
from renasci.people.races import age_years

ACTION = EventType("people.action", 1, roles={"actor": (1, 1), "target": (0, 1), "accomplice": (0, 1)},
                   payload={"action": "str", "outcome": "str"})
SEIZED = EventType("polity.seized", 1, roles={"usurper": (1, 1), "deposed": (1, 1)},
                   payload={"office": "id", "polity": "id"})
COUP_FOILED = EventType("polity.coup_foiled", 1, roles={"usurper": (1, 1), "ruler": (1, 1)},
                        payload={"office": "id"})
RAID = EventType("polity.raid", 1, roles={"raider": (1, 1), "party": (2, 2)}, payload={"relation": "id", "route": "id"})
SECEDED = EventType("polity.seceded", 1, roles={"leader": (1, 1), "from": (1, 1)},
                    payload={"polity": "str", "seat": "id"})
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
        found = geo.path(ctx, here, there, actor)
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


def _killings(ctx, actor: str, firm: float = 0.0) -> list[tuple[str, str, float]]:
    """The killings `actor` believes in (victim, killer, confidence), the victim dead, openly held."""
    out = []
    for b in (ctx.get(actor, "beliefs") or {}).values():
        c = b["claim"]
        if c["pred"] == "killed" and not b.get("secret") and b["conf"] >= firm and ctx.exists(c["args"]["victim"]) \
                and ctx.status(c["args"]["victim"]) == "dead":
            out.append((c["args"]["victim"], c["args"]["by"], b["conf"]))
    return sorted(out)


def _townsfolk(ctx, actor: str, exclude=()) -> list[str]:
    """Those living where the actor does, at home: who hears what's said there."""
    home = ctx.get(actor, "place")
    skip = {actor, *exclude}
    return sorted(r for r in ctx.get(home, "residents")
                  if r not in skip and ctx.status(r) == "active" and not ctx.get(r, "journey"))


class Slander(Action):
    """A lie told to the town: the target killed someone (a death the actor knows of, pinned on them).
    Riskier and costlier to plan than shaming at court (a fallback for those not heard there)."""

    name, achieves, secrecy, duration_days = "Slander", "shamed:{target}", 0.6, 60
    hearers, trust = 3, 0.5

    def _lie(self, ctx, actor, target):
        victims = [v for v, by, _ in _killings(ctx, actor) if by != target and v != target]
        return beliefs.claim("killed", victim=victims[0], by=target) if victims else None

    def possible(self, ctx, actor, target, scheme):
        return (beliefs.enabled(ctx) and super().possible(ctx, actor, target, scheme) and target is not None
                and self._lie(ctx, actor, target) is not None)

    def odds(self, ctx, actor, target, scheme):
        return 0.3 + 0.3 * trait(ctx, actor, "charm")

    def succeed(self, ctx, actor, target, scheme, event):
        lie = self._lie(ctx, actor, target)
        town = _townsfolk(ctx, actor, exclude=(target,))
        told = []
        for i in range(min(self.hearers, len(town))):
            h = ctx.choose(f"slander:{i}", [r for r in town if r not in told], owner=scheme or actor)
            told.append(h)
            beliefs.tell(ctx, actor, h, lie, self.trust, conf=0.8, intent="lie", cause=event,
                         place=ctx.get(actor, "place"))
        if told:  # (a lie nobody heard shames nobody)
            _favour(ctx, target, -0.3)


class Frame(Action):
    """Planted evidence: the victim's kin come to believe, firmly, that the target killed their own."""

    name, requires, achieves, secrecy, duration_days = "Frame", frozenset({"accomplice"}), "shamed:{target}", 0.5, 120
    evidence_conf = 0.85

    def _setup(self, ctx, actor, target):
        for v, by, _ in _killings(ctx, actor):
            kin = [k for k in life.grieving(ctx, v) if k not in (target, actor)]
            if by != target and v != target and kin:
                return beliefs.claim("killed", victim=v, by=target), kin
        return None, []

    def possible(self, ctx, actor, target, scheme):
        return (beliefs.enabled(ctx) and super().possible(ctx, actor, target, scheme) and target is not None
                and self._setup(ctx, actor, target)[0] is not None)

    def odds(self, ctx, actor, target, scheme):  # (nobody to frame it for: no chance, so no plan wastes a step on it)
        return 0.3 + 0.4 * trait(ctx, actor, "wits") if self._setup(ctx, actor, target)[0] is not None else 0.0

    def succeed(self, ctx, actor, target, scheme, event):
        claim, kin = self._setup(ctx, actor, target)
        for k in kin:  # (they find it: evidence, so they believe it firmly, and hold it against the target)
            beliefs.hold(ctx, k, claim, self.evidence_conf, event)
        _favour(ctx, target, -0.3)


class BearWitness(Action):
    """Public testimony to a killing the actor believes in: it corrects what the town believes."""

    name, achieves, duration_days = "BearWitness", "shamed:{target}", 30
    hearers, firm = 8, 0.8

    def _testimony(self, ctx, actor, target):
        for v, by, _ in _killings(ctx, actor, firm=self.firm):
            if by == target:
                return beliefs.claim("killed", victim=v, by=target)
        return None

    def possible(self, ctx, actor, target, scheme):
        return (beliefs.enabled(ctx) and super().possible(ctx, actor, target, scheme) and target is not None
                and self._testimony(ctx, actor, target) is not None)

    def odds(self, ctx, actor, target, scheme):
        return 0.5 + 0.3 * trait(ctx, actor, "charm")

    def succeed(self, ctx, actor, target, scheme, event):
        said = self._testimony(ctx, actor, target)
        town = _townsfolk(ctx, actor, exclude=(target,))
        heard = []
        for i in range(min(self.hearers, len(town))):
            h = ctx.choose(f"witness:{i}", [r for r in town if r not in heard], owner=scheme or actor)
            heard.append(h)
            beliefs.correct(ctx, h, said, event)
        if heard:  # (testimony nobody heard shames nobody)
            _favour(ctx, target, -0.3)
            minds.wound(ctx, target, "shame", event)


class Coup(Action):
    """Seize a realm's ruling office from its holder (S8 §9): a violent, secret action that needs a
    following. The usurper holds it, `legitimacy` seized and the old holder `deposed` (alive: where the
    usurper's own line can't hold it, the deposed line comes back). A failed coup costs favour."""

    name, requires, achieves, secrecy, duration_days, stakes = ("Coup", frozenset({"accomplice"}), "seized:{target}",
                                                                 0.5, 120, 3.0)
    present = True
    reads = frozenset({"ids:polity", "ruler", "ended", "members", "headship", "heir", "deposed", "name"})

    def _office(self, ctx, actor, target):
        found = throne(ctx, actor)
        return found if found and ctx.get(found[1], "holder") == target else None

    def possible(self, ctx, actor, target, scheme):
        return super().possible(ctx, actor, target, scheme) and target is not None             and self._office(ctx, actor, target) is not None

    def odds(self, ctx, actor, target, scheme):
        return 0.2 + 0.3 * trait(ctx, actor, "wits")

    def succeed(self, ctx, actor, target, scheme, event):
        polity, office = self._office(ctx, actor, target)
        if ctx.guarded(target):  # (canon, or a ripple, needs them on the throne)
            ctx.emit("polity.coup_foiled", {"usurper": (actor,), "ruler": (target,)}, purpose="coup_foiled",
                     actor=office, payload={"office": office}, causes=(Cause("event", event),))
            return False
        ctx.emit("polity.seized", {"usurper": (actor,), "deposed": (target,)}, purpose="seized", actor=office,
                 payload={"office": office, "polity": polity}, causes=(Cause("event", event),))
        ctx.set(office, "holder", actor)
        ctx.set(office, "legitimacy", "seized")
        ctx.set(office, "deposed", target)
        ctx.set(target, "offices", [o for o in ctx.get(target, "offices") or [] if o != office])
        ctx.set(actor, "offices", sorted((ctx.get(actor, "offices") or []) + [office]))
        houses.name_heir(ctx, office, actor)

    def fail(self, ctx, actor, target, scheme, event):
        _favour(ctx, actor, -0.3)


class Raid(Action):
    """A ruler's raid across a border (S8 §9): a border incident on purpose, a ledger entry that sours the
    relation. `target` is the neighbouring polity; it achieves their hostility (a single raid seldom does:
    a plot raids, and raids again)."""

    name, achieves, duration_days = "Raid", "hostile:{target}", 60
    reads = frozenset({"ids:polity", "ruler", "holder", "ended", "ids:route", "ends", "control"})

    def _border(self, ctx, actor, target):
        mine = ruled(ctx, actor) if _alive(ctx, actor) else None
        if mine is None or target is None or target == mine or not ctx.exists(target) or ctx.kind(target) != "polity" \
                or ctx.get(target, "ended") is not None:
            return None
        routes = [r for r in ctx.ids("route") if {ctx.get(e, "control") for e in ctx.get(r, "ends")} == {mine, target}]
        return (mine, routes) if routes else None

    def possible(self, ctx, actor, target, scheme):
        return self._border(ctx, actor, target) is not None

    def odds(self, ctx, actor, target, scheme):
        return 0.5 + 0.3 * trait(ctx, actor, "temper")

    def succeed(self, ctx, actor, target, scheme, event):
        mine, routes = self._border(ctx, actor, target)
        route = ctx.choose("raid", routes, owner=scheme or actor)
        rid = relations.rel_id(mine, target)
        ev = ctx.emit("polity.raid", {"raider": (actor,), "party": tuple(sorted((mine, target)))}, purpose="raid",
                      actor=actor, payload={"relation": rid, "route": route}, causes=(Cause("event", event),))
        relations.note(ctx, mine, target, "raid", ev.id)


class Rally(Action):
    """Win another house of the realm to one's cause (S8 §9, Recruit's cousin): politics, not friendship, so
    no tie is needed. A keyed pick among the other house heads of the actor's realm (the slighted, out of
    favour, likelier; never an enemy), who joins the scheme."""

    name, achieves, secrecy, duration_days = "Rally", "rallied", 0.2, 90
    reads = frozenset({"house", "headship", "holder", "ids:polity", "members", "ended", "favour", "ties", "a", "b",
                       "kind"})

    def _heads(self, ctx, actor):
        mine = ctx.get(actor, "house")
        realm = next((p for p in ctx.ids("polity") if ctx.get(p, "ended") is None and mine
                      and mine in (ctx.get(p, "members") or [])), None)
        if realm is None:
            return []
        ruler = ctx.get(ctx.get(realm, "ruler"), "holder") if ctx.get(realm, "ruler") else None
        skip = {mine, ctx.get(ruler, "house") if ruler else None}  # (not the ruler's own: they'd hardly rise with you)
        enemies = {ctx.get(t, "a") if ctx.get(t, "b") == actor else ctx.get(t, "b")
                   for t in ctx.get(actor, "ties") or [] if ctx.get(t, "kind") == "enemy"}
        out = []
        for h in sorted(ctx.get(realm, "members") or []):
            who = ctx.get(ctx.get(h, "headship"), "holder") if h not in skip else None
            if who and who != ruler and who not in enemies and _alive(ctx, who):
                out.append(who)
        return out

    def possible(self, ctx, actor, target, scheme):
        return _alive(ctx, actor) and bool(self._heads(ctx, actor))

    def odds(self, ctx, actor, target, scheme):
        return 0.3 + 0.4 * trait(ctx, actor, "charm")

    def succeed(self, ctx, actor, target, scheme, event):
        heads = [h for h in self._heads(ctx, actor) if h not in (ctx.get(scheme, "accomplices") or [] if scheme else [])]
        if not heads or not scheme:
            return
        pick = ctx.choose("rally", heads, owner=scheme,
                          weights=[1.0 + max(0.0, -float(ctx.get(h, "favour") or 0.0)) * 2 for h in heads])
        ctx.set(scheme, "accomplices", sorted(set(ctx.get(scheme, "accomplices") or []) | {pick}))


class Revolt(Action):
    """Rise against the realm (S8 §9): `target` is the realm. The house's seat becomes a realm of its own,
    ruled by its head (`polity.seceded`), and the realm goes to war to crush it (`war.crush`). A failed
    rising is treason before the ruler (`courts.trial`)."""

    name, requires, achieves, duration_days, stakes = "Revolt", frozenset({"rallied"}), "seceded:{target}", 60, 3.0
    reads = frozenset({"house", "headship", "holder", "seat", "control", "ended", "members", "ruler", "name",
                       "offices", "polity", "ids:route", "ends"})

    def possible(self, ctx, actor, target, scheme):
        found = governed(ctx, actor) if _alive(ctx, actor) else None
        return found is not None and found[0] == target

    def odds(self, ctx, actor, target, scheme):
        return 0.3 + 0.3 * trait(ctx, actor, "wits")

    def succeed(self, ctx, actor, target, scheme, event):
        _, house = governed(ctx, actor)
        seat = ctx.get(house, "seat")
        new, n = f"pol:{house.replace(':', '.')}:{ctx.today.year}", 1
        while ctx.exists(new):  # (risen again the same year, under a new head)
            n += 1
            new = f"pol:{house.replace(':', '.')}:{ctx.today.year}.{n}"
        for office in sorted(ctx.get(actor, "offices") or []):  # (the realm's offices they held are left behind)
            if ctx.get(office, "polity") == target:
                ctx.emit("people.office_vacant", {"last": (actor,)}, purpose="vacant", actor=office,
                         payload={"office": office}, causes=(Cause("event", event),))
                ctx.set(office, "holder", None)
                ctx.set(office, "heir", None)
                ctx.set(actor, "offices", [o for o in ctx.get(actor, "offices") or [] if o != office])
        rose = ctx.emit("polity.seceded", {"leader": (actor,), "from": (target,)}, purpose="seceded", actor=actor,
                        place=seat, payload={"polity": new, "seat": seat}, causes=(Cause("event", event),))
        ctx.create("polity", new, {"name": f"the free lands of {ctx.get(seat, 'name') or seat}", "kind": "free city",
                                   "government": "ruler", "seat": seat, "ruler": ctx.get(house, "headship"),
                                   "members": [house], "founded": ctx.today.to_json(), "ended": None, "draft": False,
                                   "seceded_from": target})
        ctx.set(target, "members", [m for m in ctx.get(target, "members") or [] if m != house])
        geo.apply_change(ctx, {"place": seat, "control": new, "why": f"{new} rose against {target}"})
        for route in ctx.ids("route"):  # (its other neighbours across the seat's roads: a neutral first acquaintance)
            ends = ctx.get(route, "ends")
            if seat in ends:
                other = ctx.get(ends[1] if ends[0] == seat else ends[0], "control")
                if other and other not in (new, target) and not ctx.exists(relations.rel_id(new, other)):
                    ctx.create("relation", relations.rel_id(new, other), relations.fields(new, other, "polity", ctx.today))
        war.crush(ctx, target, new, rose.id)

    def fail(self, ctx, actor, target, scheme, event):
        courts.trial(ctx, actor, ctx.get(ctx.get(target, "ruler"), "holder"), event, grave=1.0, scheme=scheme)


class Flee(Action):
    """Leave home: by road to any settlement within `flee_days` (S4 §5), else, in a world without routes,
    at once to another settlement of the region. The step is the decision; the journey takes the road's days."""

    name, achieves, duration_days = "Flee", "safe", 30  # at once, in a world without routes
    deciding_days = 7  # with routes: the decision; the journey carries the road's days

    def duration(self, ctx, actor, target) -> int:
        return self.deciding_days if travel.has_routes(ctx) else self.duration_days

    def _options(self, ctx, actor) -> dict[str, int]:
        """Where they could go ({settlement: days}; 0 without routes), never a realm that exiled them."""
        home = ctx.get(actor, "place")
        if travel.has_routes(ctx):
            found = travel.destinations(ctx, home, int(ctx.params.get("flee_days", travel.FLEE_DAYS)), actor)
        else:
            region = ctx.get(home, "region")
            found = {s: 0 for s in ctx.ids("settlement") if s != home and ctx.get(s, "region") == region}
        return {s: d for s, d in found.items() if not courts.barred(ctx, actor, s)}

    def _elsewhere(self, ctx, actor):
        return list(self._options(ctx, actor))

    def possible(self, ctx, actor, target, scheme):  # not the married, nor those who hold office (S4: families travel)
        return (_alive(ctx, actor) and ctx.get(actor, "spouse") is None and not ctx.get(actor, "offices")
                and not ctx.get(actor, "journey") and bool(self._elsewhere(ctx, actor)))

    def odds(self, ctx, actor, target, scheme):
        return 0.8

    def succeed(self, ctx, actor, target, scheme, event):
        options = self._options(ctx, actor)
        if travel.has_routes(ctx):
            new = ctx.choose("flee", list(options), owner=scheme or actor, weights=[1.0 / d for d in options.values()])
            travel.depart(ctx, actor, new, "flee", causes=(Cause("event", event),) if event else ())
            return
        travel.relocate(ctx, actor, ctx.choose("flee", list(options), owner=scheme or actor))


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
    "spouse", "mother", "father", "ids:settlement", "offices", "plan", "step"}) | travel.READS | courts.BAR_READS)
WRITES = (life.DIE_WRITES | families.Marriage.writes | travel.WRITES
          | frozenset({"favour", "wound", "need", "accomplices", "state", "holder", "legitimacy", "deposed", "offices",
                       "heir", "new:polity", "members", "new:war", "new:relation", "stance"})
          | geo.CHANGE_WRITES | lines.WRITES)  # (a revolt: a realm, a war)
READS = READS | geo.CHANGE_READS | lines.READS
EVENT_TYPES = ((ACTION, SEIZED, COUP_FOILED, RAID, SECEDED) + life.DIE_EVENTS + (families.MARRIAGE,) + population.LOD_TYPES
               + travel.EVENT_TYPES + (war.DECLARED, war.STANCE, geo.changed_type(), lines.LINE))


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
