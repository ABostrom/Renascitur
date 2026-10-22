"""Ties (S3 spec §6): non-kin relationships. Kin is derived from parent, children and spouse fields.

A **tie** is a record: `a`, `b` (ordered by id), `kind` (friend, rival, mentor; S7 adds enemy, patron,
lover), `strength` (0-1, in steps of 0.05), `since`, `ended`, and for a mentor `mentor` and `pupil`.
Each person lists their live ties in a sorted `ties` field, so a person's ties as of any date can be
rebuilt from `state_deltas`.

`people.ties` (yearly) runs one `ctx.scope(settlement)` per settlement:

- **Upkeep.** Each live tie is kept once a year, in the scope of its member `a` (always a resident
  somewhere while the tie lives). Living together, it strengthens or weakens by `tie_decay`, a keyed
  draw that leans to strengthening (`tie_keep`, default 0.5); living apart, it weakens by twice that.
  It ends below 0.1, so lifespans vary and strength says how close a tie has stayed.
- **Endings at once:** a death (`life.die`) or a fade into the masses (`population.demote_person`)
  ends that person's ties straight away, through `end_ties`.
- **Forming.** Each adult resident with room for more (`max_ties`) forms a tie with `tie_rate` a
  year: a co-resident chosen by rendezvous, weighted towards similar age and the same house; then the
  kind (mentor only for someone at least 15 years older). New ties start at 0.5.
"""

from __future__ import annotations

import math

from renasci.core.events import EventType
from renasci.core.systems import System
from renasci.people.races import age_years

TIE_FORMED = EventType("people.tie_formed", 1, roles={"a": (1, 1), "b": (1, 1), "tie": (1, 1)},
                       payload={"kind": "str"})
TIE_ENDED = EventType("people.tie_ended", 1, roles={"tie": (1, 1), "a": (1, 1), "b": (1, 1)},
                      payload={"kind": "str", "why": "str"}, dead_roles=("a", "b"))
UPKEEP = EventType("people.ties", 1, roles={"settlement": (1, 1)}, payload={"ties": "int"})
EVENT_TYPES = (TIE_FORMED, TIE_ENDED, UPKEEP)
ADULT = 12


READS = frozenset({"ties", "a", "b", "kind"})
WRITES = frozenset({"ties", "ended"})


def end_ties(ctx, person: str, why: str) -> None:
    """End every live tie of `person` (who has died or faded): both sides stop listing it."""
    for t in ctx.get(person, "ties") or []:
        a, b = ctx.get(t, "a"), ctx.get(t, "b")
        ctx.emit("people.tie_ended", {"tie": (t,), "a": (a,), "b": (b,)}, purpose="tie_ended", actor=t,
                 payload={"kind": ctx.get(t, "kind"), "why": why})
        ctx.set(t, "ended", ctx.today.to_json())
        for p in (a, b):
            ctx.set(p, "ties", [x for x in ctx.get(p, "ties") or [] if x != t])


def quantise(x: float) -> float:
    return round(min(max(x, 0.0), 1.0) * 20) / 20


class Ties(System):
    name, cadence = "people.ties", "yearly"
    reads = frozenset({"ids:settlement", "residents", "ties", "status", "born", "house", "a", "b", "kind",
                       "strength", "ended", "place"})
    writes = frozenset({"ties", "strength", "ended", "new:tie"})
    event_types = EVENT_TYPES

    def run(self, ctx):
        rate = float(ctx.params.get("tie_rate", 0.08))
        decay = float(ctx.params.get("tie_decay", 0.05))
        most = int(ctx.params.get("max_ties", 6))
        for s in ctx.ids("settlement"):
            with ctx.scope(s):
                residents = ctx.get(s, "residents")
                self._upkeep(ctx, s, set(residents), decay)
                self._form(ctx, s, residents, rate, most)

    def _upkeep(self, ctx, settlement: str, here: set, decay: float) -> None:
        changes = []
        for p in sorted(here):
            for t in ctx.get(p, "ties") or []:
                a, b = ctx.get(t, "a"), ctx.get(t, "b")
                if p != a:
                    continue  # kept by a, wherever a lives
                if ctx.get(b, "place") == settlement:
                    up = ctx.chance(float(ctx.params.get("tie_keep", 0.5)), "tie_keep", owner=t)
                    step = decay if up else -decay
                else:
                    step = -2 * decay
                strength = quantise(ctx.get(t, "strength") + step)
                if strength == ctx.get(t, "strength"):
                    continue
                changes.append((t, a, b, strength, "faded" if strength < 0.1 else None))
        if not changes:
            return
        ctx.emit("people.ties", {"settlement": (settlement,)}, purpose="ties", actor=settlement, place=settlement,
                 payload={"ties": len(changes)})
        for t, a, b, strength, why in changes:
            if why is None:
                ctx.set(t, "strength", strength)
                continue
            ctx.emit("people.tie_ended", {"tie": (t,), "a": (a,), "b": (b,)}, purpose="tie_ended", actor=t,
                     place=settlement, payload={"kind": ctx.get(t, "kind"), "why": why})
            ctx.set(t, "ended", ctx.today.to_json())
            for person in (a, b):
                ctx.set(person, "ties", [x for x in ctx.get(person, "ties") or [] if x != t])

    def _form(self, ctx, settlement: str, residents: list, rate: float, most: int) -> None:
        age = {p: age_years(ctx.calendar, ctx.get(p, "born"), ctx.today) for p in residents}
        adults = [p for p in residents if age[p] >= ADULT]
        for p in adults:
            mine = ctx.get(p, "ties") or []
            if len(mine) >= most or not ctx.chance(rate, "tie", owner=p):
                continue
            tied = {ctx.get(t, "a") for t in mine} | {ctx.get(t, "b") for t in mine}
            candidates = [q for q in adults if q != p and q not in tied and len(ctx.get(q, "ties") or []) < most]
            if not candidates:
                continue
            house = ctx.get(p, "house")
            weights = [math.exp(-abs(age[p] - age[q]) / 10.0) * (2.0 if house and ctx.get(q, "house") == house else 1.0)
                       for q in candidates]
            other = ctx.choose("tie", candidates, owner=p, weights=weights)
            elder, younger = (p, other) if age[p] >= age[other] else (other, p)
            kinds = {"friend": 0.6, "rival": 0.25}
            if age[elder] - age[younger] >= 15:
                kinds["mentor"] = 0.3
            names = sorted(kinds)
            kind = names[ctx.rng("tie_kind", p).choice_index([kinds[k] for k in names])]
            a, b = sorted((p, other))
            fields = {"a": a, "b": b, "kind": kind, "strength": 0.5, "since": ctx.today.to_json(), "ended": None}
            if kind == "mentor":
                fields |= {"mentor": elder, "pupil": younger}
            event = ctx.emit("people.tie_formed", {"a": (a,), "b": (b,)}, purpose="tie", actor=p, place=settlement,
                             payload={"kind": kind}, creates={"tie": [("tie", fields)]})
            tie = event.roles["tie"][0]
            for person in (a, b):
                ctx.set(person, "ties", sorted((ctx.get(person, "ties") or []) + [tie]))
