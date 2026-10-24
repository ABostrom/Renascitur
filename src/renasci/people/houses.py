"""Houses, offices and succession (S3 spec §5).

A **house** is a family name with a seat and a rank. Its **headship** is an **office**, and so is any
other title (a throne). An office has a `holder`, an `heir` and a `rule`: the name of a succession
rule class, which orders the living candidates.

**Line of succession** (`line_of_succession`): the holder's children in birth order, each followed by
their own line (a dead child's line still counts), sons before daughters under male preference; then
the same from the holder's parent the house comes through (`house_from`: the father, or the mother),
which adds the holder's siblings and their lines, then that parent's parent, up to `reach`
generations. Ancestors are passed through, never chosen: succession goes down and across, not up. Only living members of the office's house are candidates, but the walk passes
through anyone, so a house member whose parent left the house is still found. Every step reads the
recorded `children`, `father`, `sex`, `status` and `house` fields, so a birth or death that changes the
line is a recorded read that differs (explainable).

- `people.houses` (yearly, one `ctx.scope(house)` per house): recomputes each headship's heir, and
  emits `people.heir_named` only when the heir changes.
- **Succession** happens a day after the holder's death, as a follow-up of `people.life` (`die`
  schedules it; `Life.handle` runs `succeed`), in the house's scope: the next in line becomes holder,
  or the house dies out (`people.house_extinct`).

**Offices of a polity** (S8 spec §3, #120): an office may have a `scope` (house, the default; polity;
faction) and a `legitimacy` (lawful, or seized). A rule names its `candidates`, `choose`s the successor
(the first in line, by default) and names a `presumptive` heir. Two rules beyond the primogenitures:

- **appointment:** the holder of the `appointer` office picks among the realm's notables (the heads of
  its member houses and their heirs), by standing (a house's rank, the person's favour), in a keyed draw:
  `polity.appointed`. While the appointer's office is vacant, the office waits.
- **election:** the heads of the polity's member houses vote (`polity.vote`, in the polity's scope): each
  voter favours themselves, their friends and the well-standing, and shuns rivals and enemies, in a
  keyed draw; each vote weighs by the voter's standing; ties go to the elder.

An office cast vacant, or left vacant, is filled at `people.houses`'s yearly pass.

**Cadet branches** (S8 spec §3.5, #161; on when the world sets `cadet_size`): at the yearly pass, a house
of at least `cadet_size` living members (its head and their line) whose head has a grown younger son (not
the heir, holding no office, plotting no seizure, not canon; a daughter where the house comes through the
mother) founds a cadet house, at odds of `cadet_rate` for each member over the size less one (at most 0.5).
The eldest such son heads it (`people.cadet_founded`): "the <his name> branch of <the root house>",
`cadet_of` the parent, seated where he lives, a rank below, under the same rule. He, his spouse if of the
parent house, and his descendants in it through him (by `house_from`) move to the cadet house, which joins
every polity and faction the parent belongs to. (Cadets leave the parent's line; a cadet taking up an
extinct parent is future. Canon people never move: a vault house is the vault's to change.)
"""

from __future__ import annotations

from renasci.core.calendar import Span
from renasci.core.events import Cause, EventType
from renasci.core.systems import System
from renasci.people.races import age_years

HEIR_NAMED = EventType("people.heir_named", 1, roles={"holder": (1, 1), "heir": (0, 1)}, payload={"office": "id"})
SUCCESSION = EventType("people.succession", 1, roles={"predecessor": (0, 1), "successor": (1, 1)},
                       payload={"office": "id", "abdication": "bool"}, dead_roles=("predecessor",))
HOUSE_EXTINCT = EventType("people.house_extinct", 1, roles={"last": (1, 1)}, payload={"house": "id"},
                          dead_roles=("last",))
OFFICE_VACANT = EventType("people.office_vacant", 1, roles={"last": (1, 1)}, payload={"office": "id"},
                          dead_roles=("last",))
VOTE = EventType("polity.vote", 1, roles={"voter": (1, 1000), "winner": (1, 1)}, payload={"office": "id", "tally": "json"})
APPOINTED = EventType("polity.appointed", 1, roles={"by": (1, 1), "appointee": (1, 1)}, payload={"office": "id"})
CADET = EventType("people.cadet_founded", 1, roles={"founder": (1, 1), "head": (1, 1)},
                  payload={"house": "str", "parent": "id"})
EVENT_TYPES = (HEIR_NAMED, SUCCESSION, HOUSE_EXTINCT, OFFICE_VACANT, VOTE, APPOINTED, CADET)
CADET_MAX = 0.5

# What succession reads and writes; people.life declares these too, since it runs the follow-up.
READS = frozenset({"offices", "headship", "holder", "heir", "rule", "house", "children", "father", "mother",
                   "sex", "status", "extinct", "scope", "polity", "members", "appointer", "rank", "favour", "ties",
                   "a", "b", "kind", "born", "legitimacy"})
WRITES = frozenset({"holder", "heir", "offices", "extinct", "legitimacy"})


def line_of_succession(get, status, holder: str, house: str | None, male_first: bool, reach: int = 3,
                       via: str = "father") -> list[str]:
    """Living members of `house` in order of succession to `holder`.

    `get(entity, field)` and `status(entity)` read the world (a ctx, or a dict in tests).
    """
    order: list[str] = []
    seen = {holder}

    def eligible(p: str) -> bool:
        return status(p) == "active" and (house is None or get(p, "house") == house)

    def descend(person: str) -> None:
        children = list(get(person, "children") or [])
        if male_first:  # stable: birth order within each sex
            children = [c for c in children if get(c, "sex") == "m"] + [c for c in children if get(c, "sex") != "m"]
        for child in children:
            if child in seen:
                continue
            seen.add(child)
            if eligible(child):
                order.append(child)
            descend(child)

    descend(holder)
    ancestor = holder
    for _ in range(reach):
        ancestor = get(ancestor, via)
        if not ancestor:
            break
        seen.add(ancestor)  # passed through, never a candidate
        descend(ancestor)  # the holder's own line is already seen, so this adds siblings, then uncles...
    return order


class SuccessionRule:
    name = ""
    male_first = True

    def candidates(self, ctx, office: str, holder: str) -> list[str]:
        via = "mother" if ctx.params.get("house_from") == "mother" else "father"
        return line_of_succession(ctx.get, ctx.status, holder, ctx.get(office, "house"), self.male_first, via=via)

    def choose(self, ctx, office: str, predecessor: str | None, line: list[str]) -> tuple[str | None, tuple]:
        """(who takes the office now, or None: nobody yet, the office waits; the events that decided it)."""
        return (line[0] if line else None), ()

    def presumptive(self, ctx, office: str, holder: str, line: list[str]) -> str | None:
        """Who would take it next, as things stand (the heir)."""
        return line[0] if line else None


class MalePreferencePrimogeniture(SuccessionRule):
    name, male_first = "male_preference_primogeniture", True


class AbsolutePrimogeniture(SuccessionRule):
    name, male_first = "absolute_primogeniture", False


def _notables(ctx, polity: str) -> list[str]:
    """A polity's notables: the living heads of its member houses and their heirs."""
    out = []
    for house in sorted(ctx.get(polity, "members") or []):
        office = ctx.get(house, "headship")
        for who in (ctx.get(office, "holder"), ctx.get(office, "heir")) if office else ():
            if who and ctx.status(who) == "active" and who not in out:
                out.append(who)
    return out


def _heads(ctx, polity: str) -> list[str]:
    out = []
    for house in sorted(ctx.get(polity, "members") or []):
        office = ctx.get(house, "headship")
        holder = ctx.get(office, "holder") if office else None
        if holder and ctx.status(holder) == "active":
            out.append(holder)
    return out


def standing(ctx, person: str) -> float:
    """How much a person counts in a realm: their house's rank, and their favour at court."""
    house = ctx.get(person, "house")
    rank = float(ctx.get(house, "rank") or 0) if house else 0.0
    return max(0.1, 1.0 + 0.25 * rank + float(ctx.get(person, "favour") or 0.0))


class Appointment(SuccessionRule):
    """The holder of the `appointer` office picks among the realm's notables, by standing."""

    name = "appointment"

    def candidates(self, ctx, office, holder):
        return [p for p in _notables(ctx, ctx.get(office, "polity")) if p != holder]

    def choose(self, ctx, office, predecessor, line):
        appointer = ctx.get(office, "appointer")
        by = ctx.get(appointer, "holder") if appointer else None
        if not line or by is None or ctx.status(by) != "active":
            return None, ()  # (no one to appoint, or no one to appoint them: the office waits)
        pick = ctx.choose(f"appoint:{office}", line, owner=office, weights=[standing(ctx, p) for p in line],
                          stakes=1.0, roles={"by": [by]})
        ev = ctx.emit("polity.appointed", {"by": (by,), "appointee": (pick,)}, purpose="appoint", actor=office,
                      payload={"office": office})
        return pick, (Cause("event", ev.id),)

    def presumptive(self, ctx, office, holder, line):
        return max(line, key=lambda p: (standing(ctx, p), p)) if line else None


def _tie(ctx, a: str, b: str) -> str | None:
    for t in ctx.get(a, "ties") or []:
        if {ctx.get(t, "a"), ctx.get(t, "b")} == {a, b}:
            return ctx.get(t, "kind")
    return None


SELF_VOTE = 0.75  # (a head leans to themselves, but standing and ties still sway the vote)


def _seniority(ctx, person: str) -> list:
    """For a tie: the elder first (no birth date: last)."""
    born = ctx.get(person, "born")
    return [-x for x in born] if born else [float("-inf")]


class Election(SuccessionRule):
    """The heads of the polity's member houses vote; each vote weighs by the voter's standing."""

    name = "election"
    LEAN = {"friend": 1.0, "mentor": 0.5, "rival": -0.8, "enemy": -1.5}

    def candidates(self, ctx, office, holder):
        return [p for p in _heads(ctx, ctx.get(office, "polity")) if p != holder] or _heads(ctx, ctx.get(office, "polity"))

    def choose(self, ctx, office, predecessor, line):
        voters = _heads(ctx, ctx.get(office, "polity"))
        if not line or not voters:
            return None, ()
        tally: dict[str, float] = {}
        for v in voters:
            weights = [max(0.05, standing(ctx, c) + (SELF_VOTE if c == v else self.LEAN.get(_tie(ctx, v, c), 0.0)))
                       for c in line]
            choice = ctx.choose(f"vote:{office}", line, owner=v, weights=weights)
            tally[choice] = round(tally.get(choice, 0.0) + standing(ctx, v), 6)
        winner = max(tally, key=lambda c: (tally[c], _seniority(ctx, c), c))
        ev = ctx.emit("polity.vote", {"voter": tuple(voters), "winner": (winner,)}, purpose="vote", actor=office,
                      payload={"office": office, "tally": dict(sorted(tally.items()))})
        return winner, (Cause("event", ev.id),)

    def presumptive(self, ctx, office, holder, line):
        line = [p for p in line if p != holder]
        return max(line, key=lambda p: (standing(ctx, p), p)) if line else None


RULES: dict[str, SuccessionRule] = {r.name: r for r in (MalePreferencePrimogeniture(), AbsolutePrimogeniture(),
                                                        Appointment(), Election())}


def name_heir(ctx, office: str, holder: str) -> None:
    """Recompute the heir; emit `people.heir_named` only if it changed."""
    rule = RULES[ctx.get(office, "rule")]
    heir = rule.presumptive(ctx, office, holder, rule.candidates(ctx, office, holder))
    if heir != ctx.get(office, "heir"):
        ctx.emit("people.heir_named", {"holder": (holder,), "heir": (heir,) if heir else ()}, purpose="heir",
                 actor=office, payload={"office": office})
        ctx.set(office, "heir", heir)


def vacate(ctx, person: str) -> None:
    """Called when `person` dies: each office they held passes on tomorrow."""
    for office in ctx.get(person, "offices") or []:  # (a polity's offices a day later: the houses choose first)
        days = 1 if ctx.get(office, "scope") in (None, "house") else 2
        ctx.schedule(Span(days=days), "succession", entity=office, payload={"office": office, "predecessor": person})


def handle_succession(ctx, activation) -> None:
    """The follow-up `vacate` schedules on whichever system called `life.die`."""
    if activation.purpose != "succession":
        raise ValueError(f"{ctx.system.name} has no follow-up {activation.purpose!r}")
    succeed(ctx, activation.payload["office"], activation.payload["predecessor"])


def succeed(ctx, office: str, predecessor: str | None) -> None:
    """The next in line takes the office, in the house's (or the polity's) scope; with nobody left, the
    house dies out. With no predecessor, a vacant office is filled."""
    house = ctx.get(office, "house")
    with ctx.scope(house or ctx.get(office, "polity") or office):
        if ctx.get(office, "holder") != predecessor:
            return  # already settled
        rule = RULES[ctx.get(office, "rule")]
        line = rule.candidates(ctx, office, predecessor)
        successor, decided = rule.choose(ctx, office, predecessor, line)
        if successor is None and line:  # (the office waits: its appointer is vacant)
            if predecessor is not None:  # (and stands vacant meanwhile, for the yearly pass to fill)
                ctx.emit("people.office_vacant", {"last": (predecessor,)}, purpose="vacant", actor=office,
                         payload={"office": office})
                ctx.set(office, "holder", None)
                ctx.set(office, "heir", None)
            return
        if not line or successor is None:
            if predecessor is None:
                return  # (a vacant office with no one to fill it: it stays vacant)
            if house and ctx.get(house, "headship") == office:  # the house itself ends
                ctx.emit("people.house_extinct", {"last": (predecessor,)}, purpose="extinct", actor=office,
                         payload={"house": house})
                ctx.set(house, "extinct", ctx.today.to_json())
            else:  # a title with nobody to take it
                ctx.emit("people.office_vacant", {"last": (predecessor,)}, purpose="vacant", actor=office,
                         payload={"office": office})
            ctx.set(office, "holder", None)
            ctx.set(office, "heir", None)
            return
        ctx.emit("people.succession", {"predecessor": (predecessor,) if predecessor else (), "successor": (successor,)},
                 purpose="succession", actor=office, payload={"office": office, "abdication": False}, causes=decided)
        ctx.set(office, "holder", successor)
        if ctx.get(office, "legitimacy") not in (None, "lawful"):  # (a lawful succession ends a seizure)
            ctx.set(office, "legitimacy", "lawful")
        ctx.set(successor, "offices", sorted((ctx.get(successor, "offices") or []) + [office]))
        name_heir(ctx, office, successor)


def cadet(ctx, house: str, office: str, holder: str) -> None:
    """Perhaps found a cadet branch of `house` (in its scope): see the module's doc."""
    size = ctx.params.get("cadet_size")
    if not size:
        return
    rule = RULES[ctx.get(office, "rule")]
    line = rule.candidates(ctx, office, holder)
    if len(line) + 1 < size:
        return
    from renasci.people.life import world

    races, _, _ = world(ctx)
    heir = ctx.get(office, "heir")
    via = "mother" if ctx.params.get("house_from") == "mother" else "father"
    line_sex = "f" if via == "mother" else "m"  # (who passes the house on to their children)

    def plotting(p) -> bool:
        return any(ctx.get(a, "class") == "Seize" for a in ctx.get(p, "ambitions") or [])

    sons = [c for c in ctx.get(holder, "children") or []
            if c != heir and ctx.status(c) == "active" and ctx.get(c, "house") == house and not ctx.get(c, "offices")
            and ctx.get(c, "sex") == line_sex and not c.startswith("v:") and not plotting(c)
            and age_years(ctx.calendar, ctx.get(c, "born"), ctx.today) >= races[ctx.get(c, "race")].marriage[0]]
    p = min(CADET_MAX, float(ctx.params.get("cadet_rate", 0.05)) * (len(line) + 2 - size))
    if not sons or not ctx.chance(p, "cadet", owner=house):
        return
    founder = sons[0]  # (the eldest: children are in birth order)
    new = f"{house}~{founder.replace(':', '.')}"
    seat = ctx.get(founder, "place") or ctx.get(house, "seat")
    root = house
    while ctx.get(root, "cadet_of"):
        root = ctx.get(root, "cadet_of")
    name = f"the {ctx.get(founder, 'name') or founder} branch of {ctx.get(root, 'name')}"
    ctx.emit("people.cadet_founded", {"founder": (founder,), "head": (holder,)}, purpose="cadet", actor=house,
             place=seat, payload={"house": new, "parent": house})
    ctx.create("house", new, {"name": name, "seat": seat, "rank": max(0, int(ctx.get(house, "rank") or 0) - 1),
                              "founded": ctx.today.to_json(), "headship": f"{new}-head", "extinct": None,
                              "cadet_of": house})
    ctx.create("office", f"{new}-head", {"name": f"Head of {name}", "holder": founder, "heir": None,
                                         "rule": rule.name, "house": new})
    moving, todo = [founder], [founder]
    spouse = ctx.get(founder, "spouse")
    if spouse and ctx.get(spouse, "house") == house and not spouse.startswith("v:"):
        moving.append(spouse)
    while todo:  # (descendants through the line the house passes by, still of the parent house)
        parent = todo.pop(0)
        for c in ctx.get(parent, "children") or []:
            if ctx.get(c, via) == parent and ctx.get(c, "house") == house and not c.startswith("v:") and c not in moving:
                moving.append(c)
                todo.append(c)
    for who in moving:
        ctx.set(who, "house", new)
    ctx.set(founder, "offices", sorted((ctx.get(founder, "offices") or []) + [f"{new}-head"]))
    for group in ctx.ids("polity") + ctx.ids("faction"):
        members = ctx.get(group, "members") or []
        if house in members:
            ctx.set(group, "members", sorted(members + [new]))
    name_heir(ctx, f"{new}-head", founder)


class Houses(System):
    name, cadence = "people.houses", "yearly"
    reads = READS | {"ids:house", "ids:office", "ids:polity", "ids:faction", "race", "spouse", "place", "seat", "name",
                     "cadet_of", "ambitions", "class"}
    writes = WRITES | {"house", "members", "new:house", "new:office"}
    event_types = EVENT_TYPES

    def coarse_fallback(self, ctx, years: int) -> None:
        """A coarse step (S8 §7: rulers only): the yearly pass, once. Successions follow deaths, whenever."""
        self.run(ctx)

    def run(self, ctx):
        for office in ctx.ids("office"):  # (a polity's offices: vacant ones filled, heirs named)
            if ctx.get(office, "scope") in (None, "house"):  # (scope and polity never change)
                continue
            where = ctx.get(office, "polity") or office
            with ctx.scope(where):
                holder = ctx.get(office, "holder")
                alive = holder is not None and ctx.status(holder) == "active"
                if alive:
                    name_heir(ctx, office, holder)
            if not alive:
                succeed(ctx, office, holder)  # (vacant: filled; a dead holder's, if it never passed on: settled)
        for house in ctx.ids("house"):
            with ctx.scope(house):
                if ctx.get(house, "extinct") is not None:
                    continue
                office = ctx.get(house, "headship")
                holder = ctx.get(office, "holder")
                if holder is not None and ctx.status(holder) == "active":  # a dead holder's succession is pending
                    name_heir(ctx, office, holder)
                    cadet(ctx, house, office, holder)
