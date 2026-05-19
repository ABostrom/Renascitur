"""Targeted inference of confident property values.

Goes through specific known cases and sets values that are
unambiguously correct from context. Designed to override DEFAULTS
(like nature: divine for every deity) when the more specific
answer is known.

Cases handled:
- pantheon = Elementals  -> nature = elemental
- pantheon = The God Hand -> nature = corrupted
- lineage = Engineered    -> nature = bioengineered (race files)
- race lineage = Solarans -> nature = celestial (debatable; Aaron may revise)
- type = chronicle        -> nature = mortal (mortal-authored documents)

Specific files outside the type-default pattern. Conservative.

Idempotent.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Tuple, Any

# Allow running as a script from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from refactor.common import iter_md_files, read_frontmatter, write_frontmatter, rel_to_docs


def overrides_for(meta: dict, relpath: str = "") -> Dict[str, Any]:
    """Return field overrides justified by inference, or {}."""
    out: Dict[str, Any] = {}
    type_ = meta.get("type")
    pantheon = meta.get("pantheon", "")
    lineage = meta.get("lineage", "")

    # Pantheon-driven overrides (override default nature: divine)
    if isinstance(pantheon, str):
        if pantheon == "[[Elementals]]" or pantheon == "Elementals":
            out["nature"] = "elemental"
        elif pantheon == "[[The God Hand]]":
            out["nature"] = "corrupted"

    # Path-based: God Hand entries live under Corruption/The God Hand/
    # and don't have pantheon set (typed cosmic-force not deity).
    if "Cosmology/Creation/Corruption/The God Hand/" in relpath:
        out["nature"] = "corrupted"
        out["alignment"] = "chaotic-evil"

    # Aberrations + Ishna + Quintumvirate folder
    if "/Corruption/" in relpath and "The God Hand" not in relpath:
        # Top-level Corruption entries (Aberrations, Ishna, Quintumvirate)
        out["nature"] = "aberrant"

    # Race lineage-driven
    if type_ == "race":
        if lineage in ("Engineered", "engineered"):
            out["nature"] = "bioengineered"
        elif lineage in ("Solarans", "solarans"):
            out["nature"] = "celestial"  # debatable; Aaron may revise
        elif lineage in ("Kyojin", "kyojin"):
            out.setdefault("nature", "mortal")
        elif lineage in ("Humans", "humans"):
            out.setdefault("nature", "mortal")
        elif lineage in ("Grundthains", "grundthains"):
            out.setdefault("nature", "mortal")

    return out


def apply_overrides(meta: dict, overrides: Dict[str, Any]) -> Tuple[dict, int]:
    """Apply overrides regardless of current value (they're confident).
    Returns (new_meta, count_changed)."""
    out = dict(meta)
    changed = 0
    for k, v in overrides.items():
        if out.get(k) != v:
            out[k] = v
            changed += 1
    return out, changed


def main() -> None:
    files_changed = 0
    fields_overridden = 0
    by_nature: Dict[str, int] = {}

    for md in iter_md_files():
        meta, body = read_frontmatter(md)
        rel = rel_to_docs(md)
        overrides = overrides_for(meta, rel)
        if not overrides:
            continue
        new_meta, changed = apply_overrides(meta, overrides)
        if changed == 0:
            continue
        write_frontmatter(md, new_meta, body)
        files_changed += 1
        fields_overridden += changed
        nat = overrides.get("nature")
        if nat:
            by_nature[nat] = by_nature.get(nat, 0) + 1

    print("Files changed: {}".format(files_changed))
    print("Fields overridden: {}".format(fields_overridden))
    print("Nature inferences applied:")
    for n, c in sorted(by_nature.items(), key=lambda kv: -kv[1]):
        print("  {:18s} {:5d}".format(n, c))


if __name__ == "__main__":
    main()
