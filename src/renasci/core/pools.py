"""Pools: the one way any modular list in the engine is kept and extended (#162).

A `Pool` holds the entries of one kind (actions, ambitions, ...) by key. It reads as a mapping, always in
sorted key order, so the order things were registered in can never reach a draw. Two entries with one key are
refused, and a frozen pool refuses additions, so a class defined later (in a test) never leaks into a run.

`Pools` is the overarching registry: every pool by name, so a new kind of content is one `define` and needs no
new mechanism. `pools` is the base set, which modules fill as they load and then freeze. `snapshot` gives an
open copy of everything, the seam an extension registers into without touching the base.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from typing import Any

BASE = "base"


def _name(entry: Any) -> str:
    return entry.name


class Pool(Mapping):
    def __init__(self, name: str, key: Callable[[Any], str] = _name):
        self.name, self.key = name, key
        self.frozen = False
        self._entries: dict[str, Any] = {}
        self._sources: dict[str, str] = {}

    def add(self, entry: Any, source: str = BASE) -> Any:
        """Add an entry and hand it back, so this works as a class decorator. A class joins as an instance."""
        item = entry() if isinstance(entry, type) else entry
        if self.frozen:
            raise ValueError(f"pool {self.name!r} is frozen: extend a snapshot instead")
        key = self.key(item)
        if not key:
            raise ValueError(f"an entry for pool {self.name!r} has no key")
        if key in self._entries:
            raise ValueError(f"pool {self.name!r} already has {key!r}")
        self._entries[key], self._sources[key] = item, source
        return entry

    def freeze(self) -> None:
        self.frozen = True

    def copy(self) -> Pool:
        """An open copy: the source stays as it is."""
        new = Pool(self.name, self.key)
        new._entries, new._sources = dict(self._entries), dict(self._sources)
        return new

    def sources(self) -> dict[str, str]:
        """Where each entry came from, by key."""
        return {k: self._sources[k] for k in self}

    def __getitem__(self, key: str) -> Any:
        try:
            return self._entries[key]
        except KeyError:
            raise KeyError(f"pool {self.name!r} has no {key!r}") from None

    def __iter__(self) -> Iterator[str]:
        return iter(sorted(self._entries))

    def __len__(self) -> int:
        return len(self._entries)

    def __repr__(self) -> str:
        return f"Pool({self.name!r}, {list(self)})"


class Pools(Mapping):
    def __init__(self):
        self._pools: dict[str, Pool] = {}

    def define(self, name: str, key: Callable[[Any], str] = _name) -> Pool:
        if name in self._pools:
            raise ValueError(f"pool {name!r} is already defined")
        self._pools[name] = Pool(name, key)
        return self._pools[name]

    def snapshot(self) -> Pools:
        """An open copy of every pool."""
        new = Pools()
        new._pools = {n: p.copy() for n, p in self._pools.items()}
        return new

    def describe(self) -> dict[str, dict[str, str]]:
        """Every pool's entries and where each came from: what a run was built with."""
        return {n: self._pools[n].sources() for n in self}

    def __getattr__(self, name: str) -> Pool:
        if name != "_pools" and name in self._pools:
            return self._pools[name]
        raise AttributeError(f"no pool named {name!r}")

    def __getitem__(self, name: str) -> Pool:
        return self._pools[name]

    def __iter__(self) -> Iterator[str]:
        return iter(sorted(self._pools))

    def __len__(self) -> int:
        return len(self._pools)


pools = Pools()
