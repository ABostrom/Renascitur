"""Checkpoint files: one canonical JSON document, gzipped, written atomically. No pickle."""

from __future__ import annotations

import gzip
import json
import os
from pathlib import Path

from renasci.core.canon import canonical


def save_checkpoint(path, checkpoint: dict) -> None:
    path = Path(path)
    data = bytearray(gzip.compress(canonical(checkpoint).encode("utf-8"), compresslevel=9, mtime=0))
    data[9] = 0xFF  # platform-independent gzip header
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(bytes(data))
    os.replace(tmp, path)


def load_checkpoint(path) -> dict:
    return json.loads(gzip.decompress(Path(path).read_bytes()).decode("utf-8"))
