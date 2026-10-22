"""The entity store.

- **Records:** every entity has an id, a kind, a status and a dict of JSON fields.
- **Columns:** bulk numeric state (aggregates), a NumPy array aligned with sorted ids.

Nothing is ever deleted: the dead and the dormant keep their records. Iteration is always in id
order. Every write names the event that caused it and leaves a delta. Record writes leave a
`StateDelta` with old and new values; column writes leave one `BulkDelta` per call, with a hash
of the values instead of the values themselves. Writes are validated completely before anything
changes, so a failed write leaves the store untouched.
"""

from __future__ import annotations

import bisect
import json
from dataclasses import dataclass

import numpy as np

from renasci.core.calendar import Date
from renasci.core.canon import canonical, digest, plain

STATUSES = ("active", "dormant", "dead")
RESERVED_FIELDS = ("status",)  # status lives on the entity; its deltas use the field name "status"
COLUMN_KINDS = "biuf"  # bool, int, uint, float


def _json_copy(value):
    """Validate as canonical JSON and return an independent plain copy."""
    return json.loads(canonical(value))


def _need_event(event) -> str:
    if not isinstance(event, str) or not event:
        raise ValueError("every write must name the event that caused it")
    return event


def _need_name(label: str, value) -> str:
    if not isinstance(value, str) or not value:
        raise TypeError(f"{label} must be a non-empty string, got {value!r}")
    return value


def _need_date(date) -> Date:
    if not isinstance(date, Date):
        raise TypeError(f"date must be a Date, got {date!r}")
    return date


def _need_field(field) -> str:
    _need_name("field", field)
    if field in RESERVED_FIELDS:
        raise ValueError(f"{field!r} is reserved; use set_status")
    return field


@dataclass(frozen=True)
class StateDelta:
    date: Date
    entity: str
    field: str
    old: object
    new: object
    event: str
    activation: str = ""  # the activation that made the write ("" for casting)

    def to_json(self) -> dict:
        return {"date": self.date.to_json(), "entity": self.entity, "field": self.field,
                "old": plain(self.old), "new": plain(self.new), "event": self.event,
                "activation": self.activation}


@dataclass(frozen=True)
class BulkDelta:
    date: Date
    component: str  # one column; "" when `components` lists several written together
    ids: tuple[str, ...]  # every id written, sorted: clarity over compactness
    values_hash: str
    event: str
    activation: str
    components: tuple[str, ...] = ()  # several columns of the same ids in one write (sorted)

    def to_json(self) -> dict:
        where = {"components": list(self.components)} if self.components else {"component": self.component}
        return {"date": self.date.to_json(), **where, "ids": list(self.ids),
                "values_hash": self.values_hash, "event": self.event, "activation": self.activation}


class _Entity:
    __slots__ = ("kind", "status", "fields")

    def __init__(self, kind: str, status: str, fields: dict):
        self.kind, self.status, self.fields = kind, status, fields


class _Column:
    def __init__(self, dtype: str):
        self.dtype = np.dtype(dtype)
        if self.dtype.kind not in COLUMN_KINDS:
            raise ValueError(f"columns hold bool, int or float, not {self.dtype}")
        self.ids: list[str] = []
        self.data = np.zeros(0, dtype=self.dtype)

    def ensure(self, ids) -> None:
        """Add zeroed rows for ids not yet present, keeping ids sorted (one merge, not n inserts)."""
        have = set(self.ids)
        missing = sorted({i for i in ids if i not in have})
        if not missing:
            return
        merged = sorted(self.ids + missing)
        data = np.zeros(len(merged), dtype=self.dtype)
        old = {i: r for r, i in enumerate(self.ids)}
        for r, i in enumerate(merged):
            if i in old:
                data[r] = self.data[old[i]]
        self.ids, self.data = merged, data

    def lookup(self, ids) -> list[int]:
        rows = []
        for i in ids:
            r = bisect.bisect_left(self.ids, i)
            if r == len(self.ids) or self.ids[r] != i:
                raise KeyError(f"no row {i!r}")
            rows.append(r)
        return rows

    def coerce(self, values) -> np.ndarray:
        """Convert exactly to this column's dtype, or raise. Normalises -0.0 to 0.0."""
        raw = np.asarray(values)
        if raw.ndim != 1:
            raise ValueError(f"column values must be one-dimensional, got shape {raw.shape}")
        if raw.size and raw.dtype.kind not in COLUMN_KINDS:
            raise TypeError(f"column values must be numeric, got {raw.dtype}")
        out = raw.astype(self.dtype)
        if out.dtype.kind == "f":
            if not np.isfinite(out).all():
                raise ValueError("column values must be finite")
            out = out + 0.0  # -0.0 -> 0.0, so checkpoints round-trip exactly
        if raw.size and not np.array_equal(out.astype(raw.dtype), raw):
            raise ValueError(f"lossy conversion to {self.dtype}: {values!r}")
        return out


class Store:
    def __init__(self):
        self._entities: dict[str, _Entity] = {}
        self._columns: dict[str, _Column] = {}
        self.deltas: list[StateDelta] = []
        self.bulk_deltas: list[BulkDelta] = []
        self.created: list[dict] = []  # pending: one row per entity created (id, kind, date, event, activation)

    # ------------------------------------------------------------ records

    def create(self, kind: str, entity: str, fields: dict, date: Date, event: str, activation: str = "") -> None:
        _need_name("kind", kind)
        _need_name("entity", entity)
        _need_date(date)
        _need_event(event)
        if entity in self._entities:
            raise ValueError(f"entity {entity!r} already exists")
        fields = _json_copy(fields)
        for name in fields:
            _need_field(name)
        self._entities[entity] = _Entity(kind, "active", fields)
        self.created.append({"id": entity, "kind": kind, "date": date.to_json(), "event": event,
                             "activation": activation})
        self.deltas.append(StateDelta(date, entity, "status", None, "active", event, activation))
        for name in sorted(fields):
            self.deltas.append(StateDelta(date, entity, name, None, fields[name], event, activation))

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
        value = self._entity(entity).fields.get(field, default)
        return _json_copy(value)

    def set(self, entity: str, field: str, value, date: Date, event: str, activation: str = "") -> None:
        _need_field(field)
        _need_date(date)
        _need_event(event)
        record = self._entity(entity)
        value = _json_copy(value)
        old = record.fields.get(field)
        record.fields[field] = value
        self.deltas.append(StateDelta(date, entity, field, old, value, event, activation))

    def set_status(self, entity: str, status: str, date: Date, event: str, activation: str = "") -> None:
        _need_date(date)
        _need_event(event)
        if status not in STATUSES:
            raise ValueError(f"status must be one of {STATUSES}, got {status!r}")
        record = self._entity(entity)
        old, record.status = record.status, status
        self.deltas.append(StateDelta(date, entity, "status", old, status, event, activation))

    # ------------------------------------------------------------ columns

    def add_column(self, name: str, dtype: str) -> None:
        _need_name("column", name)
        if name in self._columns:
            raise ValueError(f"column {name!r} already exists")
        self._columns[name] = _Column(dtype)

    def read_column(self, name: str, ids) -> np.ndarray:
        col = self._columns[name]
        return col.data[col.lookup(ids)].copy()

    def write_column(self, name: str, ids, values, date: Date, event: str, activation: str = "") -> None:
        _need_date(date)
        _need_event(event)
        col = self._columns[name]
        ids = [_need_name("id", i) for i in ids]
        values = col.coerce(values)
        if len(ids) != len(values) or len(set(ids)) != len(ids):
            raise ValueError("write_column needs one value per distinct id")
        order = sorted(range(len(ids)), key=ids.__getitem__)
        sorted_ids = tuple(ids[i] for i in order)
        values_hash = digest([col.dtype.name, values[order].tolist()], size=16)
        # Everything is validated: now mutate.
        col.ensure(ids)
        col.data[col.lookup(ids)] = values
        self.bulk_deltas.append(BulkDelta(date, name, sorted_ids, values_hash, event, activation))

    def write_columns(self, entity: str, values: dict, date: Date, event: str, activation: str = "") -> None:
        """Set several columns for one entity as a single change (one bulk delta, not one per column)."""
        _need_date(date)
        _need_event(event)
        _need_name("id", entity)
        if not values:
            raise ValueError("write_columns needs at least one column")
        names = sorted(values)
        coerced = {}
        for name in names:
            if name not in self._columns:
                raise KeyError(f"no column {name!r}")
            coerced[name] = self._columns[name].coerce([values[name]])
        values_hash = digest([[n, self._columns[n].dtype.name, coerced[n].tolist()] for n in names], size=16)
        for name in names:  # everything is validated: now mutate
            col = self._columns[name]
            col.ensure([entity])
            col.data[col.lookup([entity])] = coerced[name]
        self.bulk_deltas.append(BulkDelta(date, "", (entity,), values_hash, event, activation, tuple(names)))

    # ------------------------------------------------------------ deltas

    def drain(self) -> tuple[list[StateDelta], list[BulkDelta]]:
        """Hand pending deltas to the run-folder writer and forget them."""
        out = (self.deltas, self.bulk_deltas)
        self.deltas, self.bulk_deltas, self.created = [], [], []
        return out

    # ------------------------------------------------------------ JSON (checkpoint state)

    def to_json(self) -> dict:
        """A detached snapshot of state. Pending deltas are history, not state, and are excluded."""
        return _json_copy({
            "entities": [{"id": i, "kind": e.kind, "status": e.status, "fields": e.fields}
                         for i, e in sorted(self._entities.items())],
            "columns": {name: {"dtype": col.dtype.name, "ids": list(col.ids), "data": col.data.tolist()}
                        for name, col in sorted(self._columns.items())},
        })

    @classmethod
    def from_json(cls, data: dict) -> Store:
        store = cls()
        for row in data["entities"]:
            if row["status"] not in STATUSES:
                raise ValueError(f"bad status in checkpoint: {row!r}")
            if row["id"] in store._entities:
                raise ValueError(f"duplicate entity in checkpoint: {row['id']!r}")
            store._entities[row["id"]] = _Entity(row["kind"], row["status"], _json_copy(row["fields"]))
        for name, col in data["columns"].items():
            c = _Column(col["dtype"])
            if col["ids"] != sorted(set(col["ids"])) or len(col["ids"]) != len(col["data"]):
                raise ValueError(f"column {name!r} in checkpoint is not sorted, unique and aligned")
            c.ids, c.data = list(col["ids"]), c.coerce(col["data"])
            store._columns[name] = c
        return store
