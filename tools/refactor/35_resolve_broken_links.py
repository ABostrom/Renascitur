"""Resolve high-impact broken wikilinks.

The audit (Layer 34) found 99 distinct broken targets. Most cluster
around short-form names that don't match the canonical filename.
Strategy:
  - For aliases of existing files: add the short form as an alias
    (cheapest, non-destructive, makes wikilinks resolve).
  - For missing concept pages with high reference count: create a
    skeleton file so the link resolves and a future view picks it up.

Idempotent.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from refactor.common import DOCS_DIR, read_frontmatter, write_frontmatter


# (existing file relpath, list of short-form aliases to add)
ALIAS_ADDITIONS: List = [
    ("factions/Firebrand Empire.md",          ["Firebrand", "Firebrand Empire", "The Firebrand Empire"]),
    ("factions/Thraysian Magocracy.md",       ["Thraysian Magocracy", "The Magocracy"]),
    ("factions/Saurian Enclave.md",           ["Saurian Enclave", "The Saurian Enclave"]),
    ("factions/Dwarven Holds.md",             ["Dwarven Holds", "The Dwarven Holds"]),
    ("factions/Rahalan Nomads.md",            ["Rahalan", "Rahalan Nomads", "The Rahalan Nomads"]),
    ("factions/The Blackiron Collective.md",  ["Blackiron Collective", "Blackiron"]),
    ("factions/People of Mokoweri.md",        ["Mokoweri People", "Mokoweri"]),
    ("factions/Velkhar Dominion.md",          ["Velkhar"]),
    ("factions/The Solaran Federation of Worlds.md", ["Solaran Federation", "Solaran Federation of Worlds"]),

    # Sub-factions: ensure both short and long forms resolve
    ("factions/The Tidebound of Draumhavn.md", ["Tidebound", "Tidebound of Draumhavn"]),
    ("factions/The Icebound of Uftine.md",     ["Icebound", "Icebound of Uftine"]),
    ("factions/The Stormbound of Thundrakar.md", ["Stormbound", "Stormbound of Thundrakar"]),
    ("factions/The Flamebound of Magnus' Rest.md", ["Flamebound", "Flamebound of Magnus' Rest"]),

    # Race short forms (link to the lineage parent rather than a specific variant)
    ("races/Grundthains/Grundthain.md",       ["Grundthains"]),
    ("races/Kyojin/Kyojin.md",                ["Kyojin"]),
    ("races/Solarans/Solaran.md",             ["Solaran", "Solarans"]),

    # Continent / realm short forms
    ("continents/Renascita.md",               ["Renascitur", "Renascita"]),
    ("continents/Mokoweri.md",                ["Mokoweri", "Mokoweri Island"]),
    ("continents/Draumhavn.md",               ["Draumhavn"]),
    ("continents/Thundrakar.md",              ["Thundrakar"]),

    # Pantheons
    ("deities/Noxar/Noxar Gods.md",           ["Noxar", "Noxar Pantheon", "Pantheon Of Noxar"]),
    ("deities/Luxar/Luxar Gods.md",           ["Luxar", "Luxar Pantheon", "Pantheon Of Luxar", "Luxan"]),
    ("deities/God Hand/The God Hand.md",      ["God Hand", "Quintumvirate"]),
    ("deities/Elementals/Elementals.md",      ["Elemental Pantheon", "Elemental Gods"]),

    # Hexweave
    ("cosmic-forces/Hexweave.md",             ["Hexweave", "The Hexweave"]),
]


# New skeleton files for important missing concepts.
# (relpath, type, frontmatter extras, body)
NEW_FILES: List = [
    ("races/Humans/Human.md", {
        "type": "race",
        "status": "stub",
        "tags": [],
        "lineage": "Humans",
        "nature": "mortal",
        "importance": "major",
        "aliases": ["Human", "Humans"],
    }, "\n# Human\n\n*The mortal humans of Renascitur, encompassing the Imperial, Thraysian, Mokoweri, Rahalan, Uftine, and Elasi sub-races.*\n"),

    ("resources/Lux Lapis.md", {
        "type": "resource",
        "status": "stub",
        "tags": [],
        "realm": "[[Renascita]]",
        "category": "Crystals",
        "importance": "notable",
        "aliases": ["Lux Lapis"],
    }, "\n# Lux Lapis\n\n*The magical stone that the Firebrand Empire uses to build its protective walls against the aberrant night terrors.*\n"),

    ("essays/Citizenship.md", {
        "type": "essay",
        "status": "draft",
        "topic": "firebrand",
        "tags": [],
        "aliases": ["Citizenship", "Firebrand Citizenship"],
    }, "\n# Citizenship in the Firebrand Empire\n\n*Earned through service rather than birthright. See [[Firebrand Empire]] and [[The 12 Great Houses]].*\n"),

    ("essays/Stained.md", {
        "type": "essay",
        "status": "draft",
        "topic": "firebrand",
        "tags": [],
        "aliases": ["Stained", "The Stained"],
    }, "\n# The Stained\n\n*The dispossessed underclass of the Firebrand Empire, separated from the citizenry within walled cities.*\n"),

    ("essays/The 12 Great Houses.md", {
        "type": "essay",
        "status": "draft",
        "topic": "firebrand",
        "tags": [],
        "aliases": ["The 12 Great Houses", "12 Great Houses", "Great Houses"],
    }, "\n# The 12 Great Houses\n\n*The dynastic noble houses of the Firebrand Empire that hold dragonmarked power and shape imperial politics.*\n\n## Members\n\n```dataview\nLIST FROM \"factions\" WHERE type = \"house\" SORT file.name ASC\n```\n"),

    ("cosmic-forces/Aberrations.md", {
        "type": "cosmic-force",
        "status": "stub",
        "tags": [],
        "realm": "[[Renascitur]]",
        "nature": "aberrant",
        "importance": "major",
        "aliases": ["Aberrations", "Aberration", "aberrant", "Aberrant"],
    }, "\n# Aberrations\n\n*The corrupting entities that emerged from Ishna's awakening. The Firebrand Empire's Lux Lapis walls hold them back from mortal lands.*\n"),
]


def add_aliases(path: Path, new_aliases: List[str]) -> int:
    """Add aliases to a file's frontmatter (deduplicated). Returns count added."""
    if not path.exists():
        return 0
    meta, body = read_frontmatter(path)
    existing = meta.get("aliases") or []
    if not isinstance(existing, list):
        existing = [existing]
    existing_set = {a.strip().lower() for a in existing if isinstance(a, str)}
    added = 0
    for a in new_aliases:
        if a.strip().lower() not in existing_set:
            existing.append(a)
            existing_set.add(a.strip().lower())
            added += 1
    if added > 0:
        meta["aliases"] = existing
        write_frontmatter(path, meta, body)
    return added


def create_skeleton(relpath: str, fields: Dict[str, Any], body: str) -> bool:
    """Create a skeleton file if it doesn't exist."""
    path = DOCS_DIR / relpath
    if path.exists():
        # Just merge aliases if present
        new_aliases = fields.get("aliases") or []
        if new_aliases:
            add_aliases(path, new_aliases)
            return False
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    write_frontmatter(path, fields, body)
    return True


def main() -> None:
    aliases_added = 0
    files_changed_for_aliases = 0
    new_created = 0

    for relpath, aliases in ALIAS_ADDITIONS:
        path = DOCS_DIR / relpath
        added = add_aliases(path, aliases)
        if added > 0:
            files_changed_for_aliases += 1
            aliases_added += added
            print("Aliased: {} (+{})".format(relpath, added))

    for relpath, fields, body in NEW_FILES:
        if create_skeleton(relpath, dict(fields), body):
            new_created += 1
            print("Created: {}".format(relpath))

    print("---")
    print("Files aliased: {}".format(files_changed_for_aliases))
    print("Aliases added: {}".format(aliases_added))
    print("New skeleton files: {}".format(new_created))


if __name__ == "__main__":
    main()
