"""Fix data inconsistencies that broke the folder restructure.

Issues observed in the partial restructure:
  1. type: city — Aaron's older convention. Normalise to type: settlement.
  2. lineage values with full-path wikilinks like
     '[[docs/Races/Kyojin/Leonin/Leonin|Leonin]]' — strip to canonical
     lineage name from the 5-set: Humans, Grundthains, Kyojin, Solarans,
     Engineered.
  3. lineage values like 'Mortal Race', 'Engineered Race' — normalise.
  4. parent_race values with full-path wikilinks — strip to just the
     race name.

After this normalisation, the restructure script can be re-run cleanly.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Dict

# Allow running as a script from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from refactor.common import iter_md_files, read_frontmatter, write_frontmatter, rel_to_docs


# Lineage value normalisation map.
LINEAGE_NORMALIZE: Dict[str, str] = {
    "Mortal Race":     "Humans",
    "Mortal race":     "Humans",
    "mortal-descendant": "Humans",
    "Human":           "Humans",
    "Solaran":         "Solarans",
    "Grundthain":      "Grundthains",
    "Dwarves":         "Grundthains",
    "Dwarf":           "Grundthains",
    "Engineered Race": "Engineered",
    "Orc":             "Kyojin",
    "Orcs":            "Kyojin",
    "Leonin":          "Kyojin",
    "Imperial Leonin": "Kyojin",
    "Imperial Orcs":   "Kyojin",
}

# Acceptable final lineage values
CANONICAL_LINEAGES = {"Humans", "Grundthains", "Kyojin", "Solarans", "Engineered"}


def _strip_wikilink(s: str) -> str:
    if not isinstance(s, str):
        return ""
    s = s.strip()
    if s.startswith("[[") and s.endswith("]]"):
        inner = s[2:-2]
        if "|" in inner:
            # Last segment after | (the display alias) is usually the cleanest name
            inner = inner.split("|", 1)[1]
        if "/" in inner:
            inner = inner.split("/")[-1]
        return inner
    return s


def normalise_lineage(raw) -> str:
    if not isinstance(raw, str):
        return ""
    candidate = _strip_wikilink(raw).strip()
    if not candidate:
        return ""
    # Direct map?
    if candidate in LINEAGE_NORMALIZE:
        return LINEAGE_NORMALIZE[candidate]
    if candidate in CANONICAL_LINEAGES:
        return candidate
    # Last-resort: title-case + plural-ish fallback
    return candidate


def normalise_parent_race(raw) -> str:
    if not isinstance(raw, str):
        return ""
    stripped = _strip_wikilink(raw).strip()
    if not stripped:
        return ""
    # Wrap in wikilink for consistency
    return "[[{}]]".format(stripped)


def main() -> None:
    files_changed = 0
    fixes = {"type": 0, "lineage": 0, "parent_race": 0}

    for md in iter_md_files():
        meta, body = read_frontmatter(md)
        original = dict(meta)

        # Fix type: city -> settlement
        if meta.get("type") == "city":
            meta["type"] = "settlement"

        # Fix lineage
        if meta.get("type") == "race":
            lineage = meta.get("lineage", "")
            new_lin = normalise_lineage(lineage)
            if new_lin and new_lin != lineage:
                meta["lineage"] = new_lin

            # Fix parent_race
            parent_race = meta.get("parent_race", "")
            new_pr = normalise_parent_race(parent_race) if parent_race else ""
            if new_pr and new_pr != parent_race:
                meta["parent_race"] = new_pr

        # Detect changes
        changed = False
        for k in ("type", "lineage", "parent_race"):
            if meta.get(k) != original.get(k):
                fixes[k] = fixes.get(k, 0) + 1
                changed = True
        if changed:
            write_frontmatter(md, meta, body)
            files_changed += 1
            print("Fixed: {}".format(rel_to_docs(md)))

    print("---")
    print("Files changed: {}".format(files_changed))
    for k, v in fixes.items():
        if v:
            print("  {}: {}".format(k, v))


if __name__ == "__main__":
    main()
