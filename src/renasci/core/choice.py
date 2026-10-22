"""Choosing among candidates without coupling unrelated people.

Rendezvous (highest-random-weight) choice: every candidate gets a score from a hash of
(key, candidate), and the best score wins. Adding or removing a candidate only changes the result
if that candidate would have won. Greedy list-order picks, by contrast, couple everyone in the list.

`match` pairs seekers with targets by Gale–Shapley, with both sides' preferences drawn from
rendezvous scores. The result is unique for given preferences, so the order seekers are processed
in never matters, and separate markets never affect each other.
"""

from __future__ import annotations

import hashlib
import math

from renasci.core.canon import canonical


def _u(key: list, candidate: str) -> float:
    """A uniform number in (0, 1) from the hash of (key, candidate)."""
    h = hashlib.blake2b(canonical([key, candidate]).encode(), digest_size=16).digest()
    return (int.from_bytes(h, "big") + 0.5) / 2**128


def _scores(key: list, candidates, weights) -> list[tuple[float, str]]:
    candidates = list(candidates)
    for c in candidates:
        if not isinstance(c, str) or not c:
            raise ValueError(f"candidates must be non-empty strings, got {c!r}")
    if len(set(candidates)) != len(candidates):
        raise ValueError("candidates must be distinct")
    if weights is None:
        return [(_u(key, c), c) for c in candidates]
    weights = [float(w) for w in weights]
    if len(weights) != len(candidates):
        raise ValueError("one weight per candidate")
    if any(not math.isfinite(w) or w < 0 for w in weights) or (candidates and sum(weights) <= 0):
        raise ValueError(f"weights must be finite, non-negative, with a positive sum: {weights}")
    # -log(u)/w: the minimum wins with probability proportional to w. Zero weight never wins.
    return [(-math.log(_u(key, c)) / w, c) for c, w in zip(candidates, weights) if w > 0]


def rank(key: list, candidates, weights=None) -> list[str]:
    """All candidates (with positive weight), best first."""
    return [c for _, c in sorted(_scores(key, candidates, weights))]


def rendezvous(key: list, candidates, weights=None) -> str | None:
    """The winning candidate, or None if there are none."""
    ranked = rank(key, candidates, weights)
    return ranked[0] if ranked else None


def match(key: list, seekers: dict[str, list[str]]) -> dict[str, str]:
    """Pair seekers with targets (each target at most once). Unmatched seekers are left out."""
    prefs = {}
    for s in sorted(seekers):
        targets = list(seekers[s])
        if s in targets:
            raise ValueError(f"{s!r} cannot seek itself")
        prefs[s] = rank([*key, "seek", s], targets)
    nxt = {s: 0 for s in prefs}
    holder: dict[str, str] = {}  # target -> seeker it currently holds
    free = sorted(prefs)
    while free:
        s = free.pop(0)
        if nxt[s] >= len(prefs[s]):
            continue  # nobody left to ask
        t = prefs[s][nxt[s]]
        nxt[s] += 1
        current = holder.get(t)
        if current is None:
            holder[t] = s
        elif _u([*key, "accept", t], s) < _u([*key, "accept", t], current):
            holder[t] = s
            free.append(current)
            free.sort()
        else:
            free.append(s)
            free.sort()
    return {s: t for t, s in sorted(holder.items(), key=lambda item: item[1])}
