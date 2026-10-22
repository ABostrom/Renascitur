"""The context a system runs in.

Every read, write, event and random draw goes through `Ctx`, which enforces the system's
declarations (when strict), records what was actually read, and stamps every write and event with
the event that explains it and the activation that made it.

Recorded reads are `(entity, field)` pairs. Listing a kind records each entity's `status` it looked
at plus the membership key `("$<kind>", "ids")`, which divergence analysis treats as written
whenever an entity of that kind is created.
"""

from __future__ import annotations

import functools
import json
import math
from contextlib import contextmanager

from renasci.core.calendar import Span
from renasci.core.canon import canonical, digest
from renasci.core.choice import match, scored
from renasci.core.events import Cause, Event, Source
from renasci.core.ids import entity_id, event_id
from renasci.core.scheduler import Activation


@functools.lru_cache(maxsize=1 << 16)
def declared(name: str, names: frozenset) -> bool:
    """Is `name` in a read or write set? A declaration ending in `*` covers a prefix: `"allele:*"`
    covers every allele column, whose names come from the world's genome catalogue. (Memoized:
    systems ask the same questions every activation.)"""
    return name in names or any(d.endswith("*") and name.startswith(d[:-1]) for d in names)


def reads_digest(reads: list) -> str:
    """One digest of a scope's sorted [entity, field, value digest] reads. A full row and a
    digest-only row of the same reads give the same value, so the two forms compare."""
    return digest(reads, size=16)


class UndeclaredAccess(Exception):
    """A system read or wrote something it did not declare."""


class _WithNewborns:
    """A read-only view of the store in which entities about to be created already exist."""

    def __init__(self, store, newborns: set[str]):
        self._store, self._new = store, newborns

    def exists(self, entity: str) -> bool:
        return entity in self._new or self._store.exists(entity)

    def status(self, entity: str) -> str:
        return "active" if entity in self._new else self._store.status(entity)


class Ctx:
    def __init__(self, engine, system, activation: Activation):
        self._engine = engine
        self.system = system
        self.activation = activation
        self.today = activation.date
        self.calendar = engine.calendar
        self.params = json.loads(canonical(engine.ruleset.params))  # a private copy
        self._reads: dict[tuple[str, str], None] = {}  # unscoped: inform everything this activation does
        self._scope: str | None = None
        self._scoped: dict[str, dict[tuple[str, str], None]] = {}
        self._events: dict[str | None, list[str]] = {None: []}
        self._event: str | None = None  # the event that writes are attributed to
        self._occurrences: dict[tuple[str, str], int] = {}  # per (actor, purpose), this activation only
        self.hinges: list[dict] = []  # buffered; the engine keeps them only if the activation completes
        self._series: list[dict] = []  # buffered likewise
        self._pin_causes: list = []  # pins that guarded someone here; the next event is caused by them
        self._guard_rows: list[dict] = []

    # ------------------------------------------------------------ declarations

    def _may_read(self, name: str) -> None:
        if self._engine.strict and not declared(name, self.system.reads):
            raise UndeclaredAccess(f"{self.system.name} read {name!r} without declaring it")

    def _may_write(self, name: str) -> str:
        if not declared(name, self.system.writes):
            raise UndeclaredAccess(f"{self.system.name} wrote {name!r} without declaring it")
        if self._event is None:
            raise ValueError(f"{self.system.name} wrote {name!r} before emitting an event to explain it")
        return self._event

    def _note(self, key: tuple[str, str], value) -> None:
        """Record a read and a digest of the value seen (the first time, i.e. before own writes)."""
        target = self._reads if self._scope is None else self._scoped[self._scope]
        if key not in target:
            target[key] = digest(value)

    @contextmanager
    def scope(self, key: str):
        """Attribute the reads and events inside to `key` (one village, one valley...).

        Batch systems handle many independent units in one activation. Scoping keeps a change in one
        unit from tainting every other unit's events in divergence analysis.
        """
        if self._scope is not None:
            raise ValueError("scopes do not nest")
        if not isinstance(key, str) or not key:
            raise ValueError("a scope needs a non-empty string key")
        self._scope = key
        self._scoped.setdefault(key, {})
        self._events.setdefault(key, [])
        self._event, self._pin_causes, self._guard_rows = None, [], []  # nothing carries across scopes
        try:
            yield
        finally:
            self._scope = None
            self._event, self._pin_causes, self._guard_rows = None, [], []

    def read_rows(self, full: bool = True) -> list[dict]:
        """One row per scope (None = unscoped): what was read, and which events it informed.

        `full` keeps every read (entity, field, digest of the value seen). Otherwise a row keeps one
        digest of them all (`reads_digest`) and their count, which is enough to tell whether a scope
        saw different inputs, at a fraction of the size (#151)."""
        rows = []
        sources = ([(None, self._reads)] if (self._reads or self._events[None]) else []) + \
            [(key, self._scoped[key]) for key in sorted(self._scoped)]
        for key, seen in sources:
            reads = [[*k, v] for k, v in sorted(seen.items())]
            row = {"activation": self.activation.id, "scope": key, "events": list(self._events[key])}
            if full:
                row["reads"] = reads
            else:
                row["digest"], row["n"] = reads_digest(reads), len(reads)
            rows.append(row)
        return rows

    def recorded_reads(self) -> list[list[str]]:
        """All reads, scoped or not."""
        keys = set(self._reads)
        for scoped in self._scoped.values():
            keys |= set(scoped)
        return [list(k) for k in sorted(keys)]

    # ------------------------------------------------------------ reads

    def get(self, entity: str, field: str, default=None):
        self._may_read(field)
        value = self._engine.store.get(entity, field, default)
        self._note((entity, field), value)
        return value

    def status(self, entity: str) -> str:
        self._may_read("status")
        value = self._engine.store.status(entity)
        self._note((entity, "status"), value)
        return value

    def exists(self, entity: str) -> bool:
        """Whether `entity` exists. Recorded as a read of its status (creation writes status)."""
        store = self._engine.store
        self._note((entity, "status"), store.status(entity) if store.exists(entity) else None)
        return store.exists(entity)

    def kind(self, entity: str) -> str:
        self._note((entity, "status"), self._engine.store.status(entity))
        return self._engine.store.kind(entity)

    def ids(self, kind: str, status: str | None = None) -> list[str]:
        self._may_read(f"ids:{kind}")
        store = self._engine.store
        everyone = store.ids(kind)
        self._note((f"${kind}", "ids"), everyone)
        if status is not None:
            for entity in everyone:  # filtering looked at every status
                self._note((entity, "status"), store.status(entity))
        return store.ids(kind, status)

    def read_columns(self, entity: str, names) -> dict[str, int | float]:
        """Several columns of one entity (an aggregate's whole state) as plain numbers. Recorded as
        one read, `(entity, "columns:<digest of the names>")`, whose value is the digest of them all."""
        names = list(names)
        for name in names:
            self._may_read(name)
        store = self._engine.store
        values = {name: store.read_column(name, [entity])[0].item() for name in names}
        self._note((entity, f"columns:{digest(names)}"), [values[n] for n in names])
        return values

    def read_column(self, name: str, ids):
        self._may_read(name)
        ids = list(ids)
        values = self._engine.store.read_column(name, ids)
        for i, v in zip(ids, values):
            self._note((i, name), v)
        return values

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

    def series(self, entity: str, values: dict) -> None:
        """Log numbers about `entity` today (an aggregate's counts) to the `timeseries` table. Not
        state and not an event: a record for charts. Kept only if the activation completes."""
        self._series.append(json.loads(canonical({"date": self.today, "system": self.system.name, "entity": entity,
                                                  "values": values, "activation": self.activation.id})))

    def write_columns(self, entity: str, values: dict) -> None:
        """Several columns of one entity in one change (an aggregate's step): one bulk delta."""
        if not values:
            raise ValueError("write_columns needs at least one column")
        event = [self._may_write(name) for name in sorted(values)][-1]  # checks every column; one event
        self._engine.store.write_columns(entity, values, self.today, event, activation=self.activation.id)

    # ------------------------------------------------------------ events

    def peek_event_id(self, actor: str, purpose: str) -> str:
        """The id the next `emit(..., actor=actor, purpose=purpose)` in this activation will get.

        For fields that must name their own creating event (a mutated allele's origin is its birth),
        so the entity is created right the first time."""
        occurrence = self._occurrences.get((actor, purpose), 0)
        return event_id(self.system.name, actor, purpose, self.today, occurrence, self.activation.id)

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
        all_causes = tuple(sorted(set(causes) | set(self.activation.causes) | set(self._pin_causes)))
        self._pin_causes = []
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
            # Validate everything, with the newborns treated as existing, before any write.
            store = self._engine.store
            births = [(kind, entity, json.loads(canonical(fields))) for kind, entity, fields in births]
            for _, entity, _ in births:
                if store.exists(entity):
                    raise ValueError(f"entity {entity!r} already exists")
            self._engine.registry.validate(event, store=_WithNewborns(store, {b[1] for b in births}),
                                           today=self.today)
            for kind, entity, fields in births:
                store.create(kind, entity, fields, self.today, eid, self.activation.id)
        event = self._engine.record(event, created=[b[1] for b in births], scope=self._scope)
        self._event = event.id
        self._events[self._scope].append(event.id)
        for row in self._guard_rows:
            row["event"] = event.id
        self._guard_rows = []
        for h in self.hinges:  # close calls decided before this event are what it turned on
            if h["event"] is None:
                h["event"] = event.id
        return event

    # ------------------------------------------------------------ level of detail

    def _check_writes(self, *names: str) -> None:
        for name in names:
            if not declared(name, self.system.writes):
                raise UndeclaredAccess(f"{self.system.name} wrote {name!r} without declaring it")

    def _take(self, aggregate: str, column: str | None, columns: dict | None) -> dict[str, int]:
        if column is not None and columns is not None:
            raise ValueError("give column or columns, not both")
        amounts = {column: 1} if column is not None else dict(columns or {})
        for name, n in sorted(amounts.items()):
            if isinstance(n, bool) or not isinstance(n, int) or n < 0:
                raise ValueError(f"{name}: the amount must be a non-negative int, got {n!r}")
        return amounts

    def promote(self, aggregate: str, kind: str, fields: dict, *, reason: str, column: str | None = None,
                columns: dict | None = None, place: str | None = None, causes=()) -> str:
        """Pull a named individual out of `aggregate`.

        `column` drops that count by one; `columns` ({column: n}) drops several at once (an age band
        and the allele copies the person carries), written as one change. The id is causal (the
        promote event, role, ordinal); `place` and `causes` say where and why. Every declaration and
        count is checked before anything changes.
        """
        take = self._take(aggregate, column, columns)
        self._check_writes(f"new:{kind}", *sorted(take))
        counts = {name: self.read_column(name, [aggregate])[0] for name in sorted(take)}
        for name in sorted(take):
            if counts[name] < take[name]:
                raise ValueError(f"cannot promote from {aggregate}: {name} is {counts[name]}, needs {take[name]}")
        event = self.emit("lod.promote", {"aggregate": (aggregate,)}, purpose=f"promote:{reason}", actor=aggregate,
                          place=place, payload={"reason": reason}, causes=causes,
                          creates={"individual": [(kind, fields)]})
        if take:
            self.write_columns(aggregate, {name: counts[name] - take[name] for name in take})
        return event.roles["individual"][0]

    def demote(self, entity: str, *, reason: str, column: str | None = None, aggregate: str | None = None,
               columns: dict | None = None, causes=()) -> None:
        """Fade an individual back into the mass: a dormant record that keeps its history.

        `column` adds one back to that count; `columns` ({column: n}) adds several, as one change."""
        give = self._take(aggregate, column, columns)
        if bool(give) != (aggregate is not None):
            raise ValueError("demote needs columns and aggregate together (or neither)")
        self._check_writes("status", *sorted(give))
        if self.status(entity) != "active":
            raise ValueError(f"cannot demote {entity}: it is {self._engine.store.status(entity)}")
        counts = {name: self.read_column(name, [aggregate])[0] for name in sorted(give)}
        roles = {"individual": (entity,)} | ({"aggregate": (aggregate,)} if aggregate else {})
        self.emit("lod.demote", roles, purpose=f"demote:{reason}", actor=entity, payload={"reason": reason},
                  causes=causes)
        self.set_status(entity, "dormant")
        if give:
            self.write_columns(aggregate, {name: counts[name] + give[name] for name in give})

    # ------------------------------------------------------------ pins

    def _protector(self, entity: str):
        pin = self._engine.director.guard_pin(entity, self.today)
        ripple = None if pin is not None else self._engine.protection(entity, self.today)
        return pin, ripple

    def resolve(self, entity: str) -> str:
        """The sim entity a canon id was bound to (by a birth pin), or the id itself. A recorded read."""
        bound = self._engine.director.resolve(entity)
        self._note((entity, "binding"), bound)
        return bound

    def protected(self, entity: str) -> bool:
        """Is `entity` protected (by a pin or a ripple) today? Recorded as the same read as `guarded`,
        but nothing is guarded: no cause for the next event, no guard logged. For decisions that just
        leave a protected person alone (don't demote them), rather than saving them from death."""
        pin, ripple = self._protector(entity)
        self._note((entity, "guard"), f"pin:{pin.id}" if pin else f"ripple:{ripple.id}" if ripple else None)
        return pin is not None or ripple is not None

    def guarded(self, entity: str) -> bool:
        """Ask before a fatal outcome: True means canon needs `entity` alive, so write a near miss.

        Always recorded as a read of `(entity, "guard")` whose value names the protecting pin or
        ripple (or none), so a run with a protect ripple and a run without one differ in that value.
        The next event emitted here is caused by the protector.
        """
        pin, ripple = self._protector(entity)
        if pin is None:
            self._note((entity, "guard"), f"ripple:{ripple.id}" if ripple else None)
            if ripple is None:
                return False
            self._pin_causes.append(Cause("ripple", ripple.id))
            self._guard_rows.append(self._engine.log_ripple(ripple, "guard", True, self.activation.id,
                                                            entity=entity))
            return True
        self._note((entity, "guard"), f"pin:{pin.id}")
        self._pin_causes.append(Cause("pin", pin.id))
        self._guard_rows.append(self._engine.director.log_guard(pin, entity, self.today, self.activation.id))
        return True

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
        parent = self.activation.id if self._scope is None else f"{self.activation.id}#{self._scope}"
        causes = tuple(base) + (Cause("activation", parent),)
        activation = Activation(
            self.calendar.add(self.today, after),
            self.system.priority if priority is None else priority,
            entity or self.activation.entity, purpose, self.system.name, payload or {}, causes,
        )
        self._engine.scheduler.push(activation)
        return activation
