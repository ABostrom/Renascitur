"""Keyed, counter-based randomness.

Every draw comes from a stream named by what it is for:
`(seed, system, entity, purpose, canonical_tick, occurrence, salt)`. The name is hashed into a
128-bit Philox key. No global sequence exists, so a change in one place never shifts the draws of
an unrelated one. `occurrence` is counted locally by an `OrdinalTable` (the n-th stream opened for
the same `(system, entity, purpose, tick)`), never globally. Systems obtain streams only through
`KeyedRng.open`, which counts the occurrence and builds the stream in one step.

A stream lives inside a single activation. Checkpoints fall between activations, so no stream is
ever open across one and streams need no saved position.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

import numpy as np

Tick = tuple[int, int, int]


def _is_int(x) -> bool:
    return type(x) is int


def _check_name(label: str, value) -> str:
    if not isinstance(value, str) or not value:
        raise TypeError(f"{label} must be a non-empty string, got {value!r}")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as err:
        raise TypeError(f"{label} is not valid unicode: {value!r}") from err
    return value


def _check_tick(tick) -> Tick:
    """Accept a tuple or a JSON list; return a tuple."""
    if isinstance(tick, list):
        tick = tuple(tick)
    if not (isinstance(tick, tuple) and len(tick) == 3 and all(_is_int(x) for x in tick)):
        raise TypeError(f"tick must be (age, year, quarter) ints, got {tick!r}")
    return tick


@dataclass(frozen=True)
class Reshuffle:
    """From `from_tick` on, every key is salted, which re-rolls all later history on purpose."""

    from_tick: Tick
    salt: str

    def __post_init__(self):
        object.__setattr__(self, "from_tick", _check_tick(self.from_tick))
        if not isinstance(self.salt, str) or not self.salt:
            raise ValueError(f"a reshuffle needs a non-empty salt, got {self.salt!r}")

    def to_json(self) -> dict:
        return {"from": list(self.from_tick), "salt": self.salt}

    @classmethod
    def from_json(cls, data: dict) -> Reshuffle:
        return cls(data["from"], data["salt"])


class Stream:
    """A deterministic sequence of draws. A thin wrapper over a NumPy Philox Generator."""

    def __init__(self, key: int):
        self._gen = np.random.Generator(np.random.Philox(key=key))

    def random(self, size=None):
        return self._gen.random(size)

    def integers(self, low, high, size=None):
        return self._gen.integers(low, high, size=size)

    def normal(self, loc=0.0, scale=1.0, size=None):
        return self._gen.normal(loc, scale, size)

    def choice_index(self, weights) -> int:
        """Pick an index with probability proportional to its weight."""
        w = np.asarray(weights, dtype=float)
        with np.errstate(over="ignore"):  # an overflowing sum is rejected just below
            total = w.sum() if w.size else 0.0
        if w.size == 0 or not np.isfinite(w).all() or (w < 0).any() or not 0 < total < np.inf:
            raise ValueError(f"weights must be finite, non-negative, with a positive sum: {weights!r}")
        cumulative = np.cumsum(w)
        u = self._gen.random() * cumulative[-1]
        return min(int(np.searchsorted(cumulative, u, side="right")), w.size - 1)


class KeyedRng:
    def __init__(self, seed: int, reshuffles: tuple[Reshuffle, ...] = ()):
        if not _is_int(seed):
            raise TypeError(f"seed must be an int, got {seed!r}")
        self.seed = seed
        # Sorted by (tick, salt), so the order a recipe lists them in never matters.
        self.reshuffles = tuple(sorted(reshuffles, key=lambda r: (r.from_tick, r.salt)))

    def salt_for(self, tick: Tick) -> str:
        """Every reshuffle at or before `tick`, chained, so each one re-rolls again."""
        return "|".join(r.salt for r in self.reshuffles if r.from_tick <= tick)

    def key(self, system: str, entity: str, purpose: str, tick: Tick, occurrence: int) -> int:
        _check_name("system", system)
        _check_name("entity", entity)  # every stream has an owner; no entity=None streams
        _check_name("purpose", purpose)
        tick = _check_tick(tick)
        if not _is_int(occurrence) or occurrence < 0:
            raise TypeError(f"occurrence must be a non-negative int, got {occurrence!r}")
        # JSON list encoding keeps the parts unambiguous ("ab","c" never equals "a","bc").
        parts = [self.seed, system, entity, purpose, list(tick), occurrence, self.salt_for(tick)]
        blob = json.dumps(parts, separators=(",", ":"), ensure_ascii=False).encode()
        return int.from_bytes(hashlib.blake2b(blob, digest_size=16).digest(), "big")

    def stream(self, system: str, entity: str, purpose: str, tick: Tick, occurrence: int) -> Stream:
        """A stream for an explicit occurrence. Systems should use `open` instead."""
        return Stream(self.key(system, entity, purpose, tick, occurrence))

    def open(self, table: OrdinalTable, system: str, entity: str, purpose: str, tick: Tick) -> Stream:
        """Count the next occurrence and return its stream: the one entry point for systems."""
        occurrence = table.next(system, entity, purpose, tick)
        return self.stream(system, entity, purpose, tick, occurrence)


class OrdinalTable:
    """Counts streams opened per (system, entity, purpose, tick). Checkpointed as sorted JSON."""

    def __init__(self):
        self._counts: dict[tuple[str, str, str, Tick], int] = {}

    @staticmethod
    def _key(system, entity, purpose, tick) -> tuple[str, str, str, Tick]:
        return (
            _check_name("system", system),
            _check_name("entity", entity),
            _check_name("purpose", purpose),
            _check_tick(tick),
        )

    def next(self, system: str, entity: str, purpose: str, tick: Tick) -> int:
        k = self._key(system, entity, purpose, tick)
        n = self._counts.get(k, 0)
        self._counts[k] = n + 1
        return n

    def close_before(self, tick: Tick) -> None:
        """Forget counts for ticks that have ended."""
        tick = _check_tick(tick)
        self._counts = {k: n for k, n in self._counts.items() if k[3] >= tick}

    def to_json(self) -> list:
        return [[s, e, p, list(t), n] for (s, e, p, t), n in sorted(self._counts.items())]

    @classmethod
    def from_json(cls, data: list) -> OrdinalTable:
        table = cls()
        for s, e, p, t, n in data:
            k = cls._key(s, e, p, t)
            if k in table._counts:
                raise ValueError(f"duplicate ordinal row {k}")
            if not _is_int(n) or n < 1:
                raise ValueError(f"ordinal count must be a positive int, got {n!r}")
            table._counts[k] = n
        return table
