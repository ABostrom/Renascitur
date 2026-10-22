"""The context a system runs in.

Every read, write, event and random draw goes through `Ctx`, which enforces the system's
declarations (when strict), records what was actually read, and names the event behind every
write.
"""

from __future__ import annotations

from renasci.core.calendar import Span
from renasci.core.events import Cause, Event, Source
from renasci.core.ids import event_id
from renasci.core.scheduler import Activation


class UndeclaredAccess(Exception):
    """A system read or wrote something it did not declare."""


class Ctx:
    def __init__(self, engine, system, activation: Activation):
        self._engine = engine
        self.system = system
        self.activation = activation
        self.today = activation.date
        self.calendar = engine.calendar
        self.params = engine.ruleset.params
        self._reads: dict[tuple[str, str], None] = {}
        self._event: str | None = None  # the event that writes are attributed to

    # ------------------------------------------------------------ declarations

    def _may_read(self, name: str) -> None:
        if self._engine.strict and name not in self.system.reads:
            raise UndeclaredAccess(f"{self.system.name} read {name!r} without declaring it")

    def _may_write(self, name: str) -> str:
        if name not in self.system.writes:
            raise UndeclaredAccess(f"{self.system.name} wrote {name!r} without declaring it")
        if self._event is None:
            raise ValueError(f"{self.system.name} wrote {name!r} before emitting an event to explain it")
        return self._event

    def recorded_reads(self) -> list[list[str]]:
        return [list(k) for k in sorted(self._reads)]

    # ------------------------------------------------------------ reads

    def get(self, entity: str, field: str, default=None):
        self._may_read(field)
        self._reads[(entity, field)] = None
        return self._engine.store.get(entity, field, default)

    def status(self, entity: str) -> str:
        self._may_read("status")
        self._reads[(entity, "status")] = None
        return self._engine.store.status(entity)

    def ids(self, kind: str, status: str | None = None) -> list[str]:
        self._may_read(f"ids:{kind}")
        self._reads[(f"${kind}", "ids")] = None
        return self._engine.store.ids(kind, status)

    def read_column(self, name: str, ids):
        self._may_read(name)
        ids = list(ids)
        for i in ids:
            self._reads[(i, name)] = None
        return self._engine.store.read_column(name, ids)

    # ------------------------------------------------------------ writes

    def set(self, entity: str, field: str, value) -> None:
        event = self._may_write(field)
        self._engine.store.set(entity, field, value, self.today, event)

    def set_status(self, entity: str, status: str) -> None:
        event = self._may_write("status")
        self._engine.store.set_status(entity, status, self.today, event)

    def create(self, kind: str, entity: str, fields: dict) -> None:
        event = self._may_write(f"new:{kind}")
        self._engine.store.create(kind, entity, fields, self.today, event)

    def write_column(self, name: str, ids, values) -> None:
        event = self._may_write(name)
        self._engine.store.write_column(name, ids, values, self.today, event, activation=self.activation.id)

    # ------------------------------------------------------------ events

    def emit(self, type: str, roles: dict, *, purpose: str, actor: str | None = None, place: str | None = None,
             payload: dict | None = None, causes=(), visibility: str | None = None) -> Event:
        """Record an event and make it the explanation for this activation's following writes.

        The activation's own causes are inherited. The id comes from (system, actor, purpose, today,
        occurrence), so the same cause gives the same id in another run.
        """
        if self._engine.strict and type not in {t.name for t in self.system.event_types}:
            raise UndeclaredAccess(f"{self.system.name} emitted {type!r} without declaring it")
        actor = actor or self.activation.entity
        occurrence = self._engine.next_event_occurrence(self.system.name, actor, purpose)
        eid = event_id(self.system.name, actor, purpose, self.today, occurrence)
        all_causes = tuple(sorted(set(causes) | set(self.activation.causes)))
        event = Event(eid, self.today, type, roles, place, all_causes, payload or {},
                      Source("system", self.system.name), visibility)
        event = self._engine.record(event)
        self._event = event.id
        return event

    # ------------------------------------------------------------ randomness and follow-ups

    def rng(self, purpose: str, entity: str):
        """A stream owned by `entity` (a person, place or aggregate). Every stream has an owner."""
        tick = self.calendar.canonical_tick(self.today)
        return self._engine.rng.open(self._engine.ordinals, self.system.name, entity, purpose, tick)

    def schedule(self, after: Span, purpose: str, *, entity: str | None = None, payload: dict | None = None,
                 priority: int | None = None) -> Activation:
        """Schedule a follow-up for this system, caused by the last event emitted here."""
        causes = (Cause("event", self._event),) if self._event else self.activation.causes
        activation = Activation(
            self.calendar.add(self.today, after),
            self.system.priority if priority is None else priority,
            entity or self.activation.entity, purpose, self.system.name, payload or {}, causes,
        )
        self._engine.scheduler.push(activation)
        return activation
