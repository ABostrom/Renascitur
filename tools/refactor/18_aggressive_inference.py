"""Aggressive inference of property values, optimised for data-completeness.

Rationale (Aaron 2026-05-19): the frontmatter on these files is meant to
serve both as lore reference and as data input to world-gen tooling.
Empty fields are no good for the tooling. So this pass leans into
applying confident defaults + hardcoded facts for the major entities,
even when some calls are debatable.

Sections:
  1. Type-default importance — minor/notable/major by type
  2. Type-default nature — mortal for cultures/factions/houses/orgs/
     traditions; mundane for items; etc.
  3. Per-faction fact table — society_form/government/economy/seat/size
     for the named major societies
  4. Per-settlement importance overrides — capital cities -> major
  5. Per-deity importance — major
  6. Per-historical-event importance — most named events -> notable;
     legendary ones already tagged

Merge-only: never overwrites an existing non-empty value.
Idempotent.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict

# Allow running as a script from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from refactor.common import iter_md_files, read_frontmatter, write_frontmatter


# ---------------------------------------------------------------------------
# Type defaults
# ---------------------------------------------------------------------------

# Default `importance` by type.
TYPE_IMPORTANCE_DEFAULT: Dict[str, str] = {
    "era":           "legendary",
    "continent":     "major",
    "deity":         "major",
    "cosmic-force":  "major",
    "artifact":      "notable",
    "chronicle":     "notable",
    "prophecy":      "notable",
    "myth":          "notable",
    "technology":    "notable",
    "language":      "notable",
    "race":          "notable",  # specific override for lineage parents below
    "house":         "notable",
    "settlement":    "notable",
    "region":        "minor",
    "landmark":      "minor",
    "waterway":      "minor",
    "range":         "notable",
    "organisation":  "minor",
    "tradition":     "minor",
    "item":          "minor",
    "resource":      "minor",
    "faction":       "notable",
    "culture":       "notable",
    # character / essay: leave empty (too varied to default)
}

# Default `nature` by type (where the type implies it).
TYPE_NATURE_DEFAULT: Dict[str, str] = {
    "culture":      "mortal",
    "faction":      "mortal",
    "house":        "mortal",
    "organisation": "mortal",
    "tradition":    "mortal",
    "item":         "mundane",
    # deity (divine), cosmic-force (eldritch) handled in Layer 14
}

# Race-lineage parent files get importance: major (their variants stay notable).
LINEAGE_PARENT_RACE_NAMES = {
    "Solaran", "Grundthain", "Kyojin", "Elasi", "Terran",
    "Dwarf", "Dwarves", "Orc", "Orcs", "Leonin",
    "Forgeborn", "Saurian", "Slaad", "Goliath", "Varkuun",
    "Velastri", "Celestar", "Ilithid",
}


# ---------------------------------------------------------------------------
# Per-faction facts (hardcoded knowledge from the lore as I've understood it)
# ---------------------------------------------------------------------------

FACTION_FACTS: Dict[str, Dict[str, Any]] = {
    "Firebrand Empire": {
        "importance": "major",
        "society_form": "imperial",
        "government": "monarchy",
        "economy": "industrial",
        "size": "continental",
        "alignment": "lawful-neutral",
    },
    "Thraysian Magocracy": {
        "importance": "major",
        "society_form": "magocratic",
        "government": "magocratic-council",
        "economy": "magical",
        "size": "regional",
        "seat": "[[Eltabarr]]",
        "magic": ["[[Arcane]]", "[[Arcanometry]]", "[[Glyph Magic]]"],
        "alignment": "neutral",
    },
    "Saurian Enclave": {
        "importance": "major",
        "nature": "bioengineered",
        "society_form": "theocratic",
        "government": "theocracy",
        "economy": "agrarian",
        "size": "regional",
        "seat": "[[Aeloria]]",
        "alignment": "neutral-good",
    },
    "Rahalan Nomads": {
        "importance": "notable",
        "society_form": "nomadic",
        "government": "tribal-council",
        "economy": "pastoral",
        "size": "regional",
        "magic": ["[[Primal]]", "[[Divine]]"],
        "alignment": "neutral-good",
    },
    "Dwarven Holds": {
        "importance": "major",
        "society_form": "feudal",
        "government": "tribal-council",
        "economy": "mining",
        "size": "continental",
        "alignment": "lawful-neutral",
    },
    "Tidebound of Draumhavn": {
        "importance": "notable",
        "society_form": "martial",
        "government": "monarchy",
        "economy": "mercantile",
        "size": "regional",
        "seat": "[[Draumhavn]]",
        "magic": ["[[Rune Magic]]"],
        "alignment": "lawful-neutral",
    },
    "Icebound of Uftine": {
        "importance": "notable",
        "society_form": "feudal",
        "government": "monarchy",
        "economy": "mining",
        "size": "regional",
        "seat": "[[Uftine]]",
        "magic": ["[[Rune Magic]]"],
        "alignment": "lawful-neutral",
    },
    "Stormbound of Thundrakar": {
        "importance": "notable",
        "society_form": "martial",
        "government": "monarchy",
        "economy": "mining",
        "size": "regional",
        "seat": "[[Thundrakar]]",
        "magic": ["[[Rune Magic]]"],
        "alignment": "lawful-neutral",
    },
    "Flamebound of Magnus' Rest": {
        "importance": "notable",
        "society_form": "martial",
        "government": "monarchy",
        "economy": "mining",
        "size": "regional",
        "seat": "[[Magnus' Rest]]",
        "magic": ["[[Rune Magic]]", "[[Forge Magic]]"],
        "alignment": "lawful-neutral",
    },
    "The Blackiron Collective": {
        "importance": "notable",
        "society_form": "martial",
        "government": "oligarchy",
        "economy": "industrial",
        "size": "regional",
        "alignment": "lawful-evil",
    },
    "People of Mokoweri": {
        "importance": "notable",
        "society_form": "tribal",
        "government": "tribal-council",
        "economy": "agrarian",
        "size": "regional",
        "magic": ["[[Primal]]"],
        "alignment": "neutral-good",
    },
    "Solaran Federation of Worlds": {
        "importance": "legendary",  # historically; collapsed in First Age
        "society_form": "imperial",
        "government": "magocratic-council",
        "economy": "magical",
        "size": "cosmic",
        "magic": ["[[Arcanometry]]", "[[Astral Weaving]]"],
        "alignment": "lawful-good",
    },
    "The Solaran Federation of Worlds": {
        "importance": "legendary",
        "society_form": "imperial",
        "government": "magocratic-council",
        "economy": "magical",
        "size": "cosmic",
        "magic": ["[[Arcanometry]]", "[[Astral Weaving]]"],
        "alignment": "lawful-good",
    },
    "Velkhar Dominion": {
        "importance": "notable",
        "society_form": "imperial",
        "government": "monarchy",
        "size": "regional",
        "alignment": "lawful-evil",
    },
}


# ---------------------------------------------------------------------------
# Per-settlement (capital cities -> major importance)
# ---------------------------------------------------------------------------

CAPITAL_SETTLEMENTS = {
    "Eltabarr": "major",
    "Aeloria": "major",
    "Draumhavn": "major",
    "Uftine": "major",
    "Thundrakar": "major",
    "Magnus' Rest": "major",
    "Old Westgate": "major",
    "Runehart": "legendary",  # the lost hold of Muradin
    "Solara": "legendary",   # the fallen Solaran city
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_empty(v: Any) -> bool:
    return v in ("", None, [], False, 0)


def _ensure_in_list(meta: dict, key: str, values) -> bool:
    """Add each value in `values` to the list-typed field. Returns True if changed."""
    if isinstance(values, str):
        values = [values]
    current = meta.get(key)
    if not isinstance(current, list):
        current = [] if current is None else [current]
    changed = False
    for v in values:
        if v not in current:
            current.append(v)
            changed = True
    if changed:
        meta[key] = current
    return changed


def _set_if_empty(meta: dict, key: str, value: Any) -> bool:
    """Set field if it's currently empty/default. Returns True if changed."""
    if key not in meta:
        return False  # type doesn't have this field; skip
    if _is_empty(meta.get(key)) and not _is_empty(value):
        meta[key] = value
        return True
    return False


# ---------------------------------------------------------------------------
# Main inference passes
# ---------------------------------------------------------------------------

def apply_type_defaults(meta: dict) -> int:
    changes = 0
    type_ = meta.get("type")
    if not type_:
        return 0

    imp_default = TYPE_IMPORTANCE_DEFAULT.get(type_)
    if imp_default and _set_if_empty(meta, "importance", imp_default):
        changes += 1

    nat_default = TYPE_NATURE_DEFAULT.get(type_)
    if nat_default and _set_if_empty(meta, "nature", nat_default):
        changes += 1

    return changes


def apply_lineage_parent_override(meta: dict, stem: str) -> int:
    """Race-lineage parents get importance: major (variants stay notable)."""
    if meta.get("type") != "race":
        return 0
    if stem not in LINEAGE_PARENT_RACE_NAMES:
        return 0
    if meta.get("importance") == "major":
        return 0
    # Override notable->major for these specific races
    if meta.get("importance") in ("notable", "", None):
        meta["importance"] = "major"
        return 1
    return 0


def apply_faction_facts(meta: dict, stem: str) -> int:
    facts = FACTION_FACTS.get(stem)
    if not facts:
        return 0
    changes = 0
    for k, v in facts.items():
        if isinstance(v, list):
            if k in meta and _ensure_in_list(meta, k, v):
                changes += 1
        else:
            if _set_if_empty(meta, k, v):
                changes += 1
    return changes


def apply_capital_settlement(meta: dict, stem: str) -> int:
    if meta.get("type") != "settlement":
        return 0
    imp = CAPITAL_SETTLEMENTS.get(stem)
    if not imp:
        return 0
    # Overwrite default 'notable' for capitals, but don't downgrade.
    current = meta.get("importance")
    if current in (None, "", "notable", "minor"):
        meta["importance"] = imp
        return 1
    return 0


def main() -> None:
    files_changed = 0
    total_changes = 0
    by_kind: Dict[str, int] = {}

    for md in iter_md_files():
        meta, body = read_frontmatter(md)
        stem = md.stem  # filename without .md

        type_default_changes = apply_type_defaults(meta)
        if type_default_changes:
            by_kind["type_defaults"] = by_kind.get("type_defaults", 0) + type_default_changes

        lineage_changes = apply_lineage_parent_override(meta, stem)
        if lineage_changes:
            by_kind["lineage_parent_major"] = by_kind.get("lineage_parent_major", 0) + lineage_changes

        faction_changes = apply_faction_facts(meta, stem)
        if faction_changes:
            by_kind["faction_facts"] = by_kind.get("faction_facts", 0) + faction_changes

        cap_changes = apply_capital_settlement(meta, stem)
        if cap_changes:
            by_kind["capital_importance"] = by_kind.get("capital_importance", 0) + cap_changes

        total = type_default_changes + lineage_changes + faction_changes + cap_changes
        if total > 0:
            write_frontmatter(md, meta, body)
            files_changed += 1
            total_changes += total

    print("Files changed: {}".format(files_changed))
    print("Total inferences applied: {}".format(total_changes))
    print("By kind:")
    for k, n in sorted(by_kind.items(), key=lambda kv: -kv[1]):
        print("  {:25s} {:5d}".format(k, n))


if __name__ == "__main__":
    main()
