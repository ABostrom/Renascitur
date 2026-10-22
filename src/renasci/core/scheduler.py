"""The scheduler: a queue of activations in one total order.

Order is `(date, priority, entity, purpose, system, hash)`, where the hash covers the payload and
causes. Insertion order never matters, and two identical activations are a bug. A push must sort
strictly after the last activation popped, so nothing can jump in ahead of what already ran: the
order never depends on when something was scheduled.
"""

from __future__ import annotations

import heapq
import json
from dataclasses import dataclass, field

from renasci.core.calendar import AgeBoundaryError, Calendar, Date
from renasci.core.canon import canonical, digest
from renasci.core.events import Cause

CADENCES = {"daily": "day", "monthly": "month", "seasonal": "season", "yearly": "year", "on_demand": None}
FORMAT = 1


def next_due(calendar: Calendar, date: Date, cadence: str) -> Date | None:
    """The next date a system with `cadence` runs after `date`.

    None for `on_demand` systems, and past the end of the age.
    """
    if cadence not in CADENCES:
        raise ValueError(f"cadence must be one of {sorted(CADENCES)}, got {cadence!r}")
    unit = CADENCES[cadence]
    if unit is None:
        return None
    try:
        return calendar.start_of_next(date, unit)
    except AgeBoundaryError:
        return None


def _name(label: str, value) -> str:
    if not isinstance(value, str) or not value:
        raise TypeError(f"{label} must be a non-empty string, got {value!r}")
    return value


@dataclass(frozen=True)
class Activation:
    date: Date
    priority: int
    entity: str
    purpose: str
    system: str
    payload: dict
    causes: tuple[Cause, ...]
    _hash: str = field(init=False, repr=False, compare=False)

    def __post_init__(self):
        if not isinstance(self.date, Date):
            raise TypeError(f"date must be a Date, got {self.date!r}")
        if type(self.priority) is not int:
            raise TypeError(f"priority must be an int, got {self.priority!r}")
        for label in ("entity", "purpose", "system"):
            _name(label, getattr(self, label))
        for c in self.causes:
            if not isinstance(c, Cause):
                raise TypeError(f"causes must be Cause objects, got {c!r}")
        if len(set(self.causes)) != len(self.causes):
            raise ValueError(f"an activation lists a cause twice: {self.causes}")
        # Frozen copies: later changes to the caller's objects can't move this activation.
        object.__setattr__(self, "payload", json.loads(canonical(self.payload)))
        object.__setattr__(self, "causes", tuple(sorted(self.causes)))
        object.__setattr__(self, "_hash", digest([self.payload, self.causes], size=8))

    def __hash__(self) -> int:
        return hash(self.id)

    @property
    def id(self) -> str:
        """Names this activation; it appears on the deltas it produces."""
        return "a" + digest([self.date, self.priority, self.entity, self.purpose, self.system, self._hash])

    def key(self) -> tuple:
        return (self.date, self.priority, self.entity, self.purpose, self.system, self._hash)

    def to_json(self) -> dict:
        return {"date": self.date.to_json(), "priority": self.priority, "entity": self.entity,
                "purpose": self.purpose, "system": self.system, "payload": self.payload,
                "causes": [c.to_json() for c in self.causes]}

    @classmethod
    def from_json(cls, d: dict) -> Activation:
        return cls(Date.from_json(d["date"]), d["priority"], d["entity"], d["purpose"], d["system"],
                   d["payload"], tuple(Cause(*c) for c in d["causes"]))


class Scheduler:
    def __init__(self):
        self._heap: list[tuple[tuple, Activation]] = []
        self._keys: dict[tuple, None] = {}
        self._last: Activation | None = None  # the last activation popped

    @property
    def now(self) -> Date | None:
        return self._last.date if self._last else None

    def __len__(self) -> int:
        return len(self._heap)

    def push(self, activation: Activation) -> None:
        key = activation.key()
        if self._last is not None and key <= self._last.key():
            raise ValueError(f"cannot schedule {activation.system}/{activation.purpose} at "
                             f"{activation.date}: it sorts before or at the last activation run "
                             f"({self._last.system}/{self._last.purpose} at {self._last.date})")
        if key in self._keys:
            raise ValueError(f"identical activation scheduled twice: {activation}")
        self._keys[key] = None
        heapq.heappush(self._heap, (key, activation))

    def pending(self, predicate) -> list[Activation]:
        """Queued activations matching `predicate`, in order."""
        return [a for _, a in sorted(self._heap, key=lambda item: item[0]) if predicate(a)]

    def remove_where(self, predicate) -> list[Activation]:
        """Remove queued activations matching `predicate`; return them in order."""
        removed = self.pending(predicate)
        if removed:
            gone = {a.key() for a in removed}
            self._heap = [item for item in self._heap if item[0] not in gone]
            heapq.heapify(self._heap)
            for k in sorted(gone):
                del self._keys[k]
        return removed

    def peek(self) -> Activation | None:
        return self._heap[0][1] if self._heap else None

    def pop(self) -> Activation:
        key, activation = heapq.heappop(self._heap)
        del self._keys[key]
        self._last = activation
        return activation

    def pop_due(self, until: Date) -> list[Activation]:
        """Pop every activation dated on or before `until`, in order."""
        out = []
        while self._heap and self._heap[0][1].date <= until:
            out.append(self.pop())
        return out

    def to_json(self) -> dict:
        return {"format": FORMAT,
                "last": self._last.to_json() if self._last else None,
                "queue": [a.to_json() for _, a in sorted(self._heap, key=lambda item: item[0])]}

    @classmethod
    def from_json(cls, data: dict) -> Scheduler:
        if data.get("format") != FORMAT:
            raise ValueError(f"scheduler checkpoint format {data.get('format')!r} is not {FORMAT}; "
                             "engine changed, replay from scenario")
        s = cls()
        s._last = Activation.from_json(data["last"]) if data["last"] else None
        for row in data["queue"]:
            s.push(Activation.from_json(row))  # the guard rejects stale rows
        return s
