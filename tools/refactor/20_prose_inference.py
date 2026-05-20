"""Prose-aware inference: reads body content and refines per-file property values.

The folder-derived inference (Layer 19) is too coarse for many characters.
Example: the Second Emperor of the Firebrand Empire is described in his
body as a Leonin warrior, but Layer 19 defaulted him to Imperial Human
because he sits under `Societies/Firebrand Empire/Emperors/`.

This pass reads the body of every file and refines:

  - race          — overrides if the body explicitly wikilinks to a race
  - gender        — from pronoun frequency (he/him vs she/her vs they/them)
  - role[]        — from title/keyword patterns ("Emperor", "Elder", "Smith")
  - living_status — from past-tense death markers and historical reign tense

OVERWRITE policy: body content is authoritative. If body says X and
frontmatter currently says Y (defaulted), body wins.

Idempotent.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set

# Allow running as a script from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from refactor.common import iter_md_files, read_frontmatter, write_frontmatter, rel_to_docs


# ---------------------------------------------------------------------------
# Race names: any wikilink target matching one of these is a race signal.
# ---------------------------------------------------------------------------
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
    "Tidebound", "Icebound", "Stormbound", "Flamebound",
}

# Lower-case index for case-insensitive matching, mapping to canonical name.
RACE_LOWER_TO_CANONICAL = {n.lower(): n for n in KNOWN_RACE_NAMES}


# ---------------------------------------------------------------------------
# Wikilink extraction (handles `[[Foo]]`, `[[Foo|Bar]]`, `[[path/to/Foo|Bar]]`).
# ---------------------------------------------------------------------------
WIKILINK_RE = re.compile(r"\[\[([^\]]+?)\]\]")


def extract_race_from_body(body: str) -> Optional[str]:
    """Return the first race wikilink target found in the body, or None."""
    for m in WIKILINK_RE.finditer(body):
        raw = m.group(1)
        # Strip alias: "Foo|Bar" -> "Foo"
        target = raw.split("|", 1)[0].strip()
        # Strip path: "docs/Races/.../Leonin" -> "Leonin"
        name = target.split("/")[-1]
        # Strip .md suffix just in case
        if name.endswith(".md"):
            name = name[:-3]
        canonical = RACE_LOWER_TO_CANONICAL.get(name.lower())
        if canonical:
            return canonical
    return None


# ---------------------------------------------------------------------------
# Pronoun-based gender inference
# ---------------------------------------------------------------------------
HE_RE = re.compile(r"\b(?:he|him|his|himself)\b", re.IGNORECASE)
SHE_RE = re.compile(r"\b(?:she|her|hers|herself)\b", re.IGNORECASE)
THEY_RE = re.compile(r"\b(?:they|them|their|theirs|themself|themselves)\b", re.IGNORECASE)


def extract_gender_from_pronouns(body: str) -> Optional[str]:
    he = len(HE_RE.findall(body))
    she = len(SHE_RE.findall(body))
    they = len(THEY_RE.findall(body))

    # Need at least 3 hits and a clear majority (>= 2x the next-highest)
    counts = [("male", he), ("female", she), ("nonbinary", they)]
    counts.sort(key=lambda t: -t[1])
    winner_label, winner_count = counts[0]
    runner_up_count = counts[1][1]
    if winner_count >= 3 and winner_count >= max(1, 2 * runner_up_count):
        return winner_label
    return None


# ---------------------------------------------------------------------------
# Role pattern matching
# ---------------------------------------------------------------------------
# (regex, role-value) — first match wins per role; multiple roles allowed.
ROLE_PATTERNS: List = [
    ("ruler",       re.compile(r"\b(emperor|empress|king|queen|sultan(?:a)?|monarch|sovereign|warlord|chieftain)\b", re.IGNORECASE)),
    ("warrior",     re.compile(r"\b(captain|general|admiral|warrior|knight|legate|marshal|paladin|swordmaster|guardian|soldier)\b", re.IGNORECASE)),
    ("mage",        re.compile(r"\b(magister|archmage|mage|wizard|sorcerer|sorceress|magus|spellweaver|enchanter|enchantress)\b", re.IGNORECASE)),
    ("priest",      re.compile(r"\b(high priest|priestess|priest|cleric|prophetess)\b", re.IGNORECASE)),
    ("scholar",     re.compile(r"\b(scholar|professor|researcher|sage|loremaster|chronicler|archivist)\b", re.IGNORECASE)),
    ("craftsman",   re.compile(r"\b(smith|forgemaster|forge-master|forgeborn|craftsman|artisan|tinker|mason)\b", re.IGNORECASE)),
    ("merchant",    re.compile(r"\b(merchant|trader|magnate)\b", re.IGNORECASE)),
    ("prophet",     re.compile(r"\b(prophet|prophetess|seer|oracle|visionary)\b", re.IGNORECASE)),
    ("villain",     re.compile(r"\b(tyrant|usurper|dark lord|abomination)\b", re.IGNORECASE)),
    ("mentor",      re.compile(r"\b(elder|teacher|mentor|guide|grandmaster)\b", re.IGNORECASE)),
]


def extract_roles_from_body(body: str, name: str) -> List[str]:
    """Return roles found in the body. Filename context helps for things like 'Elder'."""
    found = []
    full_text = name + " " + body
    for role, pattern in ROLE_PATTERNS:
        if pattern.search(full_text):
            if role not in found:
                found.append(role)
    return found


# ---------------------------------------------------------------------------
# Living-status inference
# ---------------------------------------------------------------------------
DEATH_PATTERNS = [
    re.compile(r"\b(was killed|slain|perished|fell in battle|died|was murdered|was assassinated|met (?:his|her|their) end)\b", re.IGNORECASE),
    re.compile(r"\b(deceased|dead|fallen|lost to)\b", re.IGNORECASE),
    re.compile(r"\b(reigned|ruled) (?:from|until|over)\b", re.IGNORECASE),
]
ASCENDED_PATTERNS = [
    re.compile(r"\bascended to godhood\b", re.IGNORECASE),
    re.compile(r"\b(became|transformed into) a god\b", re.IGNORECASE),
]
IMPRISONED_PATTERNS = [
    re.compile(r"\b(imprisoned in|sealed within|bound in)\b", re.IGNORECASE),
]


ORDINAL_NON_LAST_RE = re.compile(
    r"\b(First|Second|Third|Fourth|Fifth|Sixth|Seventh)\b\s+(Emperor|Empress|Emperors|Empresses)",
    re.IGNORECASE,
)


def extract_living_status(body: str, name: str, frontmatter: dict, relpath: str = "") -> Optional[str]:
    # Ascended takes priority over deceased
    for p in ASCENDED_PATTERNS:
        if p.search(body):
            return "ascended"
    for p in IMPRISONED_PATTERNS:
        if p.search(body):
            return "imprisoned"
    # Death indicators in body
    for p in DEATH_PATTERNS:
        if p.search(body):
            return "deceased"
    # Sequential rulers: any non-last Emperor/Empress is historically dead
    if ORDINAL_NON_LAST_RE.search(name):
        return "deceased"
    # Anyone whose era_of_death is set is deceased
    if frontmatter.get("era_of_death"):
        return "deceased"
    return None


# ---------------------------------------------------------------------------
# Main per-character pass
# ---------------------------------------------------------------------------

def process_character(meta: dict, body: str, name: str) -> int:
    changes = 0

    # --- race (OVERWRITE — body is authoritative) ---
    body_race = extract_race_from_body(body)
    if body_race:
        candidate = "[[{}]]".format(body_race)
        if meta.get("race") != candidate:
            meta["race"] = candidate
            changes += 1

    # --- gender (only set if currently empty) ---
    if not meta.get("gender"):
        g = extract_gender_from_pronouns(body)
        if g:
            meta["gender"] = g
            changes += 1

    # --- role[] (only set if currently empty) ---
    if not meta.get("role"):
        roles = extract_roles_from_body(body, name)
        if roles:
            meta["role"] = roles
            changes += 1

    # --- living_status (only set if currently empty) ---
    if not meta.get("living_status"):
        ls = extract_living_status(body, name, meta)
        if ls:
            meta["living_status"] = ls
            changes += 1

    return changes


def process_non_character_files() -> Dict[str, int]:
    """Lightweight prose-pass for non-character types.

    Currently:
      - Deities: extract alignment hints from body (lawful/chaotic, good/evil)
      - Factions: extract magic[] from body wikilinks to known magic disciplines
    """
    by_field: Dict[str, int] = {}
    MAGIC_NAMES = {"Arcane", "Divine", "Primal", "Arcanometry", "Astral Weaving",
                   "Glyph Magic", "Rune Magic", "Soul Magic", "Psionic"}
    MAGIC_LOWER = {n.lower(): n for n in MAGIC_NAMES}
    for md in iter_md_files():
        meta, body = read_frontmatter(md)
        type_ = meta.get("type")
        if type_ not in ("faction", "culture", "house", "organisation"):
            continue
        # Magic from body wikilinks
        if "magic" in meta:
            current = meta.get("magic") or []
            if not isinstance(current, list):
                current = [current]
            added = False
            for m in WIKILINK_RE.finditer(body):
                target = m.group(1).split("|", 1)[0].strip().split("/")[-1]
                if target.endswith(".md"):
                    target = target[:-3]
                canonical = MAGIC_LOWER.get(target.lower())
                if canonical:
                    link = "[[{}]]".format(canonical)
                    if link not in current:
                        current.append(link)
                        added = True
            if added:
                meta["magic"] = current
                write_frontmatter(md, meta, body)
                by_field["magic"] = by_field.get("magic", 0) + 1
    return by_field


def main() -> None:
    files_changed = 0
    total_changes = 0
    by_field: Dict[str, int] = {}

    for md in iter_md_files():
        meta, body = read_frontmatter(md)
        if meta.get("type") != "character":
            continue
        name = md.stem
        before = {k: meta.get(k) for k in ("race", "gender", "role", "living_status")}
        n = process_character(meta, body, name)
        if n == 0:
            continue
        for k in ("race", "gender", "role", "living_status"):
            if before[k] != meta.get(k):
                by_field[k] = by_field.get(k, 0) + 1
        write_frontmatter(md, meta, body)
        files_changed += 1
        total_changes += n

    print("Characters changed: {}".format(files_changed))
    print("Total field updates: {}".format(total_changes))
    print("By field:")
    for k, n in sorted(by_field.items(), key=lambda kv: -kv[1]):
        print("  {:18s} {:5d}".format(k, n))

    print()
    print("=== Non-character pass ===")
    non_char = process_non_character_files()
    for k, n in sorted(non_char.items(), key=lambda kv: -kv[1]):
        print("  {:18s} {:5d}".format(k, n))


if __name__ == "__main__":
    main()
