"""Keyed, counter-based randomness.

Every draw comes from a stream named by what it is for:
`(seed, system, entity, purpose, canonical_tick, occurrence, salt)`. The name is hashed into a
128-bit Philox key. No global sequence exists, so a change in one place never shifts the draws of
an unrelated one. `occurrence` is counted locally by an `OrdinalTable` (the n-th stream opened for
the same `(system, entity, purpose, tick)`), never globally.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

import numpy as np

Tick = tuple[int, int, int]


def _is_int(x) -> bool:
    return type(x) is int


def _check_name(label: str, value) -> None:
    if not isinstance(value, str) or not value:
        raise TypeError(f"{label} must be a non-empty string, got {value!r}")


def _check_tick(tick) -> Tick:
    if not (isinstance(tick, tuple) and len(tick) == 3 and all(_is_int(x) for x in tick)):
        raise TypeError(f"tick must be an (age, year, quarter) tuple of ints, got {tick!r}")
    return tick


@dataclass(frozen=True)
class Reshuffle:
    """From `from_tick` on, every key is salted, which re-rolls all later history on purpose."""

    from_tick: Tick
    salt: str


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
        if w.size == 0 or (w < 0).any() or w.sum() <= 0:
            raise ValueError(f"weights must be non-negative with a positive sum: {weights!r}")
        cumulative = np.cumsum(w)
        u = self._gen.random() * cumulative[-1]
        return int(np.searchsorted(cumulative, u, side="right"))


class KeyedRng:
    def __init__(self, seed: int, reshuffles: tuple[Reshuffle, ...] = ()):
        if not _is_int(seed):
            raise TypeError(f"seed must be an int, got {seed!r}")
        self.seed = seed
        self.reshuffles = tuple(sorted(reshuffles, key=lambda r: r.from_tick))

    def salt_for(self, tick: Tick) -> str:
        salt = ""
        for r in self.reshuffles:
            if r.from_tick <= tick:
                salt = r.salt
        return salt

    def key(self, system: str, entity: str, purpose: str, tick: Tick, occurrence: int) -> int:
        _check_name("system", system)
        _check_name("entity", entity)  # every stream has an owner; no entity=None streams
        _check_name("purpose", purpose)
        _check_tick(tick)
        if not _is_int(occurrence) or occurrence < 0:
            raise TypeError(f"occurrence must be a non-negative int, got {occurrence!r}")
        # JSON list encoding keeps the parts unambiguous ("ab","c" never equals "a","bc").
        parts = [self.seed, system, entity, purpose, list(tick), occurrence, self.salt_for(tick)]
        blob = json.dumps(parts, separators=(",", ":"), ensure_ascii=False).encode()
        return int.from_bytes(hashlib.blake2b(blob, digest_size=16).digest(), "big")

    def stream(self, system: str, entity: str, purpose: str, tick: Tick, occurrence: int) -> Stream:
        return Stream(self.key(system, entity, purpose, tick, occurrence))


class OrdinalTable:
    """Counts streams opened per (system, entity, purpose, tick). Checkpointed as sorted JSON."""

    def __init__(self):
        self._counts: dict[tuple[str, str, str, Tick], int] = {}

    def next(self, system: str, entity: str, purpose: str, tick: Tick) -> int:
        k = (system, entity, purpose, _check_tick(tick))
        n = self._counts.get(k, 0)
        self._counts[k] = n + 1
        return n

    def close_before(self, tick: Tick) -> None:
        """Forget counts for ticks that have ended."""
        self._counts = {k: n for k, n in self._counts.items() if k[3] >= tick}

    def to_json(self) -> list:
        return [[s, e, p, list(t), n] for (s, e, p, t), n in sorted(self._counts.items())]

    @classmethod
    def from_json(cls, data: list) -> OrdinalTable:
        table = cls()
        for s, e, p, t, n in data:
            table._counts[(s, e, p, tuple(t))] = n
        return table
