"""Typed events, their causes, and the cause graph.

An event is a dated fact: participants in named roles, a place, a payload, a source, a visibility,
and the causes that produced it. Event types are registered with a schema, and every event is
validated against it. A secret event (a poisoning) and its public cover (a death from "a wasting
illness") are two events, the cover caused by the secret.
"""

from __future__ import annotations

import bisect
import json
from dataclasses import dataclass, replace

from renasci.core.calendar import Date
from renasci.core.canon import canonical

CAUSE_KINDS = ("event", "pin", "ripple", "state", "ambition", "belief", "drive")
SOURCE_KINDS = ("system", "action", "pin", "ripple", "lod", "scenario")
VISIBILITIES = ("public", "secret")
PAYLOAD_TYPES = ("str", "int", "float", "bool", "id", "ids", "json")

Node = tuple[str, str]  # (kind, ref) in the cause graph


def _ref(label: str, value) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string, got {value!r}")
    return value


@dataclass(frozen=True, order=True)
class Cause:
    kind: str
    ref: str

    def __post_init__(self):
        if self.kind not in CAUSE_KINDS:
            raise ValueError(f"cause kind must be one of {CAUSE_KINDS}, got {self.kind!r}")
        _ref("cause ref", self.ref)

    def to_json(self) -> list[str]:
        return [self.kind, self.ref]


@dataclass(frozen=True)
class Source:
    kind: str
    ref: str

    def __post_init__(self):
        if self.kind not in SOURCE_KINDS:
            raise ValueError(f"source kind must be one of {SOURCE_KINDS}, got {self.kind!r}")
        _ref("source ref", self.ref)

    def to_json(self) -> list[str]:
        return [self.kind, self.ref]


@dataclass(frozen=True)
class EventType:
    name: str
    version: int
    roles: dict[str, tuple[int, int]]  # role -> (min, max) participants
    payload: dict[str, str]  # field -> one of PAYLOAD_TYPES
    visibility: str = "public"
    dead_roles: tuple[str, ...] = ()  # roles that may hold the dead (the deceased at a funeral)

    def __post_init__(self):
        _ref("event type name", self.name)
        if self.visibility not in VISIBILITIES:
            raise ValueError(f"visibility must be one of {VISIBILITIES}")
        for role, (lo, hi) in self.roles.items():
            if not 0 <= lo <= hi:
                raise ValueError(f"role {role!r} has a bad cardinality {(lo, hi)}")
        for name, kind in self.payload.items():
            if kind not in PAYLOAD_TYPES:
                raise ValueError(f"payload field {name!r} has unknown type {kind!r}")
        if not set(self.dead_roles) <= set(self.roles):
            raise ValueError("dead_roles must name declared roles")


@dataclass(frozen=True)
class Event:
    id: str
    date: Date
    type: str
    roles: dict[str, tuple[str, ...]]
    place: str | None
    causes: tuple[Cause, ...]
    payload: dict
    source: Source
    visibility: str | None = None  # None: take the type's default at validation

    def __post_init__(self):
        # Normalise: roles sorted by name, members sorted; causes sorted; payload copied.
        roles = {r: tuple(sorted(m)) for r, m in sorted(self.roles.items())}
        object.__setattr__(self, "roles", roles)
        object.__setattr__(self, "causes", tuple(sorted(self.causes)))
        object.__setattr__(self, "payload", json.loads(canonical(self.payload)))

    def participants(self) -> list[str]:
        return sorted({e for members in self.roles.values() for e in members})

    def to_json(self) -> dict:
        return {
            "id": self.id, "date": self.date.to_json(), "type": self.type,
            "roles": {r: list(m) for r, m in self.roles.items()}, "place": self.place,
            "causes": [c.to_json() for c in self.causes], "payload": self.payload,
            "source": self.source.to_json(), "visibility": self.visibility,
        }

    @classmethod
    def from_json(cls, d: dict) -> Event:
        return cls(
            id=d["id"], date=Date.from_json(d["date"]), type=d["type"],
            roles={r: tuple(m) for r, m in d["roles"].items()}, place=d["place"],
            causes=tuple(Cause(*c) for c in d["causes"]), payload=d["payload"],
            source=Source(*d["source"]), visibility=d["visibility"],
        )


def _check_payload_value(name: str, kind: str, value) -> None:
    ok = {
        "str": lambda v: isinstance(v, str),
        "int": lambda v: type(v) is int,
        "float": lambda v: type(v) in (int, float),
        "bool": lambda v: type(v) is bool,
        "id": lambda v: isinstance(v, str) and bool(v),
        "ids": lambda v: isinstance(v, list) and all(isinstance(x, str) and x for x in v),
        "json": lambda v: True,
    }[kind](value)
    if not ok:
        raise TypeError(f"payload field {name!r} must be {kind}, got {value!r}")


class Registry:
    def __init__(self):
        self._types: dict[str, EventType] = {}

    def register(self, event_type: EventType) -> None:
        if event_type.name in self._types:
            raise ValueError(f"event type {event_type.name!r} is already registered")
        self._types[event_type.name] = event_type

    def get(self, name: str) -> EventType:
        try:
            return self._types[name]
        except KeyError:
            raise ValueError(f"unknown event type {name!r}") from None

    def validate(self, event: Event, store=None, today: Date | None = None) -> Event:
        """Check `event` against its schema and return it with its visibility filled in.

        With `store`, every participant must exist and be alive (except in `dead_roles`).
        With `today`, the event must be dated today.
        """
        t = self.get(event.type)
        _ref("event id", event.id)
        if not isinstance(event.date, Date):
            raise TypeError(f"event date must be a Date, got {event.date!r}")
        if today is not None and event.date != today:
            raise ValueError(f"event {event.id} is dated {event.date}, but today is {today}")
        if Cause("event", event.id) in event.causes:
            raise ValueError(f"event {event.id} cannot cause itself")
        if event.place is not None:
            _ref("place", event.place)

        for role in event.roles:
            if role not in t.roles:
                raise ValueError(f"{event.type} has no role {role!r}")
        for role, (lo, hi) in t.roles.items():
            members = event.roles.get(role, ())
            if not lo <= len(members) <= hi:
                raise ValueError(f"{event.type}.{role} needs {lo}..{hi} participants, got {len(members)}")
            if len(set(members)) != len(members):
                raise ValueError(f"{event.type}.{role} lists an entity twice")
            for member in members:
                _ref("participant", member)
                if store is not None:
                    if not store.exists(member):
                        raise ValueError(f"participant {member!r} does not exist")
                    if store.status(member) == "dead" and role not in t.dead_roles:
                        raise ValueError(f"participant {member!r} is dead (role {role!r})")

        if set(event.payload) != set(t.payload):
            raise ValueError(f"{event.type} payload fields must be exactly {sorted(t.payload)}, "
                             f"got {sorted(event.payload)}")
        for name, kind in t.payload.items():
            _check_payload_value(name, kind, event.payload[name])

        visibility = t.visibility if event.visibility is None else event.visibility
        if visibility not in VISIBILITIES:
            raise ValueError(f"visibility must be one of {VISIBILITIES}, got {visibility!r}")
        return replace(event, visibility=visibility)


class CauseIndex:
    """The cause graph, queryable both ways. Every edge runs from an event to one of its causes."""

    def __init__(self):
        self._events: list[str] = []  # sorted
        self._parents: dict[Node, list[Node]] = {}  # sorted lists
        self._children: dict[Node, list[Node]] = {}

    def add(self, event: Event) -> None:
        self._add(event.id, [(c.kind, c.ref) for c in event.causes])

    def _add(self, event_id: str, causes: list[Node]) -> None:
        r = bisect.bisect_left(self._events, event_id)
        if r < len(self._events) and self._events[r] == event_id:
            raise ValueError(f"event {event_id} is already in the cause index")
        self._events.insert(r, event_id)
        node = ("event", event_id)
        self._parents[node] = sorted(set(causes))
        for parent in self._parents[node]:
            bisect.insort(self._children.setdefault(parent, []), node)

    def _walk(self, start: Node, edges: dict[Node, list[Node]], depth: int | None) -> list[Node]:
        seen: dict[Node, None] = {}
        frontier, level = [start], 0
        while frontier and (depth is None or level < depth):
            nxt = []
            for node in frontier:
                for other in edges.get(node, ()):
                    if other not in seen and other != start:
                        seen[other] = None
                        nxt.append(other)
            frontier, level = sorted(nxt), level + 1
        return sorted(seen)

    def ancestors(self, node: Node, depth: int | None = None) -> list[Node]:
        return self._walk(node, self._parents, depth)

    def descendants(self, node: Node, depth: int | None = None) -> list[Node]:
        return self._walk(node, self._children, depth)

    def to_json(self) -> dict:
        return {
            "events": list(self._events),
            "edges": [[e, k, r] for e in self._events for k, r in self._parents[("event", e)]],
        }

    @classmethod
    def from_json(cls, data: dict) -> CauseIndex:
        idx = cls()
        causes: dict[str, list[Node]] = {e: [] for e in data["events"]}
        for e, k, r in data["edges"]:
            causes[e].append((Cause(k, r).kind, r))
        for e in data["events"]:
            idx._add(e, causes[e])
        return idx
