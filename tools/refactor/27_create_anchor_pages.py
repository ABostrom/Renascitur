"""Create the missing anchor pages.

After the restructure several major entities have no self-summary page
even though their children exist:
  - Dwarven Holds (parent of 4 sub-holds)
  - Saurian Enclave (had only the Archive + Elders)
  - The Solaran Federation of Worlds (historical)
  - Noxar Gods, Luxar Gods, The God Hand, Elementals (pantheon hubs)
  - Hexweave (cosmological structure referenced widely; no page)

All are structural anchor files: frontmatter + minimal placeholder body.
Aaron writes the prose later.

Pantheon pages get embedded Dataview blocks listing their deities.
Faction pages will pick up the standard dynamic-Contents blocks via
the next injection pass (re-run 08_inject_dynamic_blocks.py).

Idempotent — skips existing files.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict

# Allow running as a script from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from refactor.common import DOCS_DIR, write_frontmatter


# ---------------------------------------------------------------------------
# Faction self-summaries (go into factions/)
# ---------------------------------------------------------------------------
FACTIONS: Dict[str, Dict[str, Any]] = {
    "Dwarven Holds.md": {
        "type": "faction",
        "status": "stub",
        "tags": [],
        "realm": "[[Renascita]]",
        "nature": "mortal",
        "importance": "major",
        "alignment": "lawful-neutral",
        "society_form": "feudal",
        "government": "tribal-council",
        "economy": "mining",
        "seat": "",
        "size": "continental",
        "allies": ["[[Firebrand Empire]]"],
        "rivals": [],
        "magic": ["[[Rune Magic]]", "[[Forge Magic]]"],
        "_body": (
            "\n# Dwarven Holds\n\n"
            "*The four united holds of the Grundthain dwarves — Tidebound, "
            "Icebound, Stormbound, and Flamebound — bound by ancestral alliance "
            "and the great subterranean railway that links their cities.*\n"
        ),
    },
    "Saurian Enclave.md": {
        "type": "faction",
        "status": "stub",
        "tags": [],
        "realm": "[[Renascita]]",
        "nature": "bioengineered",
        "importance": "major",
        "alignment": "neutral-good",
        "society_form": "theocratic",
        "government": "theocracy",
        "economy": "agrarian",
        "seat": "[[Aeloria]]",
        "size": "regional",
        "allies": [],
        "rivals": [],
        "magic": ["[[Primal]]", "[[Divine]]"],
        "_body": (
            "\n# Saurian Enclave\n\n"
            "*The Saurian society of Mokoweri, guided by the Elder council and the "
            "ancient covenant with the Solaran creators. Keepers of the Archive of "
            "the Ancients and stewards of the Aeloria tree-city.*\n"
        ),
    },
    "The Solaran Federation of Worlds.md": {
        "type": "faction",
        "status": "stub",
        "tags": [],
        "realm": "[[Renascita]]",
        "nature": "celestial",
        "importance": "legendary",
        "alignment": "lawful-good",
        "society_form": "imperial",
        "government": "magocratic-council",
        "economy": "magical",
        "seat": "[[Solara]]",
        "size": "cosmic",
        "era_founded": "[[Age of the Endless Sun]]",
        "era_dissolved": "[[Age of the Endless Sun]]",
        "allies": [],
        "rivals": [],
        "magic": ["[[Arcanometry]]", "[[Astral Weaving]]"],
        "_body": (
            "\n# The Solaran Federation of Worlds\n\n"
            "*The lost interstellar civilization of the Solarans, whose Endless Sun "
            "lit the heavens until its fall. Their works, like the Saurians and the "
            "World Trees, outlived them.*\n"
        ),
    },
}


# ---------------------------------------------------------------------------
# Pantheon hub pages (go into deities/<pantheon>/<pantheon>.md so they sit
# inside the pantheon folder as the pantheon's own summary)
# ---------------------------------------------------------------------------
PANTHEONS: Dict[str, Dict[str, Any]] = {
    "Noxar/Noxar Gods.md": {
        "type": "essay",
        "status": "stub",
        "tags": [],
        "topic": "pantheon",
        "realm": "[[Renascitur]]",
        "era": "[[Age of Stagnation]]",
        "_body": (
            "\n# The Noxar Pantheon\n\n"
            "*The dark gods of the Third Age — Noxarian and his court of suffering, "
            "decay, deception, and dominion.*\n\n"
            "## Deities of this pantheon\n\n"
            "```dataview\n"
            "LIST FROM \"deities\" WHERE pantheon = this.file.link\n"
            "SORT file.name ASC\n"
            "```\n"
        ),
    },
    "Luxar/Luxar Gods.md": {
        "type": "essay",
        "status": "stub",
        "tags": [],
        "topic": "pantheon",
        "realm": "[[Renascitur]]",
        "era": "[[Age of Stagnation]]",
        "_body": (
            "\n# The Luxar Pantheon\n\n"
            "*The bright gods — those who chose light over shadow when the Third "
            "Age dawned. Patrons of mortals, defenders against the corruption.*\n\n"
            "## Deities of this pantheon\n\n"
            "```dataview\n"
            "LIST FROM \"deities\" WHERE pantheon = this.file.link\n"
            "SORT file.name ASC\n"
            "```\n"
        ),
    },
    "God Hand/The God Hand.md": {
        "type": "essay",
        "status": "stub",
        "tags": [],
        "topic": "pantheon",
        "realm": "[[Renascitur]]",
        "era": "[[Age of the Endless Sun]]",
        "_body": (
            "\n# The God Hand\n\n"
            "*The Quintumvirate — five corrupted elder Grundthain who became the "
            "hands of Ishna: Cronus the Endless, Hyperion the Fallen, Tau Sin "
            "Manifest, Typhon the Archon of Death, and Arachnie the Matriarch of "
            "Pain.*\n\n"
            "## The Five\n\n"
            "```dataview\n"
            "LIST FROM \"deities\" WHERE pantheon = this.file.link\n"
            "SORT file.name ASC\n"
            "```\n"
        ),
    },
    "Elementals/Elementals.md": {
        "type": "essay",
        "status": "stub",
        "tags": [],
        "topic": "pantheon",
        "realm": "[[Renascitur]]",
        "era": "[[Age of the Endless Sun]]",
        "_body": (
            "\n# The Elementals\n\n"
            "*The four cosmic elemental forces given form — Leviathan of the "
            "waters, Phenos of fire, Tempus of air, and Zaratan of earth. Older "
            "than the mortal world, they are its bedrock and its weather.*\n\n"
            "## The Four\n\n"
            "```dataview\n"
            "LIST FROM \"deities\" WHERE pantheon = this.file.link\n"
            "SORT file.name ASC\n"
            "```\n"
        ),
    },
}


# ---------------------------------------------------------------------------
# Concept page (cosmic-force)
# ---------------------------------------------------------------------------
CONCEPTS: Dict[str, Dict[str, Any]] = {
    "Hexweave.md": {
        "type": "cosmic-force",
        "status": "stub",
        "tags": [],
        "realm": "[[Renascitur]]",
        "nature": "eldritch",
        "importance": "legendary",
        "alignment": "",
        "_body": (
            "\n# The Hexweave\n\n"
            "*The great cosmological lattice bound during the Age of Forging to "
            "seal Ishna and the Aberrations. Its breaking in the Age of Stagnation "
            "let the corruption seep back into the world.*\n\n"
            "## Referenced in\n\n"
            "```dataview\n"
            "LIST WHERE contains(file.inlinks, this.file.link)\n"
            "SORT file.name ASC\n"
            "```\n"
        ),
    },
}


def create_file(path: Path, fields: Dict[str, Any]) -> bool:
    if path.exists():
        print("Skip (exists): {}".format(path.relative_to(DOCS_DIR.parent)))
        return False
    body = fields.pop("_body", "\n")
    path.parent.mkdir(parents=True, exist_ok=True)
    write_frontmatter(path, fields, body)
    print("Created: {}".format(path.relative_to(DOCS_DIR.parent)))
    return True


def main() -> None:
    created = 0
    factions_dir = DOCS_DIR / "factions"
    for name, fields in FACTIONS.items():
        if create_file(factions_dir / name, dict(fields)):
            created += 1

    deities_dir = DOCS_DIR / "deities"
    for relpath, fields in PANTHEONS.items():
        if create_file(deities_dir / relpath, dict(fields)):
            created += 1

    cosmic_dir = DOCS_DIR / "cosmic-forces"
    for name, fields in CONCEPTS.items():
        if create_file(cosmic_dir / name, dict(fields)):
            created += 1

    print("---")
    print("Created: {}".format(created))


if __name__ == "__main__":
    main()
