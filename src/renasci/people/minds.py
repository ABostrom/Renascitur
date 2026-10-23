"""Minds (S7 spec §7): what a notable carries inside, as of any date.

- **`wound`** `{"kind", "event", "since"}` or null. One at a time: a fresher wound replaces it, and it
  heals after `wound_years` (default 10). The kinds:
  - `grief`: a parent, spouse or child killed by a known hand (`life.die`);
  - `betrayal`: a tie turned enemy by an exposed plot (`schemes`);
  - `terror`: one's own near miss (`people.life`);
  - `shame`: one's own plot exposed, or being `Shame`d.
- **`need`**: a phrase for the wound's kind (the ruleset param `needs`, world data; `NEEDS` by default),
  or null.
- **`wants`**: the active ambitions' texts, in ambition order.

Wounds are struck, with their need, where they happen (`wound`). `people.minds` (yearly, per settlement
scope, after schemes) heals old wounds and rewrites `need` and `wants`, **only on change**, under one
`people.minds` event per settlement, so the fields rebuild from `state_deltas` as of any date.
"""

from __future__ import annotations

from renasci.core.events import EventType
from renasci.core.systems import System
from renasci.people.ambitions import classes

WOUNDS = ("betrayal", "grief", "shame", "terror")
NEEDS = {
    "betrayal": "to trust again",
    "grief": "to answer for the dead",
    "shame": "to win back their name",
    "terror": "to feel safe",
}
UPDATE = EventType("people.minds", 1, roles={"settlement": (1, 1)}, payload={"changed": "int"})


def need_of(ctx, kind: str | None) -> str | None:
    return {**NEEDS, **(ctx.params.get("needs") or {})}[kind] if kind else None


def wound(ctx, person: str, kind: str, event: str) -> None:
    """Strike a wound (the fresher one is the one carried), and the need that goes with it."""
    if kind not in WOUNDS:
        raise ValueError(f"unknown wound {kind!r}; known: {WOUNDS}")
    ctx.set(person, "wound", {"kind": kind, "event": event, "since": ctx.today.to_json()})
    need = need_of(ctx, kind)
    if ctx.get(person, "need") != need:
        ctx.set(person, "need", need)


class Minds(System):
    name, cadence = "people.minds", "yearly"
    priority = 8  # after ambitions (6) and schemes (7)
    reads = frozenset({"ids:settlement", "residents", "wound", "need", "wants", "ambitions", "class", "target",
                       "name", "house"})
    writes = frozenset({"wound", "need", "wants"})
    event_types = (UPDATE,)

    def run(self, ctx):
        heal = int(ctx.params.get("wound_years", 10))
        library = classes(ctx)
        for s in ctx.ids("settlement"):
            with ctx.scope(s):
                fresh = {}
                for p in ctx.get(s, "residents"):
                    w = ctx.get(p, "wound")
                    if w and w["since"][1] + heal <= ctx.today.year:
                        w = None
                    wants = [library[ctx.get(a, "class")].text(ctx, p, ctx.get(a, "target"))
                             for a in ctx.get(p, "ambitions") or [] if ctx.get(a, "class") in library]
                    now = {"wound": w, "need": need_of(ctx, w["kind"] if w else None), "wants": wants or None}
                    old = {f: ctx.get(p, f) for f in now}
                    if now != old:
                        fresh[p] = {f: v for f, v in now.items() if v != old[f]}
                if not fresh:
                    continue
                ctx.emit("people.minds", {"settlement": (s,)}, purpose="minds", actor=s, place=s,
                         payload={"changed": len(fresh)})
                for p, changes in sorted(fresh.items()):
                    for f, v in sorted(changes.items()):
                        ctx.set(p, f, v)
