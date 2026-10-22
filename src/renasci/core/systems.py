"""Systems and rulesets.

A system is one rule of the world ("people age and die", "the granary fills at harvest"). It
declares what it reads and writes, the event types it emits, and how often it runs. Systems never
call each other: they communicate only through state, events and scheduled activations.

Declared names:
- `reads` / `writes`: record field names, column names, `"status"`, `"ids:<kind>"` (listing a
  kind) and `"new:<kind>"` (creating one).
- `cadence`: daily, monthly, seasonal, yearly, or on_demand (runs only from scheduled follow-ups).

Systems are stateless: everything they know lives in the store, so checkpoints capture it.

A ruleset is the set of systems active in an age, plus parameters.
"""

from __future__ import annotations

from renasci.core.events import EventType
from renasci.core.scheduler import CADENCES


class System:
    name: str = ""
    cadence: str = "on_demand"
    priority: int = 0
    reads: frozenset[str] = frozenset()
    writes: frozenset[str] = frozenset()
    event_types: tuple[EventType, ...] = ()

    def run(self, ctx) -> None:
        """Called on each cadence date."""

    def handle(self, ctx, activation) -> None:
        """Called for a follow-up this system scheduled."""
        raise NotImplementedError(f"{self.name} scheduled a follow-up but has no handle()")

    def check(self) -> None:
        if not isinstance(self.name, str) or not self.name or self.name == "engine":
            raise ValueError(f"system needs a name other than 'engine', got {self.name!r}")
        if self.cadence not in CADENCES:
            raise ValueError(f"{self.name}: cadence must be one of {sorted(CADENCES)}, got {self.cadence!r}")
        if type(self.priority) is not int:
            raise ValueError(f"{self.name}: priority must be an int")
        for label in ("reads", "writes"):
            names = getattr(self, label)
            if not isinstance(names, frozenset) or not all(isinstance(n, str) and n for n in names):
                raise ValueError(f"{self.name}: {label} must be a frozenset of names")
        for t in self.event_types:
            if not isinstance(t, EventType):
                raise ValueError(f"{self.name}: event_types must be EventType objects")


class Ruleset:
    def __init__(self, name: str, version: int, systems: tuple[System, ...], params: dict | None = None):
        if not isinstance(name, str) or not name or type(version) is not int:
            raise ValueError("a ruleset needs a name and an int version")
        by_name: dict[str, System] = {}
        for s in systems:
            s.check()
            if s.name in by_name:
                raise ValueError(f"ruleset {name!r} has two systems named {s.name!r}")
            by_name[s.name] = s
        self.name, self.version = name, version
        self.systems = tuple(by_name[n] for n in sorted(by_name))  # stable order
        self.params = dict(params or {})
        self._by_name = by_name

    def get(self, name: str) -> System | None:
        return self._by_name.get(name)

    def event_types(self) -> list[EventType]:
        return [t for s in self.systems for t in s.event_types]
