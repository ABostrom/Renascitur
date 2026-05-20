"""Add explicit prose body links to factions whose Contents are sparse.

Some factions have no characters/sub-factions/orgs pointing to them
yet, so their dynamic Contents would be blank in Obsidian. Add a
short 'Connections' section to each sparse faction's prose body with
wikilinks to entities Aaron will likely associate with them (drawn
from the corpus + known lore). The dynamic Contents block stays where
it is, but the body itself now has navigable links.

Idempotent: only adds the section if the file doesn't already have
one with the AUTO-CONNECTIONS marker.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from refactor.common import DOCS_DIR, read_frontmatter, write_frontmatter


MARKER = "<!-- AUTO-CONNECTIONS — safe to edit; will not be re-injected -->"


# Per-faction Connections section, inserted BEFORE the `## Contents`
# dynamic block. Each entry's keys are wikilink targets to known
# entities in the vault.
CONNECTIONS: Dict[str, str] = {
    "Dwarven Holds.md": (
        "\n## Connections\n\n" + MARKER + "\n\n"
        "- **Sub-factions**: [[The Tidebound of Draumhavn]], [[The Icebound of Uftine]], "
        "[[The Stormbound of Thundrakar]], [[The Flamebound of Magnus' Rest]]\n"
        "- **Race**: [[Dwarf]] (a lineage of the [[Grundthain]])\n"
        "- **Allied with**: [[Firebrand Empire]] via the Deepline railway\n"
        "- **Patron deity**: [[Muradin]] (in his original [[Grundthain]] form)\n"
        "- **Concept**: [[Hexweave]] — the cosmic structure their forges helped bind\n"
        "- **Magic disciplines**: [[Rune Magic]], [[Forge Magic]]\n"
    ),
    "Rahalan Nomads.md": (
        "\n## Connections\n\n" + MARKER + "\n\n"
        "- **Race**: [[Rahalan]] (a [[Human]] variant)\n"
        "- **Homeland**: desert provinces of [[Qethusiyya]] (especially [[Al-Ramal]])\n"
        "- **Vessels**: Gaia-ships — living craft (referenced in lore)\n"
        "- **Magic**: [[Primal]], [[Divine]]\n"
        "- **Roles**: Dreamweavers, Grove Shapers, Battle Sisters\n"
        "- **Realm**: [[Renascita]]\n"
    ),
    "The Order of Magnus.md": (
        "\n## Connections\n\n" + MARKER + "\n\n"
        "- **Parent faction**: [[The Flamebound of Magnus' Rest]]\n"
        "- **Honors**: [[Magnus]] (the Luxar deity), [[Muradin]] (the ancestral patron)\n"
        "- **Seat**: [[Magnus' Rest]]\n"
        "- **Realm**: [[Renascita]]\n"
        "- **Magic**: [[Divine]], [[Forge Magic]]\n"
    ),
    "Souls of the Devourer.md": (
        "\n## Connections\n\n" + MARKER + "\n\n"
        "- **Worship**: [[Ishna]], the [[Aberrations]], the [[Machinery of Death]]\n"
        "- **Era of relevance**: [[Age of Stagnation]] onward\n"
        "- **Nature**: [[Corruption]]\n"
        "- **Adversaries**: [[Luxar Gods]], the [[Hexweave]]\n"
        "- **Realm**: [[Renascita]]\n"
    ),
    "Weavers of Agony.md": (
        "\n## Connections\n\n" + MARKER + "\n\n"
        "- **Patron**: [[Varkhaal Bloodlash]] (the First Fang)\n"
        "- **Era of emergence**: [[Age of Stagnation]]\n"
        "- **Nature**: [[Corruption]], aberrant ritual practice\n"
        "- **Magic**: [[Soul Magic]] (corrupted)\n"
        "- **Adversaries**: [[Luxar Gods]], the [[Saurian Enclave]]\n"
        "- **Realm**: [[Renascita]]\n"
    ),
    "Velkhar Dominion.md": (
        "\n## Connections\n\n" + MARKER + "\n\n"
        "- **Society form**: imperial monarchy with lawful-evil alignment\n"
        "- **Realm**: [[Renascita]]\n"
        "- **Adversaries**: [[Firebrand Empire]], [[Dwarven Holds]]\n"
        "- **Era**: [[Age of Night]] presence\n"
    ),
    "People of Mokoweri.md": (
        "\n## Connections\n\n" + MARKER + "\n\n"
        "- **Race**: [[Mokoweri Human]]\n"
        "- **Continent**: [[Mokoweri]]\n"
        "- **Allied with**: [[Saurian Enclave]] via ancestral covenant\n"
        "- **Notable group**: [[Tyrannosaurs of Mokoweri]]\n"
        "- **Magic**: [[Primal]]\n"
        "- **Society**: tribal, spiritual, agrarian\n"
    ),
}


def main() -> None:
    factions_dir = DOCS_DIR / "factions"
    added = 0
    for filename, section in CONNECTIONS.items():
        path = factions_dir / filename
        if not path.exists():
            print("Skip (missing): {}".format(filename))
            continue
        meta, body = read_frontmatter(path)
        if MARKER in body:
            print("Skip (already has connections): {}".format(filename))
            continue
        # Insert BEFORE the existing '## Contents' if any, else at end of body
        contents_idx = body.find("\n## Contents")
        if contents_idx == -1:
            contents_idx = body.find("---\n\n## Contents")
        if contents_idx == -1:
            # Append at end of body
            new_body = body.rstrip() + section
        else:
            new_body = body[:contents_idx].rstrip() + section + body[contents_idx:]
        write_frontmatter(path, meta, new_body)
        print("Connections added: {}".format(filename))
        added += 1
    print("---")
    print("Factions fleshed: {}".format(added))


if __name__ == "__main__":
    main()
