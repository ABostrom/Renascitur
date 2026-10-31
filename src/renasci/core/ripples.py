"""Ripples: the author's hand, applied through in-world causes.

A ripple is a recorded, replayable intervention. When it fires, the engine records a *secret*
`ripple.<kind>` event (source: the ripple), and the visible change happens through an in-world
**disguise**: a ruleset-supplied class that writes a fall from a horse, a physician's care, a comet.
Everything the ripple touches descends from it in the cause graph, so the Observatory can show the
author's hand while prose never does.

The kinds:
- **protect** `{"until": [age, year, day]}`: while active, `ctx.guarded(target)` says yes, so a
  system writes a near miss instead of a death (the near miss is caused by the ripple);
- **doom**: the target's `doom` disguise applies at the ripple date;
- **inject**: the `inject` disguise adds an event at the ripple date;
- **favour** `{"by": (0, 1], "until"}` (#114): while active, a chance drawn for the target (owned by
  them, or by a scheme or ambition of theirs) whose purpose is `act:...` is `by` likelier, and one whose
  purpose is `expose:...` is `by` less likely: their schemes go better;
- **luck** `{"until"}` (#114): while active, the target's own draws are re-rolled (their keys salted
  with the ripple): a change of fortune, not a bias (the engine can't know which outcome is lucky);
- **plant** and **structural** (#114): through the ruleset's disguise for the kind (a rumour planted in
  a town's talk; the world changing shape: a pass closes).

favour and luck need no disguise: they change the odds of things that happen anyway, and every draw
they touch is recorded as a read of the ripple (`(owner, "favour")`, `(owner, "luck")`), and the next
event is caused by it, so divergence analysis traces what follows to the ripple.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from renasci.core.calendar import Date
from renasci.core.canon import canonical
from renasci.core.events import EventType
from renasci.core.systems import System

KINDS = ("protect", "doom", "favour", "luck", "inject", "plant", "structural")
SUPPORTED = KINDS
NEEDS_DISGUISE = ("doom", "inject", "plant", "structural")
SPANS = ("protect", "favour", "luck")  # kinds active from their date until params.until
EVENT_TYPES = {k: EventType(f"ripple.{k}", 1, roles={"target": (0, 1)}, payload={"target": "str", "params": "json"},
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

    def check(self) -> None:
        """What each kind needs in its params (a disguise checks the rest of its own)."""
        if self.kind in SPANS and (self.until is None or self.until < self.date):
            raise ValueError(f"{self.kind} ripple {self.id} needs params.until on or after its date")
        if self.kind == "favour":
            by = self.params.get("by")
            if isinstance(by, bool) or not isinstance(by, (int, float)) or not 0 < by <= 1:
                raise ValueError(f"favour ripple {self.id} needs params.by in (0, 1], got {by!r}")
        if self.kind == "plant" and not isinstance(self.params.get("claim"), dict) \
                and not isinstance(self.params.get("object"), dict):
            raise ValueError(f"plant ripple {self.id} needs params.claim (a rumour) or params.object (a thing)")
        if self.kind == "plant" and isinstance(self.params.get("object"), dict):
            o = self.params["object"]
            if not isinstance(o.get("type"), str) or not isinstance(o.get("material"), str):
                raise ValueError(f"plant ripple {self.id}: an object needs a type and a material")
            q = o.get("quality", 0.5)
            if isinstance(q, bool) or not isinstance(q, (int, float)) or not 0 <= q <= 1:
                raise ValueError(f"plant ripple {self.id}: an object's quality must be in [0, 1], got {q!r}")
        share = self.params.get("share", 0.2)
        if self.kind == "plant" and (isinstance(share, bool) or not isinstance(share, (int, float)) or not 0 < share <= 1):
            raise ValueError(f"plant ripple {self.id}: share must be in (0, 1], got {share!r}")
        if self.kind == "structural":
            if "open" in self.params and not isinstance(self.params["open"], bool):
                raise ValueError(f"structural ripple {self.id}: open must be true or false")
            days = self.params.get("days", 1)
            if isinstance(days, bool) or not isinstance(days, int) or days < 1:
                raise ValueError(f"structural ripple {self.id}: days must be a positive whole number")
        if self.kind == "structural" and self.params.get("harvest"):  # (S10 #127: a blight on a region's harvest)
            f = self.params.get("factor")
            if isinstance(f, bool) or not isinstance(f, (int, float)) or not 0 <= f <= 1:
                raise ValueError(f"structural ripple {self.id}: a harvest's factor must be in [0, 1], got {f!r}")
            if "until" in self.params:
                try:
                    until = self.until
                except Exception as err:
                    raise ValueError(f"structural ripple {self.id}: until must be a date, got {self.params['until']!r}") from err
                if until < self.date:
                    raise ValueError(f"structural ripple {self.id}: until is before its date")
        if self.kind == "structural" and not ({"open", "days", "region", "control", "harvest"} & set(self.params)):
            raise ValueError(f"structural ripple {self.id} needs params.open, days, region, control or harvest")
        if self.kind == "structural" and "control" in self.params and self.params["control"] is not None \
                and not isinstance(self.params["control"], str):
            raise ValueError(f"structural ripple {self.id}: control must be a polity id or null")

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
