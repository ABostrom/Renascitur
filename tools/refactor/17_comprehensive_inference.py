"""Comprehensive property inference.

Builds on Layer-16 by adding many more confident inferences:

  - magic[] derived from existing flat tags (arcane, arcanometry, etc.)
  - society_form derived from existing flat tags (nomadic, imperial, ...)
  - climate by continent (Arcturia=arctic, Pyrosia=volcanic, ...)
  - character.nature inherited from character.race (chain lookup)
  - race-specific nature overrides (Elasi=mortal, Forgeborn=forgeborn,
    Saurian=bioengineered, Slaad=aberrant)
  - item nature default = 'mundane'
  - importance=legendary for the 4 era summaries + the heavy-impact
    named historical events
  - house nature=mortal + government=oligarchy for the 12 Great Houses
  - Re-correct Solarans from 'celestial' to 'mortal' (they're ancient
    flesh-and-blood, not cosmic-beings)

Merge-only for empty/default fields; never overwrites a non-default
existing value.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List

# Allow running as a script from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from refactor.common import iter_md_files, read_frontmatter, write_frontmatter, rel_to_docs


# ---------------------------------------------------------------------------
# Mapping rules
# ---------------------------------------------------------------------------

# Flat tag -> magic discipline wikilink
TAG_TO_MAGIC: Dict[str, str] = {
    "arcane":         "[[Arcane]]",
    "divine":         "[[Divine]]",
    "primal":         "[[Primal]]",
    "arcanometry":    "[[Arcanometry]]",
    "astralweaving":  "[[Astral Weaving]]",
    "astral-weaving": "[[Astral Weaving]]",
    "glyph":          "[[Glyph Magic]]",
    "glyphs":         "[[Glyph Magic]]",
    "rune":           "[[Rune Magic]]",
    "soul":           "[[Soul Magic]]",
    "soulmagic":      "[[Soul Magic]]",
    "psionic":        "[[Psionic]]",
}

# Flat tag -> society_form value
TAG_TO_SOCIETY_FORM: Dict[str, str] = {
    "nomadic":     "nomadic",
    "imperial":    "imperial",
    "magocratic":  "magocratic",
    "tribal":      "tribal",
    "industrial":  "industrial",
    "spiritual":   "monastic",
    "mercantile":  "mercantile",
    "pastoral":    "pastoral",
    "martial":     "martial",
}

# Continent -> climate
CONTINENT_TO_CLIMATE: Dict[str, str] = {
    "[[Arcturia]]":          "arctic",
    "[[Pyrosia]]":           "volcanic",
    "[[Mokoweri]]":          "tropical",
    "[[Aquaria]]":           "aquatic",
    "[[Qethusiyya]]":        "arid",
    "[[Draumhavn]]":         "maritime",
    "[[Thundrakar]]":        "stormy",
    "[[The World Beneath]]": "subterranean",
}

# Race name -> nature (for the race files themselves)
RACE_NAME_TO_NATURE: Dict[str, str] = {
    "Forgeborn":   "forgeborn",
    "Saurian":     "bioengineered",
    "Slaad":       "aberrant",
    "Solaran":     "mortal",  # corrects earlier 'celestial' overshoot
    "Ilithid":     "corrupted",
    "Celestar":    "celestial",  # Solaran variant that DID achieve cosmic ascension
    "Velastri":    "mortal",
    "Grundthain":  "mortal",
    "Varkuun":     "mortal",
    "Goliath":     "mortal",
    "Dwarf":       "mortal",
    "Dwarves":     "mortal",
    "Kyojin":      "mortal",
    "Orc":         "mortal",
    "Orcs":        "mortal",
    "Leonin":      "mortal",
    "Imperial Leonin": "mortal",
    "Imperial Orcs":   "mortal",
    "Elasi":       "mortal",
    "Aquasi":      "mortal",
    "Ignasi":      "mortal",
    "Terrasi":     "mortal",
    "Ventasi":     "mortal",
    "Terran":      "mortal",
    "Imperial Human":  "mortal",
    "Mokoweri Human":  "mortal",
    "Rahalan":         "mortal",
    "Thraysian Human": "mortal",
    "Uftine Human":    "mortal",
    "Tidebound":   "mortal",
    "Icebound":    "mortal",
    "Stormbound":  "mortal",
    "Flamebound":  "mortal",
}

# Named historical events that are legendary in importance (heavy-impact, widely referenced).
LEGENDARY_EVENT_NAMES = {
    "Hexweave Binding",
    "The Forge Wars",
    "Breaking of the Hexweave Seal",
    "Collapse of Solara",
    "Creation of the World",
    "The Fall of the Endless Sun",
    "End of the First Age",
    "Sealing of Ishna",
    "Muradin Seals Typhon",
    "Collapse of Runehart",
    "Betrayal of Vecna",
    "Night War",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_empty(v: Any) -> bool:
    return v in ("", None, [], False)


def _ensure_in_list(meta: dict, key: str, value: str) -> bool:
    """Append value to a list-typed field if absent. Returns True if changed."""
    current = meta.get(key)
    if current is None:
        meta[key] = [value]
        return True
    if not isinstance(current, list):
        current = [current]
    if value in current:
        return False
    current.append(value)
    meta[key] = current
    return True


def _strip_wikilink(s: str) -> str:
    """[[Foo]] -> Foo, [[Foo|Bar]] -> Foo."""
    if not isinstance(s, str):
        return ""
    s = s.strip()
    if s.startswith("[[") and s.endswith("]]"):
        inner = s[2:-2]
        if "|" in inner:
            inner = inner.split("|", 1)[0]
        return inner
    return s


# ---------------------------------------------------------------------------
# Pass 0: build race -> nature map from race files (chain prep)
# ---------------------------------------------------------------------------

def build_race_nature_map() -> Dict[str, str]:
    """Read all race files; return {race_name: nature}.

    Used to chain character.nature from character.race.
    """
    out: Dict[str, str] = {}
    for md in iter_md_files():
        meta, _ = read_frontmatter(md)
        if meta.get("type") != "race":
            continue
        nature = meta.get("nature")
        if not nature:
            continue
        race_name = md.stem  # filename without .md
        out[race_name] = nature
    return out


# ---------------------------------------------------------------------------
# Pass 1: per-file inference
# ---------------------------------------------------------------------------

def infer_for_file(meta: dict, relpath: str, race_nature: Dict[str, str]) -> int:
    """Apply inference rules to meta in-place. Returns count of changes."""
    changes = 0
    type_ = meta.get("type")
    tags = meta.get("tags") or []
    if not isinstance(tags, list):
        tags = [tags]

    # ----- Magic[] from tags -----
    for tag in tags:
        if not isinstance(tag, str):
            continue
        magic_link = TAG_TO_MAGIC.get(tag.lower())
        if magic_link:
            # magic is a list field on character/faction/culture/technology/etc.
            if "magic" not in meta:
                continue  # type doesn't have magic field, skip
            if _ensure_in_list(meta, "magic", magic_link):
                changes += 1

    # ----- Society_form from tags -----
    if "society_form" in meta and _is_empty(meta.get("society_form")):
        for tag in tags:
            if not isinstance(tag, str):
                continue
            sf = TAG_TO_SOCIETY_FORM.get(tag.lower())
            if sf:
                meta["society_form"] = sf
                changes += 1
                break

    # ----- Climate by continent -----
    if "climate" in meta and _is_empty(meta.get("climate")):
        continent = meta.get("continent")
        if isinstance(continent, str):
            climate = CONTINENT_TO_CLIMATE.get(continent.strip())
            if climate:
                meta["climate"] = climate
                changes += 1

    # ----- Race file -> own nature (using race name) -----
    if type_ == "race" and _is_empty(meta.get("nature")):
        race_name = relpath.split("/")[-1][:-3]  # strip .md
        nat = RACE_NAME_TO_NATURE.get(race_name)
        if nat:
            meta["nature"] = nat
            changes += 1

    # ----- Override Solaran race nature (was set to celestial by Layer 16) -----
    if type_ == "race":
        race_name = relpath.split("/")[-1][:-3]
        if race_name == "Solaran" and meta.get("nature") == "celestial":
            meta["nature"] = "mortal"
            changes += 1

    # ----- Character.nature inherited from race -----
    if type_ == "character" and _is_empty(meta.get("nature")):
        race = meta.get("race")
        if isinstance(race, str) and race:
            race_name = _strip_wikilink(race)
            nat = race_nature.get(race_name) or RACE_NAME_TO_NATURE.get(race_name)
            if nat:
                meta["nature"] = nat
                changes += 1

    # ----- Item nature default = mundane -----
    if type_ == "item" and _is_empty(meta.get("nature")):
        meta["nature"] = "mundane"
        changes += 1

    # ----- Importance: legendary for era summaries + named legendary events -----
    if type_ == "era" and _is_empty(meta.get("importance")):
        meta["importance"] = "legendary"
        changes += 1

    if type_ == "event" and _is_empty(meta.get("importance")):
        # Check filename stripped of prefix
        stem = relpath.split("/")[-1][:-3]
        # Strip <CODE><year> prefix if present
        import re as _re
        m = _re.match(r"^[A-Z]{2}\d{4,6}\s+(.+)$", stem)
        title = m.group(1) if m else stem
        if title in LEGENDARY_EVENT_NAMES:
            meta["importance"] = "legendary"
            changes += 1

    # ----- House (Great House) nature=mortal, government=oligarchy -----
    if type_ == "house":
        if _is_empty(meta.get("nature")):
            meta["nature"] = "mortal"
            changes += 1
        if _is_empty(meta.get("government")):
            meta["government"] = "oligarchy"
            changes += 1

    # ----- Deity importance: notable default (still allow override) -----
    # leave to author; skip

    return changes


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("Pass 0: building race -> nature map...")
    race_nature = build_race_nature_map()
    print("  {} race files indexed".format(len(race_nature)))

    files_changed = 0
    total_changes = 0
    by_type: Dict[str, int] = {}

    for md in iter_md_files():
        rel = rel_to_docs(md)
        meta, body = read_frontmatter(md)
        type_ = meta.get("type", "?")
        n = infer_for_file(meta, rel, race_nature)
        if n > 0:
            write_frontmatter(md, meta, body)
            files_changed += 1
            total_changes += n
            by_type[type_] = by_type.get(type_, 0) + n

    print()
    print("Files changed: {}".format(files_changed))
    print("Total inferences applied: {}".format(total_changes))
    print("By type:")
    for t, n in sorted(by_type.items(), key=lambda kv: -kv[1]):
        print("  {:18s} {:5d}".format(t, n))


if __name__ == "__main__":
    main()
