"""Canonical JSON: one exact text form for any engine value.

Sorted keys, no whitespace, floats as Python's shortest round-trip repr (exact for float64),
`-0.0` normalised, NaN/inf and sets rejected. Hashes, deltas and checkpoints all use this.
"""

from __future__ import annotations

import hashlib
import json

import numpy as np


def plain(value):
    """Convert to plain JSON types, rejecting anything without one exact JSON form."""
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, np.generic):
        return plain(value.item())
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            raise ValueError(f"non-finite float has no canonical form: {value!r}")
        return 0.0 if value == 0.0 else value
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if not isinstance(k, str):
                raise TypeError(f"JSON object keys must be strings, got {k!r}")
            out[k] = plain(v)
        return out
    to_json = getattr(value, "to_json", None)
    if callable(to_json):
        return plain(to_json())
    raise TypeError(f"{type(value).__name__} has no canonical JSON form: {value!r}")


def canonical(value) -> str:
    if value is None or type(value) in (str, int, bool):  # the common case, same text, less work
        return json.dumps(value, ensure_ascii=False)
    return json.dumps(plain(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def digest(value, size: int = 8) -> str:
    """Hex blake2b of the canonical form."""
    return hashlib.blake2b(canonical(value).encode(), digest_size=size).hexdigest()
