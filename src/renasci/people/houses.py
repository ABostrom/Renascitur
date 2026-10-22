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
"""

from __future__ import annotations

from renasci.core.calendar import Span
from renasci.core.events import EventType
from renasci.core.systems import System

HEIR_NAMED = EventType("people.heir_named", 1, roles={"holder": (1, 1), "heir": (0, 1)}, payload={"office": "id"})
SUCCESSION = EventType("people.succession", 1, roles={"predecessor": (1, 1), "successor": (1, 1)},
                       payload={"office": "id", "abdication": "bool"}, dead_roles=("predecessor",))
HOUSE_EXTINCT = EventType("people.house_extinct", 1, roles={"last": (1, 1)}, payload={"house": "id"},
                          dead_roles=("last",))
OFFICE_VACANT = EventType("people.office_vacant", 1, roles={"last": (1, 1)}, payload={"office": "id"},
                          dead_roles=("last",))
EVENT_TYPES = (HEIR_NAMED, SUCCESSION, HOUSE_EXTINCT, OFFICE_VACANT)

# What succession reads and writes; people.life declares these too, since it runs the follow-up.
READS = frozenset({"offices", "headship", "holder", "heir", "rule", "house", "children", "father", "mother",
                   "sex", "status", "extinct"})
WRITES = frozenset({"holder", "heir", "offices", "extinct"})


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


class MalePreferencePrimogeniture(SuccessionRule):
    name, male_first = "male_preference_primogeniture", True


class AbsolutePrimogeniture(SuccessionRule):
    name, male_first = "absolute_primogeniture", False


RULES: dict[str, SuccessionRule] = {r.name: r for r in (MalePreferencePrimogeniture(), AbsolutePrimogeniture())}


def name_heir(ctx, office: str, holder: str) -> None:
    """Recompute the heir; emit `people.heir_named` only if it changed."""
    line = RULES[ctx.get(office, "rule")].candidates(ctx, office, holder)
    heir = line[0] if line else None
    if heir != ctx.get(office, "heir"):
        ctx.emit("people.heir_named", {"holder": (holder,), "heir": (heir,) if heir else ()}, purpose="heir",
                 actor=office, payload={"office": office})
        ctx.set(office, "heir", heir)


def vacate(ctx, person: str) -> None:
    """Called when `person` dies: each office they held passes on tomorrow."""
    for office in ctx.get(person, "offices") or []:
        ctx.schedule(Span(days=1), "succession", entity=office, payload={"office": office, "predecessor": person})


def succeed(ctx, office: str, predecessor: str) -> None:
    """The next in line takes the office, in the house's scope; with nobody left, the house dies out."""
    house = ctx.get(office, "house")
    with ctx.scope(house or office):
        if ctx.get(office, "holder") != predecessor:
            return  # already settled
        line = RULES[ctx.get(office, "rule")].candidates(ctx, office, predecessor)
        if not line:
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
        successor = line[0]
        ctx.emit("people.succession", {"predecessor": (predecessor,), "successor": (successor,)},
                 purpose="succession", actor=office, payload={"office": office, "abdication": False})
        ctx.set(office, "holder", successor)
        ctx.set(successor, "offices", sorted((ctx.get(successor, "offices") or []) + [office]))
        name_heir(ctx, office, successor)


class Houses(System):
    name, cadence = "people.houses", "yearly"
    reads = READS | {"ids:house"}
    writes = frozenset({"heir"})
    event_types = (HEIR_NAMED,)

    def run(self, ctx):
        for house in ctx.ids("house"):
            with ctx.scope(house):
                if ctx.get(house, "extinct") is not None:
                    continue
                office = ctx.get(house, "headship")
                holder = ctx.get(office, "holder")
                if holder is not None and ctx.status(holder) == "active":  # a dead holder's succession is pending
                    name_heir(ctx, office, holder)
