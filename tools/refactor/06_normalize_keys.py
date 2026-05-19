"""Normalize hyphenated frontmatter keys to underscore_case.

Dataview can parse `field-name` as `field MINUS name` in WHERE/TABLE
clauses. Underscore form avoids this ambiguity. Aaron's existing
convention is also underscore (`inhabited_by`, `faction_control`).

Special exception: keys starting with `aat-` are the
aprils-automatic-timelines plugin's convention; those stay as-is.

Idempotent: re-running on already-normalized files is a no-op.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running as a script from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from refactor.common import iter_md_files, read_frontmatter, write_frontmatter

# Keys that stay hyphenated (third-party plugin conventions).
PRESERVE_PREFIXES = ("aat-",)


def normalize_key(key: str) -> str:
    if any(key.startswith(p) for p in PRESERVE_PREFIXES):
        return key
    if "-" in key:
        return key.replace("-", "_")
    return key


def normalize_meta(meta: dict) -> tuple:
    """Return (new_meta, changed_count). Preserves key order."""
    new_meta = {}
    changed = 0
    for k, v in meta.items():
        nk = normalize_key(k)
        if nk != k:
            changed += 1
        # If both old and new key exist, the new key wins (later overrides).
        new_meta[nk] = v
    return new_meta, changed


def main() -> None:
    files_changed = 0
    keys_renamed = 0
    for md in iter_md_files():
        meta, body = read_frontmatter(md)
        if not meta:
            continue
        new_meta, changed = normalize_meta(meta)
        if changed > 0:
            write_frontmatter(md, new_meta, body)
            files_changed += 1
            keys_renamed += changed
    print("Files changed: {}".format(files_changed))
    print("Keys renamed: {}".format(keys_renamed))


if __name__ == "__main__":
    main()
