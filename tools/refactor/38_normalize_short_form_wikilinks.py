"""Replace short-form wikilinks with their canonical long forms.

Many references use short forms like [[Firebrand]] (29 occurrences) or
[[Human]] (23) that resolved via aliases in Obsidian but were treated
as different Link objects in Dataview — making `contains(file.outlinks,
this.file.link)` queries miss them.

This script does in-text find/replace on wikilinks:
  [[Firebrand]]                 -> [[Firebrand Empire]]
  [[Human]]                     -> [[Human]] (no change — Human page now exists)
  [[Tidebound]]                 -> [[The Tidebound of Draumhavn]]
  [[Icebound]]                  -> [[The Icebound of Uftine]]
  ...

After this, every short-form reference is rewritten to the canonical
full name, so Dataview queries match cleanly.

Preserves alias text after pipe: [[Firebrand|the empire]] -> [[Firebrand Empire|the empire]]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Dict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from refactor.common import DOCS_DIR, REPO_ROOT


# Short-form -> canonical full form mappings.
# Only rewrite when the short form is unambiguous.
NORMALIZE: Dict[str, str] = {
    # Factions
    "Firebrand":                        "Firebrand Empire",
    "The Firebrand Empire":             "Firebrand Empire",
    "Magocracy":                        "Thraysian Magocracy",
    "The Magocracy":                    "Thraysian Magocracy",
    "The Saurian Enclave":              "Saurian Enclave",
    "The Dwarven Holds":                "Dwarven Holds",
    "The Rahalan Nomads":               "Rahalan Nomads",
    "Blackiron Collective":             "The Blackiron Collective",
    "Blackiron":                        "The Blackiron Collective",
    "Mokoweri People":                  "People of Mokoweri",
    "Velkhar":                          "Velkhar Dominion",
    "Solaran Federation":               "The Solaran Federation of Worlds",
    "Solaran Federation of Worlds":     "The Solaran Federation of Worlds",

    # Sub-factions — short forms used by characters
    "Tidebound":                        "The Tidebound of Draumhavn",
    "Tidebound of Draumhavn":           "The Tidebound of Draumhavn",
    "Icebound":                         "The Icebound of Uftine",
    "Icebound of Uftine":               "The Icebound of Uftine",
    "Stormbound":                       "The Stormbound of Thundrakar",
    "Stormbound of Thundrakar":         "The Stormbound of Thundrakar",
    "Flamebound":                       "The Flamebound of Magnus' Rest",
    "Flamebound of Magnus' Rest":       "The Flamebound of Magnus' Rest",

    # Pantheons
    "Noxar":                            "Noxar Gods",
    "Noxar Pantheon":                   "Noxar Gods",
    "Pantheon Of Noxar":                "Noxar Gods",
    "Luxar":                            "Luxar Gods",
    "Luxar Pantheon":                   "Luxar Gods",
    "Pantheon Of Luxar":                "Luxar Gods",
    "Luxan":                            "Luxar Gods",
    "God Hand":                         "The God Hand",
    "Quintumvirate":                    "The God Hand",
    "Elemental Pantheon":               "Elementals",
    "Elemental Gods":                   "Elementals",

    # Realms / continents
    "Renascitur":                       "Renascita",  # collapse world -> primary mortal continent
    "Mokoweri Island":                  "Mokoweri",

    # Aberrations
    "Aberration":                       "Aberrations",
    "aberrant":                         "Aberrations",
    "Aberrant":                         "Aberrations",

    # The Hexweave
    "The Hexweave":                     "Hexweave",
}


# Pattern: [[target]] or [[target|display]]
WIKILINK_RE = re.compile(r"\[\[([^\]|]+?)(\|[^\]]+?)?\]\]")


def normalize_wikilinks_in_text(text: str) -> tuple:
    """Rewrite short-form wikilinks. Returns (new_text, count)."""
    count = 0

    def _sub(m):
        nonlocal count
        target = m.group(1).strip()
        alias_part = m.group(2) or ""
        # Strip any path prefix
        bare = target.split("/")[-1]
        if bare.endswith(".md"):
            bare = bare[:-3]
        canonical = NORMALIZE.get(bare)
        if canonical and canonical != bare:
            count += 1
            return "[[{}{}]]".format(canonical, alias_part)
        return m.group(0)

    new_text = WIKILINK_RE.sub(_sub, text)
    return new_text, count


def main() -> None:
    files_changed = 0
    total = 0

    targets = list(DOCS_DIR.rglob("*.md"))
    templates_dir = REPO_ROOT / "templates"
    if templates_dir.exists():
        targets.extend(sorted(templates_dir.glob("*.md")))

    for path in targets:
        text = path.read_text(encoding="utf-8")
        new_text, n = normalize_wikilinks_in_text(text)
        if n == 0:
            continue
        with path.open("w", encoding="utf-8", newline="\n") as fh:
            fh.write(new_text)
        files_changed += 1
        total += n

    print("Files changed: {}".format(files_changed))
    print("Wikilinks rewritten: {}".format(total))


if __name__ == "__main__":
    main()
