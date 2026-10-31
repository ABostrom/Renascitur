"""Marks: what a thing has become (vision spec §3, #163). A sword turns bloodthirsty, a town is haunted, a survivor is
shaken. A mark is earned from what happened, not handed out.

Things build up in stocks and fields, in the systems where they happen, and those systems never name a mark: a
deed adds to an object's `blood`, a near miss to a person's `dread`, the dead lie in a town's `corpses`. Each year
`marks.change` looks at every entity of every kind a mark fits. When what it `needs` is met, a draw at `chance` gives
it the mark (`mark.gained`, caused by what filled those stocks, or the deeds behind its fame; a skill has no event to
cite); a mark that `fades` goes when they drop below half of that (`mark.lost`). `ebb` is how much of what brought it
still weighs on it a year on, for a mark that time eases though nothing drains the stock. An entity's `acquired` lists
its marks, with the date, the event and what each changed.

**What a mark does** is write through what the engine already reads, so nothing else has to know about marks. On a
person, `gives` moves `traits` (by the world's role names, so `wits`, `charm`, `temper`; a role the world doesn't map
does nothing), which every action's odds, drive and urge read. On anything else, it moves the named field: a haunted
town's `danger` is what its people's `safety` reads. Values stay in [0, 1]. Marks aren't inherited: a child's traits
come from the genome.

A mark is an entry in the `marks` pool, so an extension adds one with `pools.marks.add(Mark(...))`, for any kind of
entity. `needs` names stocks, and `fame` and `skill` (of the holder's job) as well. `pre` names marks it must already
have, so they can stack. The fields in `gives` are its `reads` and `writes`. The catalogue here is a draft.

People are looked at town by town, one scope each, as `people.life` does: a scope per person logged a row for everyone,
every year, and a scope for all of them would lose where a change happened. Other kinds take a scope of their own.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from renasci.core import stocks
from renasci.core.events import Cause, EventType
from renasci.core.pools import pools
from renasci.core.systems import System
from renasci.relations import over

GAINED = EventType("mark.gained", 1, roles={"subject": (1, 1)}, payload={"mark": "str", "name": "str"})
LOST = EventType("mark.lost", 1, roles={"subject": (1, 1)}, payload={"mark": "str", "name": "str"})
HOLD = 0.5  # (a fading mark goes when what brought it falls below this share of what it needed)


@dataclass(frozen=True)
class Mark:
    id: str
    name: str
    fits: tuple[str, ...]
    needs: dict
    gives: dict = field(default_factory=dict)
    chance: float = 0.2
    fades: bool = False
    pre: tuple[str, ...] = ()
    ebb: float = 1.0

    @property
    def reads(self) -> frozenset:
        return frozenset(self.gives)

    writes = reads


MARKS = pools.define("marks", key=lambda m: m.id)
for _mark in (
    Mark("bloodthirsty", "bloodthirsty", ("object",), {"blood": 3}, {"fame": 0.2}),
    Mark("haunted", "haunted", ("settlement",), {"corpses": 150}, {"danger": 0.2}, chance=0.5, fades=True),
    Mark("shaken", "shaken", ("person",), {"dread": 2}, {"temper": 0.2, "charm": -0.1}, fades=True, ebb=0.8),
    Mark("adept", "an adept", ("person",), {"skill": 0.9}, {"wits": 0.1}),
):
    MARKS.add(_mark)
MARKS.freeze()


def reading(ctx, entity: str, key: str) -> float:
    """What a mark's `needs` looks at on an entity."""
    if key == "fame":
        return float(ctx.get(entity, "fame") or 0.0)
    if key == "skill":
        return float((ctx.get(entity, "skills") or {}).get(ctx.get(entity, "job"), 0.0))
    return stocks.level(ctx, entity, key)


def met(ctx, entity: str, mark: Mark, share: float = 1.0, eased: float = 1.0) -> bool:
    return all(reading(ctx, entity, k) * eased >= v * share for k, v in mark.needs.items())


def held(ctx, entity: str, mark_id: str) -> dict | None:
    return next((m for m in ctx.get(entity, "acquired") or [] if m["id"] == mark_id), None)


def why(ctx, entity: str, mark: Mark) -> tuple:
    """What brought a mark: what filled its stocks, or the latest deeds behind a thing's fame."""
    found = [c for k in sorted(mark.needs) for c in stocks.because(ctx, entity, k, 3)]
    if "fame" in mark.needs:
        found += [Cause("event", e) for e in (ctx.get(entity, "deeds") or [])[-3:]]
    return tuple(found)


def _apply(ctx, kind: str, entity: str, gives: dict, sign: int = 1) -> dict:
    """Move what a mark moves; returns what really moved, so a lost mark puts it back exactly."""
    moved = {}
    if kind == "person":
        names = ctx.params.get("traits") or {}
        traits = dict(ctx.get(entity, "traits") or {})
        for role, delta in sorted(gives.items()):
            name = names.get(role)
            if not name:
                continue
            was = float(traits.get(name, 0.5))
            traits[name] = round(min(1.0, max(0.0, was + sign * delta)), 6)
            moved[role] = round(traits[name] - was, 6)
        ctx.set(entity, "traits", traits)
        return moved
    for name, delta in sorted(gives.items()):
        was = float(ctx.get(entity, name) or 0.0)
        now = round(min(1.0, max(0.0, was + sign * delta)), 6)
        ctx.set(entity, name, now)
        moved[name] = round(now - was, 6)
    return moved


class Marks(System):
    """A year's changes (see the module doc)."""

    name, cadence = "marks.change", "yearly"
    priority = 7  # (after the year's work, deeds and ambitions)
    reads = stocks.READS | frozenset({"ids:*", "acquired", "fame", "deeds", "skills", "job", "traits", "danger", "status",
                                      "residents"})
    writes = frozenset({"acquired", "traits", "fame", "danger"})
    event_types = (GAINED, LOST)

    def run(self, ctx):
        self.step(ctx, 1)

    def coarse_fallback(self, ctx, years: int) -> None:
        self.step(ctx, years)

    def step(self, ctx, years: int) -> None:
        catalogue = list(ctx.pools.marks.values())
        for kind in sorted({k for m in catalogue for k in m.fits}):
            marks = [m for m in catalogue if kind in m.fits]
            for scope, entities in self.groups(ctx, kind):
                with ctx.scope(scope):
                    for entity in entities(ctx):
                        for mark in marks:
                            self.look(ctx, kind, entity, mark, years)

    def groups(self, ctx, kind):
        """Who to look at, a scope at a time: (scope, entities(ctx)), read inside that scope."""
        if kind == "person":
            return [(s, lambda c, s=s: [p for p in sorted(c.get(s, "residents") or []) if c.status(p) == "active"])
                    for s in ctx.ids("settlement")]
        return [(kind, lambda c: c.ids(kind, "active"))]

    def look(self, ctx, kind, entity, mark, years) -> None:
        have = held(ctx, entity, mark.id)
        if have:
            eased = mark.ebb ** (ctx.today.year - have["since"][1])
            if mark.fades and not met(ctx, entity, mark, HOLD, eased):
                self.lose(ctx, kind, entity, mark, have)
        elif all(held(ctx, entity, p) for p in mark.pre) and met(ctx, entity, mark) \
                and ctx.chance(over(mark.chance, years), f"mark:{mark.id}", owner=entity):
            self.gain(ctx, kind, entity, mark)

    def gain(self, ctx, kind, entity, mark) -> None:
        ev = ctx.emit("mark.gained", {"subject": (entity,)}, purpose=f"mark:{mark.id}", actor=entity,
                      payload={"mark": mark.id, "name": mark.name}, causes=why(ctx, entity, mark))
        moved = _apply(ctx, kind, entity, mark.gives)
        have = list(ctx.get(entity, "acquired") or [])
        ctx.set(entity, "acquired", [*have, {"id": mark.id, "since": ctx.today.to_json(), "event": ev.id, "moved": moved}])

    def lose(self, ctx, kind, entity, mark, have) -> None:
        ctx.emit("mark.lost", {"subject": (entity,)}, purpose=f"unmark:{mark.id}", actor=entity,
                 payload={"mark": mark.id, "name": mark.name}, causes=(Cause("event", have["event"]),))
        _apply(ctx, kind, entity, have["moved"], -1)
        ctx.set(entity, "acquired", [m for m in ctx.get(entity, "acquired") or [] if m["id"] != mark.id])
