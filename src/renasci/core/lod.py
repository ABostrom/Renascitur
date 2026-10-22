"""Level of detail: how finely time and people are simulated.

**Time.** A `ResolutionPolicy` says, for any date, whether the world runs `fine` (every system on
its cadence) or `coarse` (big steps, for quiet centuries). Focus windows are always fine. S1 ships
the interface only and runs everything fine; coarse execution and its tuning arrive with the First
Age (M5). The rule that keeps formats stable is fixed now: a coarse step draws its randomness under
its first canonical tick, plus a step ordinal. Systems already declare how they would behave
coarsely: `coarse_ok` (it can integrate over a long step) or `coarse_fallback` (a summary update).

**People.** Masses live as aggregates (numeric columns). `ctx.promote` pulls a named individual
out of an aggregate when someone becomes interesting, with a causal id, and `ctx.demote` fades
them back into it as a dormant record that keeps its history. Both are `lod.*` events. A ruleset
can supply a `conservation(store)` check that lists anything that doesn't add up.
"""

from __future__ import annotations

from dataclasses import dataclass

from renasci.core.calendar import Date, Span
from renasci.core.events import EventType

PROMOTE = EventType("lod.promote", 1, roles={"aggregate": (1, 1), "individual": (1, 1)}, payload={"reason": "str"})
DEMOTE = EventType("lod.demote", 1, roles={"individual": (1, 1), "aggregate": (0, 1)}, payload={"reason": "str"})
EVENT_TYPES = (PROMOTE, DEMOTE)


@dataclass(frozen=True)
class Resolution:
    kind: str
    step: Span | None = None

    def __post_init__(self):
        if self.kind not in ("fine", "coarse"):
            raise ValueError(f"resolution is fine or coarse, got {self.kind!r}")
        if self.kind == "coarse" and (self.step is None or (self.step.years == 0 and self.step.days == 0)):
            raise ValueError("a coarse resolution needs a non-zero step")

    @classmethod
    def fine(cls) -> Resolution:
        return cls("fine")

    @classmethod
    def coarse(cls, step: Span) -> Resolution:
        return cls("coarse", step)


class ResolutionPolicy:
    def __init__(self, default: Resolution | None = None, focus=()):
        self.default = default or Resolution.fine()
        self.focus = tuple(sorted(tuple(w) for w in focus))
        for start, end in self.focus:
            if not (isinstance(start, Date) and isinstance(end, Date)) or end < start:
                raise ValueError(f"a focus window needs start <= end, got {(start, end)}")

    def at(self, date: Date) -> Resolution:
        if any(start <= date <= end for start, end in self.focus):
            return Resolution.fine()
        return self.default

    def ever_coarse(self) -> bool:
        return self.default.kind == "coarse"

    def to_json(self) -> dict:
        step = self.default.step
        return {"default": {"kind": self.default.kind, "step": [step.years, step.days] if step else None},
                "focus": [[a.to_json(), b.to_json()] for a, b in self.focus]}
