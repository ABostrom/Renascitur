"""Ripples: the author's hand, applied through in-world causes.

A ripple is a recorded, replayable intervention. When it fires, the engine records a *secret*
`ripple.<kind>` event (source: the ripple), and the visible change happens through an in-world
**disguise**: a ruleset-supplied class that writes a fall from a horse, a physician's care, a comet.
Everything the ripple touches descends from it in the cause graph, so the Observatory can show the
author's hand while prose never does.

S1 supports:
- **protect** `{"until": [age, year, day]}`: while active, `ctx.guarded(target)` says yes, so a
  system writes a near miss instead of a death (the near miss is caused by the ripple);
- **doom**: the target's `doom` disguise applies at the ripple date;
- **inject**: the `inject` disguise adds an event at the ripple date.

favour, luck, plant and structural arrive with #114 (M3).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from renasci.core.calendar import Date
from renasci.core.canon import canonical
from renasci.core.events import EventType
from renasci.core.systems import System

KINDS = ("protect", "doom", "favour", "luck", "inject", "plant", "structural")
SUPPORTED = ("protect", "doom", "inject")
NEEDS_DISGUISE = ("doom", "inject")
EVENT_TYPES = {k: EventType(f"ripple.{k}", 1, roles={"target": (0, 1)}, payload={"params": "json"},
                            visibility="secret", dead_roles=("target",)) for k in KINDS}


@dataclass(frozen=True)
class Ripple:
    id: str
    kind: str
    date: Date
    target: str
    params: dict = field(default_factory=dict)

    def __post_init__(self):
        for label in ("id", "target"):
            if not isinstance(getattr(self, label), str) or not getattr(self, label):
                raise ValueError(f"a ripple needs a {label}")
        if self.kind not in KINDS:
            raise ValueError(f"ripple kind must be one of {KINDS}, got {self.kind!r}")
        if not isinstance(self.date, Date):
            raise ValueError(f"ripple date must be a Date, got {self.date!r}")
        object.__setattr__(self, "params", json.loads(canonical(self.params)))

    @property
    def until(self) -> Date | None:
        u = self.params.get("until")
        return Date.from_json(u) if u is not None else None

    def to_json(self) -> dict:
        return {"id": self.id, "kind": self.kind, "date": self.date.to_json(), "target": self.target,
                "params": self.params}

    @classmethod
    def from_json(cls, d: dict) -> Ripple:
        return cls(d["id"], d["kind"], Date.from_json(d["date"]), d["target"], d["params"])


class Disguise(System):
    """The in-world face of a ripple kind: `apply` writes what the world sees and returns success."""

    handles: str = ""

    def apply(self, ctx, ripple: Ripple) -> bool:
        raise NotImplementedError
