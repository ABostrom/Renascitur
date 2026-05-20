"""Corrective pass: rebuild character.race using SELF-IDENTIFYING patterns only.

Layer 20 was too aggressive: it grabbed the first race wikilink found in
the body. That breaks for characters whose body mentions a different
race incidentally (e.g., Elder Kirex sees 'Solaran warriors' in his
visions, but he himself is Saurian).

This pass:
  1. Re-scans every character body for SELF-IDENTIFYING race patterns:
       - 'X is a [[Race]] ...'
       - 'X, a [[Race]]'
       - 'the [[Race]] X'
       - 'X, the [[Race]] ...'
     where X is the character's name (first token).
  2. If a self-identifying race is found, it's authoritative.
  3. If NOT found, use the affiliation->race default (re-applied).
  4. If neither, leave the existing race alone (don't blank it).

Idempotent.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Dict, Optional, Set

# Allow running as a script from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from refactor.common import iter_md_files, read_frontmatter, write_frontmatter


KNOWN_RACE_NAMES: Set[str] = {
    "Leonin", "Imperial Leonin",
    "Saurian", "Slaad", "Forgeborn",
    "Dwarf", "Dwarves",
    "Orc", "Orcs", "Imperial Orcs",
    "Kyojin",
    "Human", "Imperial Human", "Mokoweri Human", "Rahalan", "Thraysian Human",
    "Uftine Human", "Terran",
    "Solaran", "Velastri", "Celestar", "Ilithid",
    "Arcanii", "Ferrun", "Mokuun",
    "Elasi", "Aquasi", "Ignasi", "Terrasi", "Ventasi",
    "Goliath", "Varkuun",
    "Grundthain",
}
RACE_LOWER = {n.lower(): n for n in KNOWN_RACE_NAMES}


# Affiliation -> default race (re-imported from Layer 19).
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
    "[[The Blackiron Collective]]":   "[[Forgeborn]]",
    "[[Velkhar Dominion]]":           "[[Imperial Human]]",
}


def _strip_wikilink_to_race(token: str) -> Optional[str]:
    """Given '[[X|Y]]' or '[[path/X]]' or 'X', return canonical race name if known."""
    if not token:
        return None
    token = token.strip()
    if token.startswith("[[") and token.endswith("]]"):
        token = token[2:-2]
    if "|" in token:
        token = token.split("|", 1)[0]
    if "/" in token:
        token = token.split("/")[-1]
    if token.endswith(".md"):
        token = token[:-3]
    return RACE_LOWER.get(token.lower())


def find_self_identified_race(body: str, name: str) -> Optional[str]:
    """Return a race name that the body self-identifies the character as, or None.

    Self-identifying patterns (in order):
      'Name is a/an [optional adjs] [[Race]] [noun]'
      'Name, a/an [optional adjs] [[Race]]'
      'the [[Race]] Name'
      'Name the [[Race]]'
    """
    # Use first token of name (e.g., 'Duo' from 'Duo - Second Emperor', 'Kirex' from 'Elder Kirex')
    # Also try the actual common name (after 'Elder ', etc.) - try several candidates.
    raw_first = name.split(" - ")[0].split(",")[0].split(" ")[0]
    # If filename like 'Elder Kirex', the character is 'Kirex'
    after_title = name.split(" ")[-1] if len(name.split(" ")) > 1 else None
    candidates = [raw_first]
    if after_title and after_title != raw_first:
        candidates.append(after_title)

    # Race-link group is (?:\[\[)?([^\]\s|]+)(?:\|[^\]]+)?(?:\]\])? — match optional wikilink markers.
    race_atom = r"(?:\[\[)?([\w' ]+?)(?:\|[\w' ]+)?(?:\]\])?"

    patterns_template = [
        # "<Name> is a [[Race]] noun"
        r"\b{name}\b\s+is\s+(?:a|an)\s+(?:[\w-]+\s+){{0,3}}\[\[(?P<r>[^\]|]+)(?:\|[^\]]+)?\]\]",
        # "<Name>, a [[Race]]"
        r"\b{name}\b,\s+(?:a|an)\s+(?:[\w-]+\s+){{0,3}}\[\[(?P<r>[^\]|]+)(?:\|[^\]]+)?\]\]",
        # "the [[Race]] <Name>"
        r"\bthe\s+\[\[(?P<r>[^\]|]+)(?:\|[^\]]+)?\]\]\s+(?:[\w-]+\s+){{0,2}}{name}\b",
        # "<Name> the [[Race]]"
        r"\b{name}\b\s+the\s+\[\[(?P<r>[^\]|]+)(?:\|[^\]]+)?\]\]",
        # Non-wikilink fallback: "Name is a Race"
        r"\b{name}\b\s+is\s+(?:a|an)\s+(?:[\w-]+\s+){{0,3}}(?P<r>" + r"|".join(re.escape(n) for n in KNOWN_RACE_NAMES) + r")\b",
        # "<Name> ... portrayed as a [[Race]]"
        r"\b{name}\b\s+is\s+portrayed\s+as\s+(?:a|an)\s+(?:[\w-]+\s+){{0,3}}\[\[(?P<r>[^\]|]+)(?:\|[^\]]+)?\]\]",
    ]

    for cand in candidates:
        for tpl in patterns_template:
            try:
                pat = re.compile(tpl.format(name=re.escape(cand)), re.IGNORECASE)
            except re.error:
                continue
            m = pat.search(body)
            if m:
                race = _strip_wikilink_to_race(m.group("r"))
                if race:
                    return race
    return None


def main() -> None:
    files_changed = 0
    set_from_self = 0
    set_from_affiliation = 0
    cleared_to_default = 0

    for md in iter_md_files():
        meta, body = read_frontmatter(md)
        if meta.get("type") != "character":
            continue

        name = md.stem
        current_race = meta.get("race") or ""
        affiliation = meta.get("affiliation") or ""
        affil_default = AFFILIATION_TO_RACE.get(affiliation) if isinstance(affiliation, str) else None

        self_race = find_self_identified_race(body, name)

        new_race = None
        source = ""
        if self_race:
            new_race = "[[{}]]".format(self_race)
            source = "self"
        elif affil_default:
            new_race = affil_default
            source = "affiliation"
        # else: leave unchanged

        if new_race and new_race != current_race:
            meta["race"] = new_race
            write_frontmatter(md, meta, body)
            files_changed += 1
            if source == "self":
                set_from_self += 1
            elif source == "affiliation":
                set_from_affiliation += 1
                if current_race and current_race != affil_default:
                    cleared_to_default += 1

    print("Files changed: {}".format(files_changed))
    print("  set from self-id pattern: {}".format(set_from_self))
    print("  set from affiliation default: {}".format(set_from_affiliation))
    print("  reverted from over-aggressive Layer 20: {}".format(cleared_to_default))


if __name__ == "__main__":
    main()
