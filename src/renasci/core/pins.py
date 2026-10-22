"""Pins: canon the run must honour, and the director that honours them.

A pin is a constraint read from canon: an entity exists, an event happens within a window, one pin
comes before another. (Lineage, succession and goal pins parse, but arrive with S2/S3.)

The director prefers doing nothing. A pin that history meets naturally is only *observed*: no
draws, no writes, no events. That is what makes "promote something that happened, then re-run"
reproduce the same history with zero strain. Only when a pin is threatened does the director act:

- **guard:** a system about to kill a pinned entity asks `ctx.guarded(entity)` and writes a near
  miss instead;
- **force:** at an event pin's deadline, the ruleset's `Forcer` for that event type constructs it,
  caused by the pin;
- **violated:** if forcing is impossible, the pin is logged as violated and the run continues.

Every guard, force and violation is logged as canon strain.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from renasci.core.calendar import Date
from renasci.core.canon import canonical
from renasci.core.systems import System

KINDS = ("existence", "event", "ordering", "lineage", "succession", "goal")
SUPPORTED = ("existence", "event", "ordering")


@dataclass(frozen=True)
class Pin:
    id: str
    kind: str
    subject: str | None = None
    window: tuple[Date, Date] | None = None  # inclusive
    payload: dict = field(default_factory=dict)

    def __post_init__(self):
        if not isinstance(self.id, str) or not self.id:
            raise ValueError("a pin needs an id")
        if self.kind not in KINDS:
            raise ValueError(f"pin kind must be one of {KINDS}, got {self.kind!r}")
        if self.window is not None:
            w = tuple(self.window)
            if len(w) != 2 or not all(isinstance(d, Date) for d in w):
                raise ValueError(f"pin window must be (Date, Date), got {self.window!r}")
            object.__setattr__(self, "window", w)
        object.__setattr__(self, "payload", json.loads(canonical(self.payload)))
        if self.kind == "event" and not isinstance(self.payload.get("type"), str):
            raise ValueError(f"event pin {self.id} needs payload.type")
        if self.kind == "existence" and not self.subject:
            raise ValueError(f"existence pin {self.id} needs a subject")
        if self.kind == "ordering" and not ({"before", "after"} <= set(self.payload)):
            raise ValueError(f"ordering pin {self.id} needs payload.before and payload.after")

    def covers(self, date: Date) -> bool:
        return self.window is None or self.window[0] <= date <= self.window[1]

    def to_json(self) -> dict:
        return {"id": self.id, "kind": self.kind, "subject": self.subject,
                "window": [d.to_json() for d in self.window] if self.window else None, "payload": self.payload}

    @classmethod
    def from_json(cls, d: dict) -> Pin:
        window = tuple(Date.from_json(x) for x in d["window"]) if d["window"] else None
        return cls(d["id"], d["kind"], d["subject"], window, d["payload"])


class Forcer(System):
    """Constructs an event of type `handles` with a plausible cause when a pin's deadline arrives."""

    handles: str = ""

    def force(self, ctx, pin: Pin) -> bool:
        raise NotImplementedError


def feasibility(pins, start: Date, end: Date) -> dict[str, str]:
    """Classify each pin as ok, out_of_scope (outside the run), unsupported or infeasible."""
    by_id = {p.id: p for p in pins}
    result: dict[str, str] = {}
    for p in sorted(pins, key=lambda p: p.id):
        if p.kind not in SUPPORTED:
            result[p.id] = "unsupported"
        elif p.window and p.window[0] > p.window[1]:
            result[p.id] = "infeasible"
        elif p.window and (p.window[1] < start or p.window[0] > end):
            result[p.id] = "out_of_scope"
        else:
            result[p.id] = "ok"

    orderings = [p for p in sorted(pins, key=lambda p: p.id) if p.kind == "ordering" and result[p.id] == "ok"]
    edges: dict[str, list[str]] = {}
    for o in orderings:
        a, b = by_id.get(o.payload["before"]), by_id.get(o.payload["after"])
        if a is None or b is None or result.get(a.id) != "ok" or result.get(b.id) != "ok":
            result[o.id] = "infeasible"
        elif a.window and b.window and a.window[0] > b.window[1]:
            result[o.id] = "infeasible"  # a cannot come before b
        else:
            edges.setdefault(a.id, []).append(b.id)

    def reaches(src: str, dst: str) -> bool:
        seen, stack = {src}, [src]
        while stack:
            for nxt in edges.get(stack.pop(), ()):
                if nxt == dst:
                    return True
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        return False

    for o in orderings:
        if result[o.id] == "ok" and reaches(o.payload["after"], o.payload["before"]):
            result[o.id] = "infeasible"  # part of a cycle
    return result


class Director:
    def __init__(self, pins=()):
        self.pins: tuple[Pin, ...] = tuple(sorted(pins, key=lambda p: p.id))
        self._by_id = {p.id: p for p in self.pins}
        self.status: dict[str, str] = {}
        self.met: dict[str, Date] = {}  # when each pin was satisfied or forced
        self.strain: list[dict] = []  # pending history
        self._forcing: str | None = None

    def _log(self, action: str, pin: Pin, date: Date, activation: str = "", **extra) -> None:
        self.strain.append(json.loads(canonical({"action": action, "pin": pin.id, "kind": pin.kind, "date": date,
                                                  "activation": activation, **extra})))

    # ------------------------------------------------------------ observation (pure)

    def observe(self, event) -> None:
        """Called for every recorded event. Marks matching event pins met; never acts."""
        for pin in self.pins:
            if pin.kind != "event" or self.status.get(pin.id) != "open" or not pin.covers(event.date):
                continue
            if event.type != pin.payload["type"]:
                continue
            wanted = pin.payload.get("roles", {})
            if all(set(m) <= set(event.roles.get(r, ())) for r, m in wanted.items()):
                self.status[pin.id] = "forced" if self._forcing == pin.id else "satisfied"
                self.met[pin.id] = event.date
                self._check_orderings(event.date)

    def _check_orderings(self, date: Date) -> None:
        for o in self.pins:
            if o.kind != "ordering" or self.status.get(o.id) != "open":
                continue
            a, b = o.payload["before"], o.payload["after"]
            if a in self.met and b in self.met:
                if self.met[a] < self.met[b]:
                    self.status[o.id] = "satisfied"
                else:
                    self.status[o.id] = "violated"
                    self._log("violated", o, date, reason=f"{a} did not come before {b}")
            elif b in self.met and a not in self.met:
                self.status[o.id] = "violated"
                self._log("violated", o, date, reason=f"{b} happened before {a}")

    # ------------------------------------------------------------ guard

    def guarded(self, entity: str, date: Date, activation: str) -> bool:
        """Whether `entity` must survive today. Logs strain when it says yes."""
        for pin in self.pins:
            if pin.kind == "existence" and pin.subject == entity and self.status.get(pin.id) == "satisfied" \
                    and pin.covers(date):
                self._log("guard", pin, date, activation, entity=entity)
                return True
        return False

    # ------------------------------------------------------------ deadlines

    def deadline(self, engine, pin_id: str, ctx_factory) -> None:
        pin = self._by_id[pin_id]
        date = pin.window[1]
        if pin.kind == "existence":
            if self.status.get(pin.id) == "open":
                ok = engine.store.exists(pin.subject)
                self.status[pin.id] = "satisfied" if ok else "violated"
                if not ok:
                    self._log("violated", pin, date, reason="never came to exist")
            return
        if self.status.get(pin.id) != "open":
            return
        forcer = engine.ruleset.forcer(pin.payload["type"]) if engine.ruleset else None
        forced, ctx = False, None
        if forcer is not None:
            ctx = ctx_factory(forcer, pin)
            self._forcing = pin.id
            try:
                forced = bool(forcer.force(ctx, pin)) and self.status.get(pin.id) == "forced"
            finally:
                self._forcing = None
            engine.hinges.extend(ctx.hinges)
        if forced:
            self._log("force", pin, date, ctx.activation.id)
        else:
            self.status[pin.id] = "violated"
            self._log("violated", pin, date, reason="no forcer could construct it")
        self._check_orderings(date)

    # ------------------------------------------------------------ state

    def to_json(self) -> dict:
        return {"status": dict(sorted(self.status.items())),
                "met": {k: v.to_json() for k, v in sorted(self.met.items())}}

    def load_json(self, data: dict) -> None:
        self.status = dict(data["status"])
        self.met = {k: Date.from_json(v) for k, v in data["met"].items()}
