"""Choosing among candidates without coupling unrelated people.

Rendezvous (highest-random-weight) choice: every candidate gets a score from a hash of
(key, candidate), and the best score wins. Adding or removing a candidate only changes the result
if that candidate would have won. Greedy list-order picks, by contrast, couple everyone in the list.

`match` pairs seekers with targets in rounds. Each round, every free seeker proposes to its
rendezvous pick among the targets still free, and each target accepts its rendezvous-best suitor.
Losers try again next round (keyed by round). There is no displacement cascade, so a seeker or
target who ends up unmatched never changes anyone else's pair, and separate markets never touch.
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


def scored(key: list, candidates, weights=None) -> list[tuple[float, str]]:
    """(score, candidate) pairs, best (lowest) first. Zero-weight candidates are left out."""
    return sorted(_scores(key, candidates, weights))


def rank(key: list, candidates, weights=None) -> list[str]:
    """All candidates (with positive weight), best first."""
    return [c for _, c in scored(key, candidates, weights)]


def rendezvous(key: list, candidates, weights=None) -> str | None:
    """The winning candidate, or None if there are none."""
    ranked = rank(key, candidates, weights)
    return ranked[0] if ranked else None


def _options(spec) -> tuple[list[str], list[float] | None]:
    if isinstance(spec, dict):
        names = sorted(spec)
        return names, [spec[n] for n in names]
    return list(spec), None


def match(key: list, seekers: dict, accept: dict[str, dict[str, float]] | None = None) -> dict[str, str]:
    """Pair seekers with targets, each target at most once. Unmatched seekers are left out.

    `seekers` maps each seeker to a list of targets, or to {target: weight} for weighted
    preferences. `accept` optionally maps a target to {seeker: weight} for weighted acceptance
    (seekers not listed weigh 1). Seekers and targets must be different people.
    """
    options = {s: _options(seekers[s]) for s in sorted(seekers)}
    targets = {t for names, _ in options.values() for t in names}
    both = sorted(targets & set(options))
    if both:
        raise ValueError(f"seekers cannot also be targets: {both}")
    accept = accept or {}
    result: dict[str, str] = {}
    taken: dict[str, None] = {}
    free = sorted(options)
    rnd = 0
    while True:
        proposals: dict[str, list[str]] = {}
        for s in free:
            names, weights = options[s]
            open_idx = [i for i, t in enumerate(names) if t not in taken]
            w = [weights[i] for i in open_idx] if weights is not None else None
            if not open_idx or (w is not None and sum(w) <= 0):
                continue
            pick = rendezvous([*key, "seek", s, rnd], [names[i] for i in open_idx], w)
            proposals.setdefault(pick, []).append(s)
        if not proposals:
            break
        for t in sorted(proposals):
            suitors = proposals[t]
            w = [float(accept[t].get(s, 1.0)) for s in suitors] if t in accept else None
            if w is not None and any(x <= 0 for x in w):
                raise ValueError(f"accept weights must be positive (target {t!r})")
            winner = rendezvous([*key, "accept", t, rnd], suitors, w)
            result[winner] = t
            taken[t] = None
        free = [s for s in free if s not in result]
        rnd += 1
    return {s: result[s] for s in sorted(result)}
