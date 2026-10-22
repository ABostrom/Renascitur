"""The scheduler: a queue of activations in one total order.

Order is `(date, priority, entity, purpose, system, hash)`, where the hash covers the payload and
causes. Insertion order never matters, and two identical activations are a bug. Nothing may be
scheduled before the last date popped.
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass, field

from renasci.core.calendar import AgeBoundaryError, Calendar, Date
from renasci.core.canon import canonical, digest
from renasci.core.events import Cause

CADENCES = {"daily": "day", "monthly": "month", "seasonal": "season", "yearly": "year"}


def next_due(calendar: Calendar, date: Date, cadence: str) -> Date | None:
    """The next date a system with `cadence` runs after `date`, or None past the end of the age."""
    if cadence not in CADENCES:
        raise ValueError(f"cadence must be one of {sorted(CADENCES)}, got {cadence!r}")
    try:
        return calendar.start_of_next(date, CADENCES[cadence])
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
        canonical(self.payload)  # validates
        object.__setattr__(self, "causes", tuple(sorted(self.causes)))
        object.__setattr__(self, "_hash", digest([self.payload, self.causes], size=8))

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
        self.now: Date | None = None  # date of the last activation popped

    def __len__(self) -> int:
        return len(self._heap)

    def push(self, activation: Activation) -> None:
        if self.now is not None and activation.date < self.now:
            raise ValueError(f"cannot schedule {activation.system}/{activation.purpose} at "
                             f"{activation.date}, before now ({self.now})")
        key = activation.key()
        if key in self._keys:
            raise ValueError(f"identical activation scheduled twice: {activation}")
        self._keys[key] = None
        heapq.heappush(self._heap, (key, activation))

    def peek(self) -> Activation | None:
        return self._heap[0][1] if self._heap else None

    def pop(self) -> Activation:
        key, activation = heapq.heappop(self._heap)
        del self._keys[key]
        self.now = activation.date
        return activation

    def pop_due(self, until: Date) -> list[Activation]:
        """Pop every activation dated on or before `until`, in order."""
        out = []
        while self._heap and self._heap[0][1].date <= until:
            out.append(self.pop())
        return out

    def to_json(self) -> dict:
        return {"now": self.now.to_json() if self.now else None,
                "queue": [a.to_json() for _, a in sorted(self._heap, key=lambda item: item[0])]}

    @classmethod
    def from_json(cls, data: dict) -> Scheduler:
        s = cls()
        for row in data["queue"]:
            s.push(Activation.from_json(row))
        s.now = Date.from_json(data["now"]) if data["now"] else None
        return s
