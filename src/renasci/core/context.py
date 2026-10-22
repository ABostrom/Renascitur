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
from renasci.core.canon import canonical, digest
from renasci.core.choice import match, scored
from renasci.core.events import Cause, Event, Source
from renasci.core.ids import entity_id, event_id
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
        self.hinges: list[dict] = []  # buffered; the engine keeps them only if the activation completes

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
             payload: dict | None = None, causes=(), visibility: str | None = None,
             creates: dict | None = None) -> Event:
        """Record an event and make it the explanation for this activation's following writes.

        `actor` is the entity the event is about (the person who died, the village that harvested).
        The id comes from (system, actor, purpose, today, occurrence, activation), so the same
        cause gives the same id in another run, and skipping one event never renumbers others.
        The activation's own causes are inherited.

        `creates` makes new entities that this event names, e.g. a birth's child:
        `{"child": [("person", {"village": v})]}`. Their ids are causal, `entity_id(event, role, i)`,
        and they are created by this event (each kind needs `new:<kind>` in `writes`).
        """
        if self._engine.strict and type not in {t.name for t in self.system.event_types}:
            raise UndeclaredAccess(f"{self.system.name} emitted {type!r} without declaring it")
        key = (actor, purpose)
        occurrence = self._occurrences.get(key, 0)
        self._occurrences[key] = occurrence + 1
        eid = event_id(self.system.name, actor, purpose, self.today, occurrence, self.activation.id)
        all_causes = tuple(sorted(set(causes) | set(self.activation.causes)))
        roles = {r: tuple(m) for r, m in roles.items()}
        births = []
        for role, specs in sorted((creates or {}).items()):
            if role in roles:
                raise ValueError(f"role {role!r} is both given and created")
            ids = []
            for i, (kind, fields) in enumerate(specs):
                if f"new:{kind}" not in self.system.writes:
                    raise UndeclaredAccess(f"{self.system.name} created a {kind!r} without declaring new:{kind}")
                ids.append(entity_id(eid, role, i))
                births.append((kind, ids[-1], fields))
            roles[role] = tuple(ids)
        event = Event(eid, self.today, type, roles, place, all_causes, payload or {},
                      Source("system", self.system.name), visibility, activation=self.activation.id)
        if births:
            self._engine.registry.validate(event, today=self.today)  # schema first, before any write
            for kind, entity, fields in births:
                self._engine.store.create(kind, entity, fields, self.today, eid, self.activation.id)
        event = self._engine.record(event)
        self._event = event.id
        for h in self.hinges:  # close calls decided before this event are what it turned on
            if h["event"] is None:
                h["event"] = event.id
        return event

    # ------------------------------------------------------------ randomness and follow-ups

    def rng(self, purpose: str, entity: str):
        """A stream owned by `entity` (a person, place or aggregate). Every stream has an owner."""
        tick = self.calendar.canonical_tick(self.today)
        return self._engine.rng.open(self._engine.ordinals, self.system.name, entity, purpose, tick)

    def _draw_key(self, purpose: str, owner: str) -> tuple[int, int]:
        tick = self.calendar.canonical_tick(self.today)
        n = self._engine.ordinals.next(self.system.name, owner, purpose, tick)
        return self._engine.rng.key(self.system.name, owner, purpose, tick, n), n

    def _hinge(self, kind: str, purpose: str, owner: str, occurrence: int, stakes, roles, **fields) -> None:
        h = {"id": "h" + digest([self.activation.id, kind, owner, purpose, occurrence]), "kind": kind,
             "activation": self.activation.id, "date": self.today, "system": self.system.name,
             "owner": owner, "purpose": purpose, "occurrence": occurrence, "stakes": float(stakes),
             "roles": roles or {}, "event": None, **fields}
        self.hinges.append(json.loads(canonical(h)))

    def choose(self, purpose: str, candidates, *, owner: str, weights=None,
               stakes: float | None = None, roles: dict | None = None) -> str | None:
        """Pick one candidate by rendezvous: a loser leaving never changes the winner.

        With `stakes`, a close race (score gap within `engine.hinge_margin`) records a hinge:
        the winner, the runner-up and the gap.
        """
        key, n = self._draw_key(f"choose:{purpose}", owner)
        ranked = scored([key], candidates, weights)
        if not ranked:
            return None
        winner = ranked[0][1]
        if stakes is not None and len(ranked) > 1:
            margin = ranked[1][0] - ranked[0][0]
            if margin <= self._engine.hinge_margin:
                self._hinge("choice", purpose, owner, n, stakes, roles, winner=winner,
                            runner_up=ranked[1][1], margin=margin)
        return winner

    def match(self, purpose: str, seekers: dict, *, owner: str, accept: dict | None = None) -> dict[str, str]:
        """Pair seekers with targets (e.g. a marriage market) without list-order coupling."""
        key, _ = self._draw_key(f"match:{purpose}", owner)
        return match([key], seekers, accept)

    def chance(self, p: float, purpose: str, *, owner: str, stakes: float | None = None,
               roles: dict | None = None) -> bool:
        """True with probability p, after any odds hooks (ripples, the pin director) adjust it.

        With `stakes`, a close call (|u - p| within `engine.hinge_margin`) is recorded as a hinge,
        a source for latch points.
        """
        p_base = p = float(p)
        if not (math.isfinite(p) and 0.0 <= p <= 1.0):
            raise ValueError(f"probability must be in [0, 1], got {p!r}")
        adjusted = []
        for hook in self._engine.odds_hooks:
            p, cause = hook(self, p, purpose, owner)
            p = float(p)
            if not (math.isfinite(p) and 0.0 <= p <= 1.0):
                raise ValueError(f"odds hook returned an invalid probability {p!r}")
            if cause:
                adjusted.append(cause)
        tick = self.calendar.canonical_tick(self.today)
        n = self._engine.ordinals.next(self.system.name, owner, purpose, tick)
        u = float(self._engine.rng.stream(self.system.name, owner, purpose, tick, n).random())
        outcome = u < p
        if stakes is not None and abs(u - p) <= self._engine.hinge_margin:
            self._hinge("chance", purpose, owner, n, stakes, roles, p_base=p_base, p=p,
                        adjusted_by=adjusted, u=u, margin=abs(u - p), outcome=outcome)
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
