"""Pins: canon the run must honour, and the director that honours them.

A pin is a constraint read from canon: an entity exists, an event happens within a window, one pin
comes before another. (Lineage, succession and goal pins parse, but arrive with S2/S3.)

The director prefers doing nothing. A pin that history meets naturally is only *observed*: no
draws, no writes, no events. That is what makes "promote something that happened, then re-run"
reproduce the same history with zero strain. Only when a pin is threatened does the director act:

- **guard:** a system about to kill someone asks `ctx.guarded(entity)`. While a pin needs that
  entity (an existence pin in its window, or a role in an open event pin), the answer is yes and the
  system writes a near miss instead. The near miss is caused by the pin, and the guard is a recorded
  read, so divergence analysis can explain it;
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
        elif p.kind == "existence" and not p.subject.startswith(("v:", "t:")) and p.window is None:
            result[p.id] = "infeasible"  # a born entity's pin needs a window to be checked against
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
        self.met: dict[str, tuple[Date, int]] = {}  # (date, event sequence): same-day order is kept
        self.seq = 0  # events observed so far
        self.strain: list[dict] = []  # pending history
        self.changes: list[dict] = []  # pending history: pin status changes, attributed to the event that caused them
        self._forcing: str | None = None

    def _log(self, action: str, pin: Pin, date: Date, activation: str = "", **extra) -> dict:
        row = json.loads(canonical({"action": action, "pin": pin.id, "kind": pin.kind, "date": date,
                                    "activation": activation, "event": None, **extra}))
        self.strain.append(row)
        return row

    def _set(self, pin: Pin, status: str, date: Date, event: str | None = None) -> None:
        self.status[pin.id] = status
        self.changes.append({"pin": pin.id, "status": status, "event": event, "date": date.to_json()})

    def _meet(self, pin: Pin, date: Date, status: str, event: str) -> None:
        self._set(pin, status, date, event)
        self.met[pin.id] = (date, self.seq)

    # ------------------------------------------------------------ observation (pure)

    def observe(self, event, created=()) -> None:
        """Called for every recorded event, with the entities it created. Marks pins met; never acts."""
        self.seq += 1
        for pin in self.pins:  # born entities: met by their creating event, if it falls inside the window
            if pin.kind == "existence" and self.status.get(pin.id) == "open" and pin.subject in created:
                if pin.covers(event.date):
                    self._meet(pin, event.date, "satisfied", event.id)
                else:
                    self._set(pin, "violated", event.date, event.id)
                    self._log("violated", pin, event.date, reason="created outside the window")
        for pin in self.pins:  # each event satisfies at most one event pin
            if pin.kind != "event" or self.status.get(pin.id) != "open" or not pin.covers(event.date):
                continue
            if event.type != pin.payload["type"]:
                continue
            wanted = pin.payload.get("roles", {})
            if all(set(m) <= set(event.roles.get(r, ())) for r, m in wanted.items()):
                self._meet(pin, event.date, "forced" if self._forcing == pin.id else "satisfied", event.id)
                break
        self._check_orderings(event.date, event.id)

    def _check_orderings(self, date: Date, event: str | None = None) -> None:
        for o in self.pins:
            if o.kind != "ordering" or self.status.get(o.id) != "open":
                continue
            a, b = o.payload["before"], o.payload["after"]
            if a in self.met and b in self.met:
                if self.met[a] < self.met[b]:
                    self._set(o, "satisfied", date, event)
                else:
                    self._set(o, "violated", date, event)
                    self._log("violated", o, date, reason=f"{a} did not come before {b}")
            elif b in self.met and a not in self.met:
                self._set(o, "violated", date, event)
                self._log("violated", o, date, reason=f"{b} happened before {a}")

    # ------------------------------------------------------------ guard

    def guard_pin(self, entity: str, date: Date) -> Pin | None:
        """The pin that needs `entity` alive today, if any."""
        for pin in self.pins:
            status = self.status.get(pin.id)
            if pin.kind == "existence" and pin.subject == entity and status in ("open", "satisfied") \
                    and pin.covers(date):
                return pin
            if pin.kind == "event" and status == "open" and pin.window and date <= pin.window[1] \
                    and any(entity in members for members in pin.payload.get("roles", {}).values()):
                return pin
        return None

    def log_guard(self, pin: Pin, entity: str, date: Date, activation: str) -> dict:
        return self._log("guard", pin, date, activation, entity=entity)

    # ------------------------------------------------------------ deadlines

    def deadline(self, engine, pin_id: str, ctx_factory) -> None:
        pin = self._by_id[pin_id]
        date = pin.window[1]
        if self.status.get(pin.id) != "open":
            return
        if pin.kind == "existence":
            self._set(pin, "violated", date)
            self._log("violated", pin, date, reason="never came to exist inside the window")
            self._check_orderings(date)
            return
        forcer = engine.ruleset.forcer(pin.payload["type"]) if engine.ruleset else None
        forced, ctx = False, None
        if forcer is not None:
            ctx = ctx_factory(forcer, pin)
            ctx._reads[(f"pin:{pin.id}", "status")] = None  # forcing depends on the pin being unmet
            self._forcing = pin.id
            try:
                forced = bool(forcer.force(ctx, pin)) and self.status.get(pin.id) == "forced"
            finally:
                self._forcing = None
            engine.finish(ctx)
        if forced:
            self._log("force", pin, date, ctx.activation.id)
        else:
            self._set(pin, "violated", date)
            self._log("violated", pin, date, reason="no forcer could construct it")
        self._check_orderings(date)

    # ------------------------------------------------------------ state

    def to_json(self) -> dict:
        return {"status": dict(sorted(self.status.items())), "seq": self.seq,
                "met": {k: [d.to_json(), n] for k, (d, n) in sorted(self.met.items())}}

    def load_json(self, data: dict) -> None:
        self.status = dict(data["status"])
        self.seq = data["seq"]
        self.met = {k: (Date.from_json(d), n) for k, (d, n) in data["met"].items()}
