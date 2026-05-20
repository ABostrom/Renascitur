"""Link characters to their Great House via surname matching.

Each of the 12 Firebrand Great Houses (House Cannith, Deneith, Jorasco,
Kundarak, Lyrandar, Medani, Orien, Phiarlan, Silverhand, Sivis,
Tharashk, Vadalis) has 0 affiliated characters because characters
affiliate generically with [[Firebrand Empire]], not their specific
House. But many character filenames end with the house surname:

  Breven Deneith.md, Brakka Orien.md, Kwanti Orien.md, etc.

This script:
  1. Reads every character file.
  2. If the last word of the filename matches a house surname, adds
     `house: [[House X]]` to frontmatter (merge-only).
  3. Also adds `house` field to the Character template.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from refactor.common import DOCS_DIR, REPO_ROOT, read_frontmatter, write_frontmatter


HOUSE_SURNAMES = {
    "Cannith":    "[[House Cannith]]",
    "Deneith":    "[[House Deneith]]",
    "Jorasco":    "[[House Jorasco]]",
    "Kundarak":   "[[House Kundarak]]",
    "Lyrandar":   "[[House Lyrandar]]",
    "Medani":     "[[House Medani]]",
    "Orien":      "[[House Orien]]",
    "Phiarlan":   "[[House Phiarlan]]",
    "Silverhand": "[[House Silverhand]]",
    "Sivis":      "[[House Sivis]]",
    "Tharashk":   "[[House Tharashk]]",
    "Vadalis":    "[[House Vadalis]]",
}


def main() -> None:
    characters_dir = DOCS_DIR / "characters"
    if not characters_dir.exists():
        print("No characters/ folder")
        return

    linked = 0
    for md in sorted(characters_dir.glob("*.md")):
        stem = md.stem
        # Extract last word as potential surname
        last_word = stem.split()[-1] if " " in stem else stem
        house_link = HOUSE_SURNAMES.get(last_word)
        if not house_link:
            continue

        meta, body = read_frontmatter(md)
        if meta.get("type") != "character":
            continue
        if meta.get("house") == house_link:
            continue  # already set
        meta["house"] = house_link
        write_frontmatter(md, meta, body)
        print("Linked {} -> {}".format(stem, house_link))
        linked += 1

    # Also add `house: ''` to the Character template so future notes have it
    char_template = REPO_ROOT / "templates" / "Character.md"
    if char_template.exists():
        meta, body = read_frontmatter(char_template)
        if "house" not in meta:
            meta["house"] = ""
            write_frontmatter(char_template, meta, body)
            print("Added house field to Character template")

    print("---")
    print("Characters linked to a House: {}".format(linked))


if __name__ == "__main__":
    main()
