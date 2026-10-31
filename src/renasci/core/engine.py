"""The engine: owns the world state and runs systems in scheduler order.

Rulesets switch on configured dates. Each switch is an engine activation that runs before
anything else on that day. At a switch:
- a system that left, or changed its cadence or priority, has its queued activations removed
  (listed in `dropped`);
- every cadence system in the new ruleset without a queued cadence run starts one that day. That
  covers new systems, changed ones, and carried ones whose chain ended at an age boundary.
"""

from __future__ import annotations

import json

from renasci import __version__
from renasci.core.calendar import Calendar, Date
from renasci.core.canon import canonical, digest
from renasci.core.determinism import check_environment, versions
from renasci.core.context import Ctx, UndeclaredAccess
from renasci.core.pools import digests, load as load_pools, pools as base_pools
from renasci.core.events import Cause, CauseIndex, Event, EventType, Registry, Source
from renasci.core.ids import CAST_STARTS, event_id
from renasci.core.lod import EVENT_TYPES as LOD_TYPES
from renasci.core.lod import ResolutionPolicy
from renasci.core.pins import Director, Pin, feasibility
from renasci.core.ripples import EVENT_TYPES as RIPPLE_TYPES
from renasci.core.ripples import KINDS as ALL_RIPPLE_KINDS
from renasci.core.ripples import NEEDS_DISGUISE, SPANS, SUPPORTED as RIPPLE_KINDS, Ripple
from renasci.core.rng import KeyedRng, OrdinalTable, Reshuffle
from renasci.core.scheduler import Activation, Scheduler, next_due
from renasci.core.store import Store
from renasci.core.systems import Ruleset

__all__ = ["Engine", "UndeclaredAccess"]

SWITCH_PRIORITY = -(10**9)
DEADLINE_PRIORITY = 10**9  # pin deadlines run after everything else that day
RIPPLE_PRIORITY = SWITCH_PRIORITY + 1  # ripples apply right after a ruleset switch, before systems
CAST = EventType("engine.cast", 1, roles={"subject": (1, 1)}, payload={"kind": "str"}, dead_roles=("subject",))
CAST_COLUMN = EventType("engine.cast_column", 1, roles={}, payload={"column": "str"})
CHECKPOINT_FORMAT = 3  # 2: recipe includes major.minor versions; 3: reshuffles in the header, not the recipe


class Engine:
    def __init__(self, calendar: Calendar, seed: int, rulesets: list[tuple[Date, Ruleset]],
                 strict: bool = True, reshuffles: tuple[Reshuffle, ...] = (), hinge_margin: float = 0.05,
                 resolution: ResolutionPolicy | None = None):
        check_environment()
        self.resolution = resolution or ResolutionPolicy()
        step = self.resolution.default.step
        if self.resolution.ever_coarse() and (step.days or step.years < 1):
            raise ValueError(f"a coarse step is whole years (S8 §7), got {step}")
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
        self.timeseries: list[dict] = []  # pending history: aggregate numbers over time (ctx.series)
        # Every read row (the Python API and tests). Recipe runs default to one digest per scope (#151).
        self.full_reads = True
        self.hinges: list[dict] = []  # close calls with stakes: the source data for latch points
        self.hinge_margin = float(hinge_margin)  # a draw with stakes is a hinge only if it was this close
        self.pools = base_pools  # this run's pools; `extend` swaps in its own set (#162)
        self.extensions: list = []  # [[name, source digest], ...]
        self.granted_reads: frozenset = frozenset()  # what extensions' entries declare they read and write
        self.granted_writes: frozenset = frozenset()
        self.odds_hooks: list = []  # (ctx, p, purpose, owner) -> (p, cause or None): ripples, director
        self.dropped: list[str] = []
        self.ruleset: Ruleset | None = None
        self.ruleset_index: int | None = None
        self.director = Director()
        self.ripples: tuple[Ripple, ...] = ()
        self.ripple_log: list[dict] = []  # pending history
        self.activations: list[dict] = []  # pending history: every activation run, in order
        self._scopes: dict[str, str | None] = {}  # pending: the ctx scope each event was emitted in
        self._date: Date | None = None

        self._register(CAST)
        self._register(CAST_COLUMN)
        for t in RIPPLE_TYPES.values():
            self._register(t)
        for t in LOD_TYPES:
            self._register(t)
        for _, rs in rulesets:
            for t in rs.event_types():
                self._register(t)
            for d in rs.disguises:
                if d.handles not in ALL_RIPPLE_KINDS:
                    raise ValueError(f"disguise {d.name!r} handles {d.handles!r}, which is not a ripple kind")
        for i, d in enumerate(dates):
            self.scheduler.push(Activation(d, SWITCH_PRIORITY, "engine", "switch", "engine", {"index": i}, ()))

    def register_event_types(self, types) -> None:
        """Register event types for systems added after the engine was built (tools and tests)."""
        for t in types:
            self._register(t)

    def extend(self, names) -> None:
        """Run with the base pools plus these extensions (#162). Before the first step: they shape history."""
        if not names:
            return
        if self.scheduler.now is not None:
            raise ValueError("an engine can't be extended once it has started")
        self.pools = load_pools(names)
        self.extensions = digests(names)
        entries = [e for pool in self.pools.values() for k, e in pool.items() if pool.sources()[k] != "base"]
        self.granted_reads = frozenset().union(*(getattr(e, "reads", ()) for e in entries))
        self.granted_writes = frozenset().union(*(getattr(e, "writes", ()) for e in entries))
        for t in self.pools.event_types.values():
            self._register(t)

    def _register(self, t: EventType) -> None:
        try:
            existing = self.registry.get(t.name)
        except ValueError:
            self.registry.register(t)
            return
        if existing != t:
            raise ValueError(f"two different event types are both named {t.name!r}")

    # ------------------------------------------------------------ setup

    def cast(self, kind: str, entity: str, fields: dict, status: str = "active") -> Event:
        """Place an entity into the world at the start date, before anything runs. `status` lets a
        scenario cast the dead (a house's founder, whose children are its line of succession)."""
        if self._date is not None:
            raise ValueError("casting happens before the run starts")
        eid = event_id("engine", entity, "cast", self.start, 0)
        self.store.create(kind, entity, fields, self.start, eid, status=status)
        return self.record(Event(eid, self.start, CAST.name, {"subject": (entity,)}, None, (),
                                 {"kind": kind}, Source("scenario", "cast")), created=[entity])

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

    def record(self, event: Event, created=(), scope: str | None = None) -> Event:
        event = self.registry.validate(event, store=self.store, today=self._date or self.start)
        self.causes.add(event)
        self.events.append(event)
        self._scopes[event.id] = scope
        self.director.observe(event, created, field=lambda entity, name: self.store.get(entity, name))
        return event

    def apply_pins(self, pins, end: Date | None = None, cast: bool = True) -> dict[str, str]:
        """Load canon pins before the run: classify them, cast what canon places, schedule deadlines."""
        if self._date is not None and cast:
            raise ValueError("pins are applied before the run starts")
        pins = tuple(pins)
        last = self.rulesets[-1][0]
        end = end or Date(last.age, self.calendar._by_index[last.age].last_year or 10**6,
                          self.calendar.days_per_year - 1)
        self.director = Director(pins)
        classes = feasibility(pins, self.start, end)
        self.director.born = frozenset(p.payload["bind"]["subject"] for p in self.director.pins
                                       if p.payload.get("bind") and classes[p.id] == "ok")
        for pin in self.director.pins:
            status = classes[pin.id]
            self.director.status[pin.id] = "open" if status == "ok" else status
            if status != "ok":
                continue
            if pin.kind == "existence" and pin.subject in self.director.born:
                pass  # born during the run: met when its birth pin binds it, never cast up front
            elif pin.kind == "existence" and self.store.exists(pin.subject):
                if self.store.status(pin.subject) != "active":
                    self.director.status[pin.id] = "violated"  # placed, but not alive to be needed
                    continue
                self.director.status[pin.id] = "satisfied"  # the scenario already placed it
                self.director.met[pin.id] = (self.start, 0)  # (date, event sequence), as the director keeps it
                self.director.held.add(pin.id)
            elif pin.kind == "existence" and pin.subject.startswith(CAST_STARTS):
                if cast:
                    self.cast(pin.payload.get("kind", "person"), pin.subject, pin.payload.get("fields", {}))
                self.director.status[pin.id] = "satisfied"
                self.director.met[pin.id] = (self.start, 0)  # (date, event sequence), as the director keeps it
            elif pin.kind in ("event", "existence") and pin.window and cast:
                self.scheduler.push(Activation(pin.window[1], DEADLINE_PRIORITY, "engine", "pin_deadline",
                                               "engine", {"pin": pin.id}, ()))
        return classes

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
            "events": [ev.to_json() | {"scope": self._scopes.get(ev.id)} for ev in events],
            "causes": [{"event": ev.id, "kind": c.kind, "ref": c.ref} for ev in events for c in ev.causes],
            "participants": [{"event": ev.id, "role": role, "entity": entity}
                             for ev in events for role, members in ev.roles.items() for entity in members],
            "entities": [dict(row) for row in self.store.created],
            "state_deltas": [d.to_json() for d in self.store.deltas],
            "bulk_deltas": [d.to_json() for d in self.store.bulk_deltas],
            "reads": list(self.reads),
            "hinges": list(self.hinges),
            "dropped": [{"activation": a} for a in self.dropped],
            "strain": list(self.director.strain),
            "ripples": list(self.ripple_log),
            "pins": list(self.director.changes),
            "activations": list(self.activations),
            "timeseries": list(self.timeseries),
        }

    def clear_pending(self) -> None:
        """Forget history already written. State (store, cause index, queue) stays."""
        self.events, self.reads, self.hinges, self.dropped = [], [], [], []
        self.director.strain = []
        self.director.changes = []
        self.ripple_log = []
        self.activations = []
        self.timeseries = []
        self._scopes = {}
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
            if activation.system == "engine" and activation.purpose == "ripple":
                self._apply_ripple(activation)
            elif activation.system == "engine" and activation.purpose == "pin_deadline":
                self.director.deadline(self, activation.payload["pin"], self._forcer_ctx)
            elif activation.system == "engine":
                self._switch(activation)
            else:
                self._dispatch(activation)

    def _advance(self, date: Date) -> None:
        if date != self._date:
            self._date = date
            self.ordinals.close_before(self.calendar.canonical_tick(date))

    def check_conservation(self) -> list[str]:
        """Problems the active ruleset's conservation check finds (counts, age structure, ...)."""
        if self.ruleset is None or self.ruleset.conservation is None:
            return []
        return list(self.ruleset.conservation(self.store))

    # ------------------------------------------------------------ ripples

    def _ruleset_at(self, date: Date) -> Ruleset:
        return [rs for d, rs in self.rulesets if d <= date][-1]

    def apply_ripples(self, ripples) -> None:
        """Load ripples before the run: validate them all, then schedule each on its date."""
        if self._date is not None or self.ripples:
            raise ValueError("ripples are applied once, before the run starts "
                             "(to add one later, replay from a checkpoint with Engine.restore(..., ripples=...))")
        ripples = self._validate_ripples(ripples)
        for r in ripples:
            self.scheduler.push(Activation(r.date, RIPPLE_PRIORITY, "engine", "ripple", "engine",
                                           {"ripple": r.id}, ()))
        self.ripples = ripples

    def _validate_ripples(self, ripples) -> tuple[Ripple, ...]:
        ripples = tuple(sorted(ripples, key=lambda r: (r.date, r.id)))
        if len({r.id for r in ripples}) != len(ripples):
            raise ValueError("ripple ids must be unique")
        for r in ripples:
            if r.kind not in RIPPLE_KINDS:
                raise ValueError(f"ripple {r.id}: {r.kind!r} is not supported ({RIPPLE_KINDS})")
            self.calendar.check(r.date)
            if r.date < self.start:
                raise ValueError(f"ripple {r.id} is dated before the run starts")
            r.check()
            if r.kind in NEEDS_DISGUISE:
                disguise = self._ruleset_at(r.date).disguise(r.kind)
                if disguise is None:
                    raise ValueError(f"ripple {r.id}: the ruleset active on {r.date} has no {r.kind!r} disguise")
                check = getattr(disguise, "check_ripple", None)
                if check is not None:
                    check(r)  # (a disguise refuses params it can't apply now, not mid-run)
        return ripples

    def reshuffle(self, reshuffles) -> None:
        """Re-roll everything from each reshuffle's tick on (a recipe's [[reshuffle]]), set before the run
        starts and after casting: a reshuffle must start after the run's first quarter."""
        if self._date is not None:
            raise ValueError("reshuffles are set before the run starts")
        first = self.calendar.canonical_tick(self.start)
        for r in reshuffles:
            if tuple(r.from_tick) <= first:
                raise ValueError(f"reshuffle {r.salt!r} starts at {r.from_tick}, not after the run's first quarter {first}")
        self.reshuffles = tuple(reshuffles)
        self.rng = KeyedRng(self.seed, self.reshuffles)

    def protection(self, entity: str, date: Date) -> Ripple | None:
        for r in self.ripples:
            if r.kind == "protect" and r.target == entity and r.date <= date <= r.until:
                return r
        return None

    def fortune(self, kind: str, owner: str, date: Date) -> Ripple | None:
        """The favour or luck ripple active for a draw owned by `owner` today, if any. Luck is the
        target's own draws; favour also the draws of their schemes and ambitions (owned by them)."""
        for r in self.ripples:
            if r.kind != kind or not r.date <= date <= r.until:
                continue
            if owner == r.target:
                return r
            if kind == "favour" and self.store.exists(owner) and self.store.kind(owner) in ("scheme", "ambition") \
                    and self.store.get(owner, "owner") == r.target:
                return r
        return None

    def log_ripple(self, ripple: Ripple, action: str, applied: bool, activation: str, **extra) -> dict:
        row = json.loads(canonical({"ripple": ripple.id, "kind": ripple.kind, "target": ripple.target,
                                    "params": ripple.params, "action": action,
                                     "applied": applied, "date": self._date or ripple.date,
                                     "activation": activation, "event": None, **extra}))
        self.ripple_log.append(row)
        return row

    def _apply_ripple(self, activation: Activation) -> None:
        r = next(x for x in self.ripples if x.id == activation.payload["ripple"])
        self._note_activation(activation)
        roles = {"target": (r.target,)} if self.store.exists(r.target) else {}
        secret = self.record(Event(event_id("engine", r.target, f"ripple:{r.id}", r.date, 0, activation.id),
                                   r.date, f"ripple.{r.kind}", roles, None, (), {"target": r.target, "params": r.params},
                                   Source("ripple", r.id), activation=activation.id))
        if r.kind in SPANS:  # (protect, favour, luck: they act on what happens while they last)
            self.log_ripple(r, "apply", True, activation.id, event=secret.id)
            return
        disguise = self.ruleset.disguise(r.kind)
        applied = False
        if disguise is not None:
            ctx = Ctx(self, disguise, Activation(r.date, RIPPLE_PRIORITY, "engine", f"ripple:{r.id}", disguise.name,
                                                 {}, (Cause("ripple", r.id), Cause("event", secret.id))))
            try:
                applied = bool(disguise.apply(ctx, r))
            except Exception:
                self.log_ripple(r, "error", False, activation.id, event=secret.id)
                raise
            finally:
                self.finish(ctx)
            if not applied and ctx._event is not None:
                raise ValueError(f"disguise {disguise.name!r} changed the world but reported failure for ripple {r.id}")
        self.log_ripple(r, "apply", applied, activation.id, event=secret.id)

    def _forcer_ctx(self, forcer, pin: Pin) -> Ctx:
        date = pin.window[1]
        return Ctx(self, forcer, Activation(date, DEADLINE_PRIORITY, "engine", f"force:{pin.id}", forcer.name, {},
                                            (Cause("pin", pin.id),)))

    def _switch(self, activation: Activation) -> None:
        old = self.ruleset
        self.ruleset_index = activation.payload["index"]
        self.ruleset = new = self.rulesets[self.ruleset_index][1]

        def unchanged(name: str) -> bool:
            a, b = old.get_any(name) if old else None, new.get_any(name)
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

    def finish(self, ctx: Ctx) -> None:
        """Keep what a completed activation produced besides events and writes: hinges and reads."""
        self._note_activation(ctx.activation)
        self.hinges.extend(ctx.hinges)
        self.timeseries.extend(ctx._series)
        self.reads.extend(ctx.read_rows(full=self.full_reads))

    def _note_activation(self, activation: Activation) -> None:
        self.activations.append({"activation": activation.id, "system": activation.system,
                                 "date": activation.date.to_json(),
                                 "causes": [c.to_json() for c in activation.causes]})

    def _dispatch(self, activation: Activation) -> None:
        system = self.ruleset.get_any(activation.system)
        if system is None:
            self.dropped.append(activation.id)
            return
        ctx = Ctx(self, system, activation)
        if activation.purpose == "cadence":
            years, due = self._coarse_step(activation.date, system)
            if years:
                system.coarse_fallback(ctx, years)
            else:
                system.run(ctx)
                due = next_due(self.calendar, activation.date, system.cadence)
            if due is not None:
                self.scheduler.push(Activation(due, system.priority, system.name, "cadence", system.name, {}, ()))
        else:
            system.handle(ctx, activation)
        self.finish(ctx)

    def _coarse_step(self, date: Date, system) -> tuple[int, Date | None]:
        """A coarse step for `system` at `date` (#157): how many years, and when it runs next. (0, None)
        means run fine: the date is fine, the system has no `coarse_fallback` (it keeps its own cadence, so
        people still age and die), the date is mid-year (a sub-yearly system runs fine to the year's start),
        or a focus window or a ruleset change comes within the year. A step runs to the start of a later
        year: cut short where the next focus window's or ruleset's year starts, and at the end of the age.
        (Pins, ripples and odds hooks dated inside a step act on a fallback only at the step's start: open a
        focus window around them to see them year by year. `coarse_ok` has no effect yet.)"""
        res = self.resolution.at(date)
        if res.kind != "coarse" or system.coarse_fallback is None or date.day:
            return 0, None
        end = date.year + res.step.years
        ahead = [start for start, _ in self.resolution.focus if start > date and start.age == date.age]
        ahead += [start for start, _ in self.rulesets if start > date and start.age == date.age]
        if ahead:
            end = min(end, min(ahead).year)
        if end <= date.year:
            return 0, None
        last = self.calendar._by_index[date.age].last_year
        if last is not None and end > last:
            return last - date.year + 1, None
        return end - date.year, Date(date.age, end, 0)

    # ------------------------------------------------------------ checkpoints

    def recipe(self) -> dict:
        """Everything that shapes history besides the state: checked on restore, hashed in full."""
        def system(s):
            fallback = s.coarse_fallback
            return {"name": s.name, "class": type(s).__qualname__, "cadence": s.cadence, "priority": s.priority,
                    "coarse_ok": s.coarse_ok,
                    "coarse_fallback": getattr(fallback, "__qualname__", None) if fallback else None,
                    "reads": sorted(s.reads), "writes": sorted(s.writes),
                    "event_types": [{"name": t.name, "version": t.version, "roles": t.roles, "payload": t.payload,
                                     "visibility": t.visibility, "dead_roles": list(t.dead_roles)}
                                    for t in s.event_types]}

        cal = self.calendar
        return {
            **({"extensions": self.extensions} if self.extensions else {}),
            "engine": __version__, "versions": versions(), "seed": self.seed, "strict": self.strict, "hinge_margin": self.hinge_margin,
            "calendar": {"ages": [[a.index, a.abbrev, a.name, a.last_year] for a in cal.ages],
                         "months": cal.months, "seasons": cal.seasons},
            "rulesets": [{"start": d.to_json(), "name": rs.name, "version": rs.version, "params": rs.params,
                          "systems": [system(s) for s in rs.systems],
                          "forcers": [system(f) | {"handles": f.handles} for f in rs.forcers],
                          "disguises": [system(d) | {"handles": d.handles} for d in rs.disguises]}
                         for d, rs in self.rulesets],
            "pins": [p.to_json() for p in self.director.pins],
            "resolution": self.resolution.to_json(),
        }

    def _state(self) -> dict:
        return {"store": self.store.to_json(), "scheduler": self.scheduler.to_json(),
                "ordinals": self.ordinals.to_json(), "causes": self.causes.to_json(),
                "ruleset_index": self.ruleset_index, "director": self.director.to_json()}

    def state_hash(self) -> str:
        """A hash of the world state (not of pending history)."""
        return digest(self._state(), size=16)

    def checkpoint(self, at: Date, segments: int) -> dict:
        """The full state as JSON, at the position "before any activation dated `at`".

        `segments` is the run folder's closed-segment count (from `cut`): a replay truncates to it.
        Pending history must be written first, so a checkpoint and its run folder agree.
        """
        for pool in (self.pools.actions, self.pools.ambitions):  # (behaviour; a data pool's entries are their fields)
            for key, entry in pool.items():
                if vars(entry):
                    raise ValueError(f"{pool.name} entry {key} keeps instance state {sorted(vars(entry))}; "
                                     "entries must be stateless, with all state in the store")
        if any(self.pending().values()):
            raise ValueError("flush pending history to the run folder before checkpointing")
        if self.odds_hooks:
            raise ValueError("odds hooks are not checkpointable yet (ripples and the director save state in #48/#49)")
        for _, rs in self.rulesets:
            for s in rs.systems + rs.forcers + rs.disguises:
                if vars(s):
                    raise ValueError(f"system {s.name} keeps instance state {sorted(vars(s))}; "
                                     "systems must be stateless, with all state in the store")
        nxt, now = self.scheduler.peek(), self.scheduler.now
        if (nxt is not None and nxt.date < at) or (now is not None and now >= at):
            raise ValueError(f"the engine is not positioned before {at}: last ran {now}, next is "
                             f"{nxt.date if nxt else None}; use run_before({at})")
        self.ordinals.close_before(self.calendar.canonical_tick(at))
        recipe = self.recipe()
        header = {"format": CHECKPOINT_FORMAT, "date": at.to_json(), "segments": int(segments),
                  "ripples": [r.to_json() for r in self.ripples],
                  "reshuffles": sorted((r.to_json() for r in self.reshuffles), key=lambda r: (r["from"], r["salt"])),
                  "recipe_hash": digest(recipe, size=16), "recipe": recipe}
        return {"header": header, "state": self._state()}

    @classmethod
    def restore(cls, checkpoint: dict, calendar: Calendar, rulesets: list[tuple[Date, Ruleset]],
                seed: int, strict: bool = True, reshuffles: tuple[Reshuffle, ...] = (),
                hinge_margin: float = 0.05, pins=(), ripples=(), resolution: ResolutionPolicy | None = None,
                extensions=()) -> Engine:
        """Rebuild an engine from a checkpoint and the recipe (including its pins) that produced it.

        Ripples dated before the checkpoint must be exactly the original run's. Ripples on or after
        it are free: that is how a what-if replays from a checkpoint with a new intervention.
        """
        header = checkpoint["header"]
        if header.get("format") != CHECKPOINT_FORMAT:
            raise ValueError(f"checkpoint format {header.get('format')!r} is not {CHECKPOINT_FORMAT}; "
                             "engine changed, replay from scenario")
        engine = cls(calendar, seed, rulesets, strict=strict, reshuffles=reshuffles, hinge_margin=hinge_margin,
                     resolution=resolution)
        engine.extend(extensions)
        engine.apply_pins(pins, cast=False)
        recipe = engine.recipe()
        if digest(recipe, size=16) != header["recipe_hash"]:
            old = header.get("recipe", {})
            changed = sorted(k for k in recipe if old.get(k) != json_plain(recipe[k]))
            raise ValueError(f"the recipe differs from the checkpoint's ({', '.join(changed) or 'details'}); "
                             "engine or recipe changed, replay from scenario")
        state = checkpoint["state"]
        engine.store = Store.from_json(state["store"])
        engine.scheduler = Scheduler.from_json(state["scheduler"])
        engine.ordinals = OrdinalTable.from_json(state["ordinals"])
        engine.causes = CauseIndex.from_json(state["causes"])
        engine.ruleset_index = state["ruleset_index"]
        engine.director.load_json(state["director"])
        at = Date.from_json(header["date"])
        given = tuple(sorted(ripples, key=lambda r: (r.date, r.id)))
        before_now = [r.to_json() for r in given if r.date < at]
        before_then = [r for r in header["ripples"] if Date.from_json(r["date"]) < at]
        if before_now != before_then:
            raise ValueError(f"ripples dated before {at} must match the checkpointed run; "
                             "replay from an earlier checkpoint to change them")
        # (A reshuffle is like a ripple: those already in force at the checkpoint are its history; later ones are free.)
        def begun(tick) -> bool:  # (its quarter started before the checkpoint: draws in it may have been made)
            age, year, q = tick
            return Date(age, year, -(-q * calendar.days_per_year // 4)) < at

        now = sorted((r.to_json() for r in reshuffles if begun(r.from_tick)), key=lambda r: (r["from"], r["salt"]))
        then = [r for r in header.get("reshuffles", []) if begun(r["from"])]
        if now != then:
            raise ValueError(f"reshuffles from before {at} must match the checkpointed run; "
                             "replay from an earlier checkpoint to change them")
        engine.ripples = engine._validate_ripples(given)
        engine.scheduler.remove_where(lambda a: a.system == "engine" and a.purpose == "ripple")
        for r in given:
            if r.date >= at:
                engine.scheduler.push(Activation(r.date, RIPPLE_PRIORITY, "engine", "ripple", "engine",
                                                 {"ripple": r.id}, ()))
        engine.ruleset = rulesets[engine.ruleset_index][1] if engine.ruleset_index is not None else None
        engine._date = engine.scheduler.now or Date.from_json(header["date"])  # restored engines are running
        return engine


def json_plain(value):
    import json

    from renasci.core.canon import canonical
    return json.loads(canonical(value))
