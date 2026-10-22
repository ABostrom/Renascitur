"""The engine: owns the world state and runs systems in scheduler order.

Rulesets switch on configured dates. Each switch is an engine activation that runs before
anything else on that day. At a switch:
- a system that left, or changed its cadence or priority, has its queued activations removed
  (listed in `dropped`);
- every cadence system in the new ruleset without a queued cadence run starts one that day. That
  covers new systems, changed ones, and carried ones whose chain ended at an age boundary.
"""

from __future__ import annotations

from renasci import __version__
from renasci.core.calendar import Calendar, Date
from renasci.core.canon import digest
from renasci.core.context import Ctx, UndeclaredAccess
from renasci.core.events import CauseIndex, Event, EventType, Registry, Source
from renasci.core.ids import event_id
from renasci.core.rng import KeyedRng, OrdinalTable, Reshuffle
from renasci.core.scheduler import Activation, Scheduler, next_due
from renasci.core.store import Store
from renasci.core.systems import Ruleset

__all__ = ["Engine", "UndeclaredAccess"]

SWITCH_PRIORITY = -(10**9)
CAST = EventType("engine.cast", 1, roles={"subject": (1, 1)}, payload={"kind": "str"})
CAST_COLUMN = EventType("engine.cast_column", 1, roles={}, payload={"column": "str"})
CHECKPOINT_FORMAT = 1


class Engine:
    def __init__(self, calendar: Calendar, seed: int, rulesets: list[tuple[Date, Ruleset]],
                 strict: bool = True, reshuffles: tuple[Reshuffle, ...] = (), hinge_margin: float = 0.05):
        if not rulesets:
            raise ValueError("an engine needs at least one ruleset")
        dates = [d for d, _ in rulesets]
        if dates != sorted(dates) or len(set(dates)) != len(dates):
            raise ValueError("ruleset start dates must be strictly increasing")
        for d in dates:
            calendar.check(d)

        self.calendar, self.strict = calendar, strict
        self.seed, self.reshuffles = seed, tuple(reshuffles)
        self.rulesets = list(rulesets)
        self.start = dates[0]
        self.store = Store()
        self.registry = Registry()
        self.rng = KeyedRng(seed, reshuffles)
        self.ordinals = OrdinalTable()
        self.scheduler = Scheduler()
        self.causes = CauseIndex()
        self.events: list[Event] = []
        self.reads: list[dict] = []
        self.hinges: list[dict] = []  # close calls with stakes: the source data for latch points
        self.hinge_margin = float(hinge_margin)  # a draw with stakes is a hinge only if it was this close
        self.odds_hooks: list = []  # (ctx, p, purpose, owner) -> (p, cause or None): ripples, director
        self.dropped: list[str] = []
        self.ruleset: Ruleset | None = None
        self.ruleset_index: int | None = None
        self._date: Date | None = None

        self._register(CAST)
        self._register(CAST_COLUMN)
        for _, rs in rulesets:
            for t in rs.event_types():
                self._register(t)
        for i, d in enumerate(dates):
            self.scheduler.push(Activation(d, SWITCH_PRIORITY, "engine", "switch", "engine", {"index": i}, ()))

    def _register(self, t: EventType) -> None:
        try:
            existing = self.registry.get(t.name)
        except ValueError:
            self.registry.register(t)
            return
        if existing != t:
            raise ValueError(f"two different event types are both named {t.name!r}")

    # ------------------------------------------------------------ setup

    def cast(self, kind: str, entity: str, fields: dict) -> Event:
        """Place an entity into the world at the start date, before anything runs."""
        if self._date is not None:
            raise ValueError("casting happens before the run starts")
        eid = event_id("engine", entity, "cast", self.start, 0)
        self.store.create(kind, entity, fields, self.start, eid)
        return self.record(Event(eid, self.start, CAST.name, {"subject": (entity,)}, None, (),
                                 {"kind": kind}, Source("scenario", "cast")))

    def cast_column(self, name: str, dtype: str, ids, values) -> Event:
        """Create a numeric column (aggregate state) with starting values, before anything runs."""
        if self._date is not None:
            raise ValueError("casting happens before the run starts")
        eid = event_id("engine", f"column:{name}", "cast", self.start, 0)
        self.store.add_column(name, dtype)
        self.store.write_column(name, ids, values, self.start, eid)
        return self.record(Event(eid, self.start, CAST_COLUMN.name, {}, None, (), {"column": name},
                                 Source("scenario", "cast")))

    # ------------------------------------------------------------ used by Ctx

    def record(self, event: Event) -> Event:
        event = self.registry.validate(event, store=self.store, today=self._date or self.start)
        self.causes.add(event)
        self.events.append(event)
        return event

    def schedule(self, system: str, date: Date, purpose: str, *, entity: str, payload: dict | None = None,
                 priority: int | None = None, causes=()) -> Activation:
        """Schedule an activation of any system (pins, ripples and scenarios start on_demand systems)."""
        rs_system = self.ruleset.get(system) if self.ruleset else None
        if priority is None:
            priority = rs_system.priority if rs_system else 0
        activation = Activation(date, priority, entity, purpose, system, payload or {}, tuple(causes))
        self.scheduler.push(activation)
        return activation

    def pending(self) -> dict[str, list[dict]]:
        """Pending history as run-folder rows. Call `clear_pending` once they are safely written."""
        events = self.events
        return {
            "events": [ev.to_json() for ev in events],
            "causes": [{"event": ev.id, "kind": c.kind, "ref": c.ref} for ev in events for c in ev.causes],
            "participants": [{"event": ev.id, "role": role, "entity": entity}
                             for ev in events for role, members in ev.roles.items() for entity in members],
            "entities": [dict(row) for row in self.store.created],
            "state_deltas": [d.to_json() for d in self.store.deltas],
            "bulk_deltas": [d.to_json() for d in self.store.bulk_deltas],
            "reads": list(self.reads),
            "hinges": list(self.hinges),
            "dropped": [{"activation": a} for a in self.dropped],
        }

    def clear_pending(self) -> None:
        """Forget history already written. State (store, cause index, queue) stays."""
        self.events, self.reads, self.hinges, self.dropped = [], [], [], []
        self.store.drain()

    # ------------------------------------------------------------ running

    def run(self, until: Date) -> None:
        """Run every activation dated on or before `until`."""
        self._run(lambda d: d <= until)

    def run_before(self, date: Date) -> None:
        """Run every activation dated before `date`: the position a checkpoint at `date` is taken."""
        self._run(lambda d: d < date)

    def _run(self, due) -> None:
        while (nxt := self.scheduler.peek()) is not None and due(nxt.date):
            activation = self.scheduler.pop()
            self._advance(activation.date)
            if activation.system == "engine":
                self._switch(activation)
            else:
                self._dispatch(activation)

    def _advance(self, date: Date) -> None:
        if date != self._date:
            self._date = date
            self.ordinals.close_before(self.calendar.canonical_tick(date))

    def _switch(self, activation: Activation) -> None:
        old = self.ruleset
        self.ruleset_index = activation.payload["index"]
        self.ruleset = new = self.rulesets[self.ruleset_index][1]

        def unchanged(name: str) -> bool:
            a, b = old.get(name) if old else None, new.get(name)
            return a is not None and b is not None and (a.cadence, a.priority) == (b.cadence, b.priority)

        removed = self.scheduler.remove_where(lambda a: a.system != "engine" and not unchanged(a.system))
        self.dropped.extend(a.id for a in removed)
        for system in new.systems:
            if system.cadence == "on_demand":
                continue
            queued = self.scheduler.pending(lambda a, n=system.name: a.system == n and a.purpose == "cadence")
            if not queued:
                self.scheduler.push(Activation(activation.date, system.priority, system.name, "cadence",
                                               system.name, {}, ()))

    def _dispatch(self, activation: Activation) -> None:
        system = self.ruleset.get(activation.system)
        if system is None:
            self.dropped.append(activation.id)
            return
        ctx = Ctx(self, system, activation)
        if activation.purpose == "cadence":
            system.run(ctx)
            due = next_due(self.calendar, activation.date, system.cadence)
            if due is not None:
                self.scheduler.push(Activation(due, system.priority, system.name, "cadence", system.name, {}, ()))
        else:
            system.handle(ctx, activation)
        self.hinges.extend(ctx.hinges)
        reads = ctx.recorded_reads()
        if reads:
            self.reads.append({"activation": activation.id, "reads": reads})

    # ------------------------------------------------------------ checkpoints

    def _recipe_header(self) -> dict:
        return {"format": CHECKPOINT_FORMAT, "engine": __version__, "seed": self.seed,
                "reshuffles": [r.to_json() for r in self.reshuffles], "hinge_margin": self.hinge_margin,
                "rulesets": [[d.to_json(), rs.name, rs.version] for d, rs in self.rulesets]}

    def _state(self) -> dict:
        return {"store": self.store.to_json(), "scheduler": self.scheduler.to_json(),
                "ordinals": self.ordinals.to_json(), "causes": self.causes.to_json(),
                "ruleset_index": self.ruleset_index}

    def state_hash(self) -> str:
        """A hash of the world state (not of pending history)."""
        return digest(self._state(), size=16)

    def checkpoint(self) -> dict:
        """The full state, as JSON, taken before the next activation runs.

        Pending history must be written first (`cut`), so a checkpoint and its run folder agree.
        """
        if any(self.pending().values()):
            raise ValueError("flush pending history to the run folder before checkpointing")
        nxt = self.scheduler.peek()
        header = self._recipe_header() | {"date": nxt.date.to_json() if nxt else None}
        return {"header": header, "state": self._state()}

    @classmethod
    def restore(cls, checkpoint: dict, calendar: Calendar, rulesets: list[tuple[Date, Ruleset]],
                seed: int, strict: bool = True, reshuffles: tuple[Reshuffle, ...] = (),
                hinge_margin: float = 0.05) -> Engine:
        """Rebuild an engine from a checkpoint and the recipe that produced it."""
        engine = cls(calendar, seed, rulesets, strict=strict, reshuffles=reshuffles, hinge_margin=hinge_margin)
        header = dict(checkpoint["header"])
        header.pop("date")
        expected = engine._recipe_header()
        for key in expected:
            if header.get(key) != expected[key]:
                raise ValueError(f"checkpoint {key} is {header.get(key)!r}, but the recipe has "
                                 f"{expected[key]!r}; engine or recipe changed, replay from scenario")
        state = checkpoint["state"]
        engine.store = Store.from_json(state["store"])
        engine.scheduler = Scheduler.from_json(state["scheduler"])
        engine.ordinals = OrdinalTable.from_json(state["ordinals"])
        engine.causes = CauseIndex.from_json(state["causes"])
        engine.ruleset_index = state["ruleset_index"]
        engine.ruleset = rulesets[engine.ruleset_index][1] if engine.ruleset_index is not None else None
        return engine
