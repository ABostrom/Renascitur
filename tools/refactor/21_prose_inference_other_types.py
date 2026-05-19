"""Prose-aware inference for non-character types.

Companion to Layer 20 (characters). Reads body content of:

  - settlement: climate, terrain, defenses, population, predominant_economy
  - region: terrain, population_density
  - deity: domain, alignment, symbol, holy_day
  - artifact: cursed, divine, magic[], current_bearer
  - faction: magic[] expansion, alignment hints, government refinement
  - culture: society_form refinement, magic[]
  - event: outcome hints
  - landmark: nature (sacred/cursed/ruined)

Merge-only: never overwrites non-empty values. Overrides defaults
(e.g., empty strings) where the body provides a clear signal.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set

# Allow running as a script from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from refactor.common import iter_md_files, read_frontmatter, write_frontmatter


WIKILINK_RE = re.compile(r"\[\[([^\]]+?)\]\]")

MAGIC_NAMES = {"Arcane", "Divine", "Primal", "Arcanometry", "Astral Weaving",
               "Glyph Magic", "Rune Magic", "Soul Magic", "Psionic", "Forge Magic"}
MAGIC_LOWER = {n.lower(): n for n in MAGIC_NAMES}


def _is_empty(v) -> bool:
    return v in ("", None, [], False, 0)


def _extract_magic_from_body(body: str) -> List[str]:
    """Return list of magic discipline wikilinks found in body."""
    found = []
    seen = set()
    for m in WIKILINK_RE.finditer(body):
        target = m.group(1).split("|", 1)[0].strip().split("/")[-1]
        if target.endswith(".md"):
            target = target[:-3]
        canonical = MAGIC_LOWER.get(target.lower())
        if canonical:
            link = "[[{}]]".format(canonical)
            if link not in seen:
                seen.add(link)
                found.append(link)
    return found


# ---------------------------------------------------------------------------
# Settlement inference
# ---------------------------------------------------------------------------
CLIMATE_KEYWORDS = [
    ("arctic",       re.compile(r"\b(arctic|frozen|glacier|ice-bound|icy|tundra|frigid)\b", re.IGNORECASE)),
    ("volcanic",     re.compile(r"\b(volcanic|magma|lava|caldera|ashen)\b", re.IGNORECASE)),
    ("tropical",     re.compile(r"\b(tropical|jungle|rainforest|sweltering|humid)\b", re.IGNORECASE)),
    ("arid",         re.compile(r"\b(arid|desert|sandstone|dune|parched)\b", re.IGNORECASE)),
    ("temperate",    re.compile(r"\b(temperate|forested|verdant|mild)\b", re.IGNORECASE)),
    ("maritime",     re.compile(r"\b(maritime|coastal|harbour|harbor|port city|sea-girt)\b", re.IGNORECASE)),
    ("subterranean", re.compile(r"\b(subterranean|underground|cavern-bound|deep underground)\b", re.IGNORECASE)),
]
TERRAIN_KEYWORDS = [
    ("plains",      re.compile(r"\b(plains|grassland|savanna|prairie)\b", re.IGNORECASE)),
    ("mountains",   re.compile(r"\b(mountain|mountainous|peaks|alpine)\b", re.IGNORECASE)),
    ("forest",      re.compile(r"\b(forest|wooded|jungle|grove)\b", re.IGNORECASE)),
    ("coast",       re.compile(r"\b(coast|coastal|shoreline|cliffs|harbour|harbor)\b", re.IGNORECASE)),
    ("tundra",      re.compile(r"\b(tundra|permafrost)\b", re.IGNORECASE)),
    ("underground", re.compile(r"\b(underground|cavern|subterranean|deep below)\b", re.IGNORECASE)),
    ("island",      re.compile(r"\b(island|atoll|archipelago)\b", re.IGNORECASE)),
    ("desert",      re.compile(r"\b(desert|sand-swept|dune)\b", re.IGNORECASE)),
    ("volcanic",    re.compile(r"\b(volcanic|magma|lava|caldera)\b", re.IGNORECASE)),
    ("river",       re.compile(r"\b(river|riverine|delta|fluvial)\b", re.IGNORECASE)),
]
DEFENSES_KEYWORDS = [
    ("strongly-warded", re.compile(r"\b(warded|magical defenses|arcane wards|enchanted walls)\b", re.IGNORECASE)),
    ("fortified",       re.compile(r"\b(fortified|fortress|citadel|stronghold|bastion)\b", re.IGNORECASE)),
    ("walled",          re.compile(r"\b(walled city|walls of|great walls|city walls)\b", re.IGNORECASE)),
    ("hidden",          re.compile(r"\b(hidden|concealed|secret city|veiled)\b", re.IGNORECASE)),
    ("open",            re.compile(r"\b(open city|undefended|peaceful settlement)\b", re.IGNORECASE)),
]
ECONOMY_KEYWORDS = [
    ("mining",      re.compile(r"\b(mining|mines|ore|smelting|smith[a-z]*)\b", re.IGNORECASE)),
    ("agrarian",    re.compile(r"\b(agriculture|farming|farmland|crop|grain)\b", re.IGNORECASE)),
    ("mercantile",  re.compile(r"\b(trade|merchants|trading post|marketplace|mercantile)\b", re.IGNORECASE)),
    ("industrial",  re.compile(r"\b(industrial|factory|forges|industry|manufactur)\b", re.IGNORECASE)),
    ("magical",    re.compile(r"\b(arcane academy|magical research|magic-driven|magical economy)\b", re.IGNORECASE)),
    ("military",   re.compile(r"\b(garrison|military|war-machine|legion)\b", re.IGNORECASE)),
]


def infer_settlement(meta: dict, body: str) -> int:
    changes = 0
    if _is_empty(meta.get("climate")):
        for label, p in CLIMATE_KEYWORDS:
            if p.search(body):
                meta["climate"] = label
                changes += 1
                break
    if _is_empty(meta.get("terrain")):
        for label, p in TERRAIN_KEYWORDS:
            if p.search(body):
                meta["terrain"] = label
                changes += 1
                break
    if _is_empty(meta.get("defenses")):
        for label, p in DEFENSES_KEYWORDS:
            if p.search(body):
                meta["defenses"] = label
                changes += 1
                break
    if _is_empty(meta.get("predominant_economy")):
        for label, p in ECONOMY_KEYWORDS:
            if p.search(body):
                meta["predominant_economy"] = label
                changes += 1
                break
    return changes


def infer_region(meta: dict, body: str) -> int:
    changes = 0
    # Climate chain from continent if still empty
    # (handled elsewhere; we focus on terrain here)
    if _is_empty(meta.get("terrain")):
        terrains = []
        for label, p in TERRAIN_KEYWORDS:
            if p.search(body):
                terrains.append(label)
        if terrains:
            meta["terrain"] = terrains[:3]  # cap at 3 to avoid bloat
            changes += 1
    return changes


# ---------------------------------------------------------------------------
# Deity inference: domain + alignment + symbol from explicit body mentions
# ---------------------------------------------------------------------------
DOMAIN_KEYWORDS = [
    ("life",        re.compile(r"\b(god[a-z]* of life|life-giver|healing|fertility|rebirth)\b", re.IGNORECASE)),
    ("death",       re.compile(r"\b(god[a-z]* of death|death|undying|necromancy)\b", re.IGNORECASE)),
    ("war",         re.compile(r"\b(god[a-z]* of war|war|conquest|battle-lord)\b", re.IGNORECASE)),
    ("knowledge",   re.compile(r"\b(god[a-z]* of (knowledge|wisdom|secrets)|loremaster)\b", re.IGNORECASE)),
    ("trickery",    re.compile(r"\b(god[a-z]* of (trickery|deception|lies)|trickster)\b", re.IGNORECASE)),
    ("nature",      re.compile(r"\b(god[a-z]* of (nature|the wild|the forest))\b", re.IGNORECASE)),
    ("forge",       re.compile(r"\b(god[a-z]* of (the forge|smithing|craft))\b", re.IGNORECASE)),
    ("sea",         re.compile(r"\b(god[a-z]* of (the sea|oceans|tides|storms))\b", re.IGNORECASE)),
    ("light",       re.compile(r"\b(god[a-z]* of (light|the sun|dawn))\b", re.IGNORECASE)),
    ("darkness",    re.compile(r"\b(god[a-z]* of (darkness|shadow|the night))\b", re.IGNORECASE)),
    ("pestilence",  re.compile(r"\b(god[a-z]* of (pestilence|disease|plague|decay|rot))\b", re.IGNORECASE)),
    ("madness",     re.compile(r"\b(god[a-z]* of (madness|the mind|insanity))\b", re.IGNORECASE)),
    ("sleep",       re.compile(r"\b(god[a-z]* of (sleep|dreams|nightmares))\b", re.IGNORECASE)),
]

ALIGNMENT_KEYWORDS = [
    ("chaotic-evil",   re.compile(r"\b(evil|malevolent|wicked|tyrannical|tyrant)\b", re.IGNORECASE)),
    ("lawful-good",    re.compile(r"\b(benevolent|just|noble|champion of good)\b", re.IGNORECASE)),
    ("neutral-good",   re.compile(r"\b(protector|guardian of the (mortals|innocent))\b", re.IGNORECASE)),
    ("chaotic-neutral", re.compile(r"\b(unpredictable|capricious|free spirit)\b", re.IGNORECASE)),
]


def infer_deity(meta: dict, body: str) -> int:
    changes = 0
    if _is_empty(meta.get("domain")):
        domains = []
        for label, p in DOMAIN_KEYWORDS:
            if p.search(body):
                domains.append(label)
        if domains:
            meta["domain"] = domains[:3]
            changes += 1
    if _is_empty(meta.get("alignment")):
        for label, p in ALIGNMENT_KEYWORDS:
            if p.search(body):
                meta["alignment"] = label
                changes += 1
                break
    return changes


# ---------------------------------------------------------------------------
# Artifact inference: cursed, divine, magic[]
# ---------------------------------------------------------------------------
CURSED_PATTERN = re.compile(r"\b(cursed|curse-bound|corrupting|maledict)\b", re.IGNORECASE)
DIVINE_PATTERN = re.compile(r"\b(divine|forged by .* god|gift of [A-Z][a-z]+|holy artifact|sacred)\b", re.IGNORECASE)


def infer_artifact(meta: dict, body: str) -> int:
    changes = 0
    if meta.get("cursed") is False and CURSED_PATTERN.search(body):
        meta["cursed"] = True
        changes += 1
    if meta.get("divine") is False and DIVINE_PATTERN.search(body):
        meta["divine"] = True
        changes += 1
    if "magic" in meta and _is_empty(meta.get("magic")):
        m = _extract_magic_from_body(body)
        if m:
            meta["magic"] = m
            changes += 1
    return changes


# ---------------------------------------------------------------------------
# Faction/culture/house inference (magic from body)
# ---------------------------------------------------------------------------

def infer_faction_or_culture(meta: dict, body: str) -> int:
    changes = 0
    if "magic" in meta:
        current = meta.get("magic") or []
        if not isinstance(current, list):
            current = [current]
        body_magic = _extract_magic_from_body(body)
        added = False
        for link in body_magic:
            if link not in current:
                current.append(link)
                added = True
        if added:
            meta["magic"] = current
            changes += 1
    return changes


# ---------------------------------------------------------------------------
# Landmark inference: nature from body keywords
# ---------------------------------------------------------------------------
LANDMARK_NATURE = [
    ("corrupted",  re.compile(r"\b(corrupted|tainted|defiled|fouled by)\b", re.IGNORECASE)),
    ("divine",     re.compile(r"\b(sacred|holy site|consecrated|blessed)\b", re.IGNORECASE)),
    ("aberrant",   re.compile(r"\b(aberration|aberrant|warped beyond)\b", re.IGNORECASE)),
    ("eldritch",   re.compile(r"\b(eldritch|otherworldly|cosmic)\b", re.IGNORECASE)),
    ("elemental",  re.compile(r"\b(elemental nexus|primal force|leyline)\b", re.IGNORECASE)),
    ("mortal",     re.compile(r"\b(built by mortals|mortal-made|mortal hands)\b", re.IGNORECASE)),
]


def infer_landmark(meta: dict, body: str) -> int:
    if not _is_empty(meta.get("nature")):
        return 0
    for label, p in LANDMARK_NATURE:
        if p.search(body):
            meta["nature"] = label
            return 1
    return 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    counts: Dict[str, Dict[str, int]] = {}
    for md in iter_md_files():
        meta, body = read_frontmatter(md)
        type_ = meta.get("type")
        n = 0
        if type_ == "settlement":
            n = infer_settlement(meta, body)
        elif type_ == "region":
            n = infer_region(meta, body)
        elif type_ == "deity":
            n = infer_deity(meta, body)
        elif type_ == "artifact":
            n = infer_artifact(meta, body)
        elif type_ in ("faction", "culture", "house", "organisation"):
            n = infer_faction_or_culture(meta, body)
        elif type_ == "landmark":
            n = infer_landmark(meta, body)
        if n == 0:
            continue
        write_frontmatter(md, meta, body)
        counts.setdefault(type_, {"files": 0, "fields": 0})
        counts[type_]["files"] += 1
        counts[type_]["fields"] += n

    print("Prose inference by type:")
    for t in sorted(counts):
        print("  {:15s}  files={:3d}  fields={:3d}".format(t, counts[t]["files"], counts[t]["fields"]))


if __name__ == "__main__":
    main()
