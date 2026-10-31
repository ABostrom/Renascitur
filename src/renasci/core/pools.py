"""Pools: the one way any modular list in the engine is kept and extended (#162).

A `Pool` holds the entries of one kind (actions, ambitions, ...) by key. It reads as a mapping, always in
sorted key order, so the order things were registered in can never reach a draw. Two entries with one key are
refused, and a frozen pool refuses additions, so a class defined later (in a test) never leaks into a run.

`Pools` is the overarching registry: every pool by name, so a new kind of content is one `define` and needs no
new mechanism. `pools` is the base set, which modules fill as they load and then freeze.

**Extensions.** An extension is a module with `extend(pools)`, named by a recipe (`extensions = ["my_beats"]`).
`load` calls it with an open copy of the base and freezes the result, which is that engine's own set (`ctx.pools`).
The base never changes, so one engine's extensions can't reach another, and nothing is scanned from a folder, so
a file nobody named can't change a run.
"""

from __future__ import annotations

import hashlib
import importlib
import os
import re
import sys
from collections.abc import Callable, Iterator, Mapping
from pathlib import Path
from typing import Any

BASE = "base"
EXTENSION = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*")
HOMES = ("renasci.people.actions", "renasci.people.ambitions")  # (what defines the base pools: see `base`)


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

    def claim(self, keys, source: str) -> None:
        """Record where these entries came from."""
        self._sources.update(dict.fromkeys(keys, source))

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
        if hasattr(type(self), name):
            raise ValueError(f"a pool can't be named {name!r}: it would hide `Pools.{name}`")
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
pools.define("event_types").freeze()  # (those extensions add; the engine's own stay with their systems for now)


def base() -> Pools:
    """The base set, whatever has been imported so far (`pools` only holds what has)."""
    for home in HOMES:
        importlib.import_module(home)
    return pools


def load(names=()) -> Pools:
    """The base plus the named extensions, frozen: one engine's own set. Names are imported from the working
    directory as well as the usual path."""
    found = base().snapshot()
    for name in names:
        before = {n: set(found[n]) for n in found}
        _module(name).extend(found)
        for n in found:
            found[n].claim(set(found[n]) - before.get(n, set()), name)
    for n in found:
        found[n].freeze()
    return found


def _module(name: str):
    if not EXTENSION.fullmatch(name):
        raise ValueError(f"an extension is a module name, got {name!r}")
    here = os.getcwd()
    sys.path.insert(0, here)
    try:
        module = importlib.import_module(name)
    except ModuleNotFoundError as e:
        raise ValueError(f"no extension named {name!r}: {e}") from None
    finally:
        sys.path.remove(here)
    if not callable(getattr(module, "extend", None)):
        raise ValueError(f"extension {name!r} has no `extend(pools)`")
    return module


def source_digest(name: str) -> str:
    """A digest of an extension's source, so an edited extension is a different recipe. It covers what the
    extension could import from beside itself: a package's whole tree, or a lone module's folder. That can flag an
    unrelated file in that folder; it can't miss a helper."""
    file = Path(_module(name).__file__)
    folder = file.parent
    files = folder.rglob("*.py") if file.name == "__init__.py" else folder.glob("*.py")
    h = hashlib.sha256()
    for path in sorted(files, key=lambda p: p.relative_to(folder).as_posix()):
        h.update(path.relative_to(folder).as_posix().encode())
        h.update(path.read_bytes().replace(b"\r\n", b"\n"))
    return h.hexdigest()[:16]


def digests(names) -> list[list[str]]:
    """[[name, source digest], ...]: what a recipe and a manifest record of the extensions."""
    return [[n, source_digest(n)] for n in names]
