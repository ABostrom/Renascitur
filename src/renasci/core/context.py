"""The context a system runs in.

Every read, write, event and random draw goes through `Ctx`, which enforces the system's
declarations (when strict), records what was actually read, and stamps every write and event with
the event that explains it and the activation that made it.

Recorded reads are `(entity, field)` pairs. Listing a kind records each entity's `status` it looked
at plus the membership key `("$<kind>", "ids")`, which divergence analysis treats as written
whenever an entity of that kind is created.
"""

from __future__ import annotations

import json
import math

from renasci.core.calendar import Span
from renasci.core.canon import canonical
from renasci.core.choice import match, rendezvous
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
        self.params = json.loads(canonical(engine.ruleset.params))  # a private copy
        self._reads: dict[tuple[str, str], None] = {}
        self._event: str | None = None  # the event that writes are attributed to
        self._occurrences: dict[tuple[str, str], int] = {}  # per (actor, purpose), this activation only

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

    def exists(self, entity: str) -> bool:
        """Whether `entity` exists. Recorded as a read of its status (creation writes status)."""
        self._reads[(entity, "status")] = None
        return self._engine.store.exists(entity)

    def kind(self, entity: str) -> str:
        self._reads[(entity, "status")] = None
        return self._engine.store.kind(entity)

    def ids(self, kind: str, status: str | None = None) -> list[str]:
        self._may_read(f"ids:{kind}")
        store = self._engine.store
        self._reads[(f"${kind}", "ids")] = None
        if status is not None:
            for entity in store.ids(kind):  # filtering looked at every status
                self._reads[(entity, "status")] = None
        return store.ids(kind, status)

    def read_column(self, name: str, ids):
        self._may_read(name)
        ids = list(ids)
        for i in ids:
            self._reads[(i, name)] = None
        return self._engine.store.read_column(name, ids)

    # ------------------------------------------------------------ writes

    def set(self, entity: str, field: str, value) -> None:
        event = self._may_write(field)
        self._engine.store.set(entity, field, value, self.today, event, self.activation.id)

    def set_status(self, entity: str, status: str) -> None:
        event = self._may_write("status")
        self._engine.store.set_status(entity, status, self.today, event, self.activation.id)

    def create(self, kind: str, entity: str, fields: dict) -> None:
        event = self._may_write(f"new:{kind}")
        self._engine.store.create(kind, entity, fields, self.today, event, self.activation.id)

    def write_column(self, name: str, ids, values) -> None:
        event = self._may_write(name)
        self._engine.store.write_column(name, ids, values, self.today, event, activation=self.activation.id)

    # ------------------------------------------------------------ events

    def emit(self, type: str, roles: dict, *, purpose: str, actor: str, place: str | None = None,
             payload: dict | None = None, causes=(), visibility: str | None = None) -> Event:
        """Record an event and make it the explanation for this activation's following writes.

        `actor` is the entity the event is about (the person who died, the village that harvested).
        The id comes from (system, actor, purpose, today, occurrence, activation), so the same
        cause gives the same id in another run, and skipping one event never renumbers others.
        The activation's own causes are inherited.
        """
        if self._engine.strict and type not in {t.name for t in self.system.event_types}:
            raise UndeclaredAccess(f"{self.system.name} emitted {type!r} without declaring it")
        key = (actor, purpose)
        occurrence = self._occurrences.get(key, 0)
        self._occurrences[key] = occurrence + 1
        eid = event_id(self.system.name, actor, purpose, self.today, occurrence, self.activation.id)
        all_causes = tuple(sorted(set(causes) | set(self.activation.causes)))
        event = Event(eid, self.today, type, roles, place, all_causes, payload or {},
                      Source("system", self.system.name), visibility, activation=self.activation.id)
        event = self._engine.record(event)
        self._event = event.id
        return event

    # ------------------------------------------------------------ randomness and follow-ups

    def rng(self, purpose: str, entity: str):
        """A stream owned by `entity` (a person, place or aggregate). Every stream has an owner."""
        tick = self.calendar.canonical_tick(self.today)
        return self._engine.rng.open(self._engine.ordinals, self.system.name, entity, purpose, tick)

    def _choice_key(self, purpose: str, owner: str) -> list:
        tick = self.calendar.canonical_tick(self.today)
        n = self._engine.ordinals.next(self.system.name, owner, f"choose:{purpose}", tick)
        return [self._engine.rng.key(self.system.name, owner, f"choose:{purpose}", tick, n)]

    def choose(self, purpose: str, candidates, *, owner: str, weights=None) -> str | None:
        """Pick one candidate by rendezvous: a loser leaving never changes the winner."""
        return rendezvous(self._choice_key(purpose, owner), candidates, weights)

    def match(self, purpose: str, seekers: dict[str, list[str]], *, owner: str) -> dict[str, str]:
        """Pair seekers with targets (e.g. a marriage market) without list-order coupling."""
        return match(self._choice_key(purpose, owner), seekers)

    def chance(self, p: float, purpose: str, *, owner: str, stakes: float | None = None,
               roles: dict | None = None) -> bool:
        """True with probability p. With `stakes`, the draw is recorded as a hinge (a latch-point source)."""
        p = float(p)
        if not (math.isfinite(p) and 0.0 <= p <= 1.0):
            raise ValueError(f"probability must be in [0, 1], got {p!r}")
        u = float(self.rng(purpose, owner).random())
        outcome = u < p
        if stakes is not None:
            self._engine.hinges.append(json.loads(canonical({
                "activation": self.activation.id, "date": self.today, "system": self.system.name,
                "owner": owner, "purpose": purpose, "p": p, "u": u, "margin": abs(u - p),
                "outcome": outcome, "stakes": float(stakes), "roles": roles or {},
            })))
        return outcome

    def schedule(self, after: Span, purpose: str, *, entity: str | None = None, payload: dict | None = None,
                 priority: int | None = None) -> Activation:
        """Schedule a follow-up for this system.

        It is caused by this activation, and by the last event emitted here (or, if none, by this
        activation's own causes), so taint flows to it even when no event was emitted.
        """
        base = (Cause("event", self._event),) if self._event else self.activation.causes
        causes = tuple(base) + (Cause("activation", self.activation.id),)
        activation = Activation(
            self.calendar.add(self.today, after),
            self.system.priority if priority is None else priority,
            entity or self.activation.entity, purpose, self.system.name, payload or {}, causes,
        )
        self._engine.scheduler.push(activation)
        return activation
