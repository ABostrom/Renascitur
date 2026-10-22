"""The entity store.

- **Records:** every entity has an id, a kind, a status and a dict of JSON fields.
- **Columns:** bulk numeric state (aggregates), a NumPy array aligned with sorted ids.

Nothing is ever deleted: the dead and the dormant keep their records. Iteration is always in id
order. Every write names the event that caused it and leaves a delta. Record writes leave a
`StateDelta` with old and new values; column writes leave one `BulkDelta` per call, with a hash
of the values instead of the values themselves.
"""

from __future__ import annotations

import bisect
import copy
import json
from dataclasses import dataclass

import numpy as np

from renasci.core.calendar import Date
from renasci.core.canon import canonical, digest, plain

STATUSES = ("active", "dormant", "dead")


def _need_event(event: str | None) -> str:
    if not isinstance(event, str) or not event:
        raise ValueError("every write must name the event that caused it")
    return event


@dataclass(frozen=True)
class StateDelta:
    date: Date
    entity: str
    field: str
    old: object
    new: object
    event: str

    def to_json(self) -> dict:
        return {"date": self.date.to_json(), "entity": self.entity, "field": self.field,
                "old": plain(self.old), "new": plain(self.new), "event": self.event}


@dataclass(frozen=True)
class BulkDelta:
    date: Date
    component: str
    ids: tuple[str, ...]
    values_hash: str
    event: str

    def to_json(self) -> dict:
        return {"date": self.date.to_json(), "component": self.component, "ids": list(self.ids),
                "values_hash": self.values_hash, "event": self.event}


class _Entity:
    __slots__ = ("kind", "status", "fields")

    def __init__(self, kind: str, status: str, fields: dict):
        self.kind, self.status, self.fields = kind, status, fields


class _Column:
    def __init__(self, dtype: str):
        self.dtype = np.dtype(dtype)
        self.ids: list[str] = []
        self.data = np.zeros(0, dtype=self.dtype)

    def ensure(self, ids) -> None:
        """Add zeroed rows for ids not yet present, keeping ids sorted."""
        for i in ids:
            r = bisect.bisect_left(self.ids, i)
            if r == len(self.ids) or self.ids[r] != i:
                self.ids.insert(r, i)
                self.data = np.insert(self.data, r, 0)

    def lookup(self, ids) -> list[int]:
        rows = []
        for i in ids:
            r = bisect.bisect_left(self.ids, i)
            if r == len(self.ids) or self.ids[r] != i:
                raise KeyError(f"no row {i!r}")
            rows.append(r)
        return rows


class Store:
    def __init__(self):
        self._entities: dict[str, _Entity] = {}
        self._columns: dict[str, _Column] = {}
        self.deltas: list[StateDelta] = []
        self.bulk_deltas: list[BulkDelta] = []

    # ------------------------------------------------------------ records

    def create(self, kind: str, entity: str, fields: dict, date: Date, event: str) -> None:
        _need_event(event)
        if entity in self._entities:
            raise ValueError(f"entity {entity!r} already exists")
        fields = json.loads(canonical(fields))  # validates and copies
        self._entities[entity] = _Entity(kind, "active", fields)
        self.deltas.append(StateDelta(date, entity, "status", None, "active", event))
        for name in sorted(fields):
            self.deltas.append(StateDelta(date, entity, name, None, fields[name], event))

    def _entity(self, entity: str) -> _Entity:
        try:
            return self._entities[entity]
        except KeyError:
            raise KeyError(f"no entity {entity!r}") from None

    def exists(self, entity: str) -> bool:
        return entity in self._entities

    def kind(self, entity: str) -> str:
        return self._entity(entity).kind

    def status(self, entity: str) -> str:
        return self._entity(entity).status

    def ids(self, kind: str, status: str | None = None) -> list[str]:
        return sorted(i for i, e in self._entities.items()
                      if e.kind == kind and (status is None or e.status == status))

    def get(self, entity: str, field: str, default=None):
        return copy.deepcopy(self._entity(entity).fields.get(field, default))

    def set(self, entity: str, field: str, value, date: Date, event: str) -> None:
        _need_event(event)
        record = self._entity(entity)
        value = json.loads(canonical(value))
        old = record.fields.get(field)
        record.fields[field] = value
        self.deltas.append(StateDelta(date, entity, field, old, value, event))

    def set_status(self, entity: str, status: str, date: Date, event: str) -> None:
        _need_event(event)
        if status not in STATUSES:
            raise ValueError(f"status must be one of {STATUSES}, got {status!r}")
        record = self._entity(entity)
        old, record.status = record.status, status
        self.deltas.append(StateDelta(date, entity, "status", old, status, event))

    # ------------------------------------------------------------ columns

    def add_column(self, name: str, dtype: str) -> None:
        if name in self._columns:
            raise ValueError(f"column {name!r} already exists")
        self._columns[name] = _Column(dtype)

    def read_column(self, name: str, ids) -> np.ndarray:
        col = self._columns[name]
        return col.data[col.lookup(ids)].copy()

    def write_column(self, name: str, ids, values, date: Date, event: str) -> None:
        _need_event(event)
        ids, values = list(ids), np.asarray(values, dtype=self._columns[name].dtype)
        if len(ids) != len(values) or len(set(ids)) != len(ids):
            raise ValueError("write_column needs one value per distinct id")
        col = self._columns[name]
        col.ensure(ids)
        col.data[col.lookup(ids)] = values
        order = sorted(range(len(ids)), key=ids.__getitem__)
        sorted_ids = tuple(ids[i] for i in order)
        values_hash = digest([values[i].item() for i in order], size=16)
        self.bulk_deltas.append(BulkDelta(date, name, sorted_ids, values_hash, event))

    # ------------------------------------------------------------ deltas

    def drain(self) -> tuple[list[StateDelta], list[BulkDelta]]:
        """Hand pending deltas to the run-folder writer and forget them."""
        out = (self.deltas, self.bulk_deltas)
        self.deltas, self.bulk_deltas = [], []
        return out

    # ------------------------------------------------------------ JSON (checkpoint state)

    def to_json(self) -> dict:
        """The state snapshot. Pending deltas are history, not state, and are not included."""
        return {
            "entities": [{"id": i, "kind": e.kind, "status": e.status, "fields": e.fields}
                         for i, e in sorted(self._entities.items())],
            "columns": {name: {"dtype": col.dtype.name, "ids": list(col.ids), "data": col.data.tolist()}
                        for name, col in sorted(self._columns.items())},
        }

    @classmethod
    def from_json(cls, data: dict) -> Store:
        store = cls()
        for row in data["entities"]:
            if row["status"] not in STATUSES:
                raise ValueError(f"bad status in checkpoint: {row!r}")
            if row["id"] in store._entities:
                raise ValueError(f"duplicate entity in checkpoint: {row['id']!r}")
            store._entities[row["id"]] = _Entity(row["kind"], row["status"], json.loads(canonical(row["fields"])))
        for name, col in data["columns"].items():
            c = _Column(col["dtype"])
            if col["ids"] != sorted(set(col["ids"])) or len(col["ids"]) != len(col["data"]):
                raise ValueError(f"column {name!r} in checkpoint is not sorted, unique and aligned")
            c.ids, c.data = list(col["ids"]), np.asarray(col["data"], dtype=c.dtype)
            store._columns[name] = c
        return store
