"""Infer character.race from affiliation, then chain character.nature.

Most characters live in `Societies/<society>/...` folders, and the
society strongly implies the character's race (Saurian Enclave members
are Saurians, Tidebound members are Dwarves, etc.). With race set,
nature inherits from the race file.

Also covers:
  - character.culture inference from affiliation chain
  - character.location inference from settlement folder context (where path is
    Societies/<society>/.../Characters/<NPC>.md and society has known seat,
    use that as location)

Merge-only, idempotent.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, Optional

# Allow running as a script from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from refactor.common import iter_md_files, read_frontmatter, write_frontmatter, rel_to_docs


# Affiliation (the wikilink value used in `affiliation:`) -> likely race wikilink.
AFFILIATION_TO_RACE: Dict[str, str] = {
    "[[Saurian Enclave]]":            "[[Saurian]]",
    "[[The Tidebound of Draumhavn]]": "[[Dwarf]]",
    "[[The Icebound of Uftine]]":     "[[Dwarf]]",
    "[[The Stormbound of Thundrakar]]": "[[Dwarf]]",
    "[[The Flamebound of Magnus' Rest]]": "[[Dwarf]]",
    "[[Tidebound of Draumhavn]]":     "[[Dwarf]]",
    "[[Icebound of Uftine]]":         "[[Dwarf]]",
    "[[Stormbound of Thundrakar]]":   "[[Dwarf]]",
    "[[Flamebound of Magnus' Rest]]": "[[Dwarf]]",
    "[[Dwarven Holds]]":              "[[Dwarf]]",
    "[[Firebrand Empire]]":           "[[Imperial Human]]",
    "[[Thraysian Magocracy]]":        "[[Thraysian Human]]",
    "[[Rahalan Nomads]]":             "[[Rahalan]]",
    "[[People of Mokoweri]]":         "[[Mokoweri Human]]",
    "[[The Solaran Federation of Worlds]]": "[[Solaran]]",
    "[[Solaran Federation of Worlds]]":     "[[Solaran]]",
    "[[The Blackiron Collective]]":   "[[Forgeborn]]",  # debatable; blackiron is industrial/metal
    "[[Velkhar Dominion]]":           "[[Imperial Human]]",  # uncertain
}

# Affiliation -> implied culture (when culture is a thing distinct from race).
AFFILIATION_TO_CULTURE: Dict[str, str] = {
    "[[The Tidebound of Draumhavn]]":   "[[Tidebound]]",
    "[[The Icebound of Uftine]]":       "[[Icebound]]",
    "[[The Stormbound of Thundrakar]]": "[[Stormbound]]",
    "[[The Flamebound of Magnus' Rest]]": "[[Flamebound]]",
    "[[Tidebound of Draumhavn]]":       "[[Tidebound]]",
    "[[Icebound of Uftine]]":           "[[Icebound]]",
    "[[Stormbound of Thundrakar]]":     "[[Stormbound]]",
    "[[Flamebound of Magnus' Rest]]":   "[[Flamebound]]",
    "[[Rahalan Nomads]]":               "[[Rahalan]]",
    "[[Firebrand Empire]]":             "[[Firebrand]]",
    "[[Thraysian Magocracy]]":          "[[Thraysian]]",
    "[[Saurian Enclave]]":              "[[Saurian]]",
    "[[People of Mokoweri]]":           "[[Mokoweri]]",
}

# Affiliation -> seat (capital city) for location default.
AFFILIATION_TO_SEAT: Dict[str, str] = {
    "[[The Tidebound of Draumhavn]]":   "[[Draumhavn]]",
    "[[Tidebound of Draumhavn]]":       "[[Draumhavn]]",
    "[[The Icebound of Uftine]]":       "[[Uftine]]",
    "[[Icebound of Uftine]]":           "[[Uftine]]",
    "[[The Stormbound of Thundrakar]]": "[[Thundrakar]]",
    "[[Stormbound of Thundrakar]]":     "[[Thundrakar]]",
    "[[The Flamebound of Magnus' Rest]]": "[[Magnus' Rest]]",
    "[[Flamebound of Magnus' Rest]]":   "[[Magnus' Rest]]",
    "[[Thraysian Magocracy]]":          "[[Eltabarr]]",
    "[[Saurian Enclave]]":              "[[Aeloria]]",
}


def _is_empty(v: Any) -> bool:
    return v in ("", None, [], False)


def _strip_wikilink(s: str) -> str:
    if not isinstance(s, str):
        return ""
    s = s.strip()
    if s.startswith("[[") and s.endswith("]]"):
        inner = s[2:-2]
        if "|" in inner:
            inner = inner.split("|", 1)[0]
        return inner
    return s


def build_race_nature_map() -> Dict[str, str]:
    """{race_name_without_md: nature}"""
    out: Dict[str, str] = {}
    for md in iter_md_files():
        meta, _ = read_frontmatter(md)
        if meta.get("type") != "race":
            continue
        nature = meta.get("nature")
        if not nature:
            continue
        out[md.stem] = nature
    return out


def infer_character(meta: dict, race_nature: Dict[str, str]) -> int:
    changes = 0
    if meta.get("type") != "character":
        return 0

    affiliation = meta.get("affiliation")
    aff_key = affiliation if isinstance(affiliation, str) else ""

    # race
    if _is_empty(meta.get("race")) and aff_key in AFFILIATION_TO_RACE:
        meta["race"] = AFFILIATION_TO_RACE[aff_key]
        changes += 1

    # culture
    if _is_empty(meta.get("culture")) and aff_key in AFFILIATION_TO_CULTURE:
        meta["culture"] = AFFILIATION_TO_CULTURE[aff_key]
        changes += 1

    # location default = affiliation's seat (unless already set)
    if _is_empty(meta.get("location")) and aff_key in AFFILIATION_TO_SEAT:
        meta["location"] = AFFILIATION_TO_SEAT[aff_key]
        changes += 1

    # nature from race
    if _is_empty(meta.get("nature")):
        race = meta.get("race")
        if isinstance(race, str) and race:
            race_name = _strip_wikilink(race)
            nat = race_nature.get(race_name)
            if nat:
                meta["nature"] = nat
                changes += 1

    return changes


def main() -> None:
    print("Building race -> nature map...")
    race_nature = build_race_nature_map()
    print("  {} race files indexed".format(len(race_nature)))

    files_changed = 0
    total_changes = 0
    by_field: Dict[str, int] = {}

    for md in iter_md_files():
        meta, body = read_frontmatter(md)
        before = {k: meta.get(k) for k in ("race", "culture", "location", "nature")}
        n = infer_character(meta, race_nature)
        if n == 0:
            continue
        for k in ("race", "culture", "location", "nature"):
            if before[k] != meta.get(k):
                by_field[k] = by_field.get(k, 0) + 1
        write_frontmatter(md, meta, body)
        files_changed += 1
        total_changes += n

    print()
    print("Files changed: {}".format(files_changed))
    print("Total inferences applied: {}".format(total_changes))
    print("By field:")
    for k, n in sorted(by_field.items(), key=lambda kv: -kv[1]):
        print("  {:18s} {:5d}".format(k, n))


if __name__ == "__main__":
    main()
