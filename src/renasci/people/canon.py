"""Canon for people (S3 spec §4.3, §5): forcing pinned births and reigns at their deadlines.

A **birth pin** (`people.birth`, with roles such as `father` and a `bind` for the child) is usually met
by an ordinary birth: the director observes it and binds the canon id. If no such birth has happened
by the end of its window, `BirthForcer` constructs one, caused by the pin:

- the parents are the pinned roles, resolved through bindings (ruler k is "whoever v:Ruler-k became"),
  and must exist, be alive, and (a father) be at least his race's marriage age;
- with no mother pinned, the father's wife, if she is alive and fertile; otherwise a woman promoted from
  the father's settlement, who bears the child outside marriage (no bigamy, and the strain says so);
  a father with no wife at all first marries her. She is of her settlement's race, and the child takes
  the mother's race, as in any birth;
- the child's sex is the pinned one.

A forcer that can't do its job returns a reason, which the director logs with the violation.

A **reign pin** (`people.succession`, roles `{successor: [...]}`, payload `office`) is usually met by an
ordinary succession. If the pinned successor doesn't hold the office by the deadline, `SuccessionForcer`
makes the holder **abdicate** in their favour: nobody is killed to make room.

Forcing is the last resort. Steering arrives in M3 (#114).
"""

from __future__ import annotations

from renasci.core.pins import Forcer
from renasci.people import families, houses, life, population, ties
from renasci.people.races import age_years


def _of_age_to_bear(ctx, woman: str, races) -> bool:
    race = races[ctx.get(woman, "race")]
    return ctx.status(woman) == "active" and race.fertile[0] <= age_years(
        ctx.calendar, ctx.get(woman, "born"), ctx.today) <= race.fertile[1]


class BirthForcer(Forcer):
    name, handles = "people.force_birth", "people.birth"
    reads = (life.Births.reads | families.Marriage.reads | houses.READS | population.COLUMN_READS
             | frozenset({"place", "binding"}))
    writes = life.Births.writes | families.Marriage.writes
    event_types = (life.BIRTH, families.MARRIAGE) + population.LOD_TYPES

    def force(self, ctx, pin) -> bool:
        races, catalogue, house_from = life.world(ctx)
        roles = pin.payload.get("roles", {})
        father = ctx.resolve(roles["father"][0]) if roles.get("father") else None
        mother = ctx.resolve(roles["mother"][0]) if roles.get("mother") else None
        if any(p is not None and not ctx.exists(p) for p in (father, mother)):
            return "a pinned parent never came to be"
        if any(p is not None and ctx.status(p) != "active" for p in (father, mother)):
            return "a pinned parent is not alive"
        if father is not None and age_years(ctx.calendar, ctx.get(father, "born"), ctx.today) <                 races[ctx.get(father, "race")].marriage[0]:
            return "the pinned father is too young"
        if mother is None:
            if father is None:
                return "the pin names no parent"
            wife = ctx.get(father, "spouse")
            if wife is not None and _of_age_to_bear(ctx, wife, races):
                mother = wife
            else:
                home = ctx.get(father, "place")
                race = races[ctx.get(home, "race")]  # she comes from the settlement's masses
                mother = population.promote_person(ctx, home, "pinned_birth", sex="f", ages=race.fertile)
                if mother is None:
                    return "nobody to bear the child"
                if wife is None:
                    families.Marriage._wed(ctx, father, mother, ctx.params.get("residence", "husband"), commoner=True)
        settlement = ctx.get(mother, "place")
        sex = (pin.payload.get("bind") or {}).get("fields", {}).get("sex")
        race = races[ctx.get(mother, "race")]
        life.give_birth(ctx, settlement, mother, father, race, catalogue, house_from, sex=sex)
        return True


class SuccessionForcer(Forcer):
    name, handles = "people.force_succession", "people.succession"
    reads = houses.READS | frozenset({"binding"})
    writes = houses.WRITES
    event_types = (houses.SUCCESSION, houses.HEIR_NAMED)

    def force(self, ctx, pin) -> bool:
        office = pin.payload.get("office")
        roles = pin.payload.get("roles", {})
        if not office or not roles.get("successor"):
            return "the pin names no office or successor"
        successor = ctx.resolve(roles["successor"][0])
        if not ctx.exists(successor):
            return "the pinned successor never came to be"
        if ctx.status(successor) != "active":
            return "the pinned successor is not alive"
        holder = ctx.get(office, "holder")
        if holder == successor:
            return "the successor already held the office before the window opened"
        living = holder is not None and ctx.status(holder) == "active"  # else their succession is still pending
        ctx.emit("people.succession", {"predecessor": (holder,) if holder else (), "successor": (successor,)},
                 purpose="abdication" if living else "succession", actor=office,
                 payload={"office": office, "abdication": living})
        if living:
            ctx.set(holder, "offices", [o for o in ctx.get(holder, "offices") or [] if o != office])
        ctx.set(office, "holder", successor)
        if ctx.get(office, "legitimacy") not in (None, "lawful"):  # (as `houses.succeed`: lawful again)
            ctx.set(office, "legitimacy", "lawful")
        ctx.set(successor, "offices", sorted((ctx.get(successor, "offices") or []) + [office]))
        houses.name_heir(ctx, office, successor)
        return True


FORCERS = (BirthForcer(), SuccessionForcer())
__all__ = ["BirthForcer", "SuccessionForcer", "FORCERS", "ties"]
