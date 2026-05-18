"""Create skeleton files for missing race summaries, promoted realms,
and heavy-impact event stubs.

All skeletons are pure structure — frontmatter only, body empty
except for the title H1. Aaron writes content later at his own pace.
Idempotent: skips files that already exist.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# Allow running as a script from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from refactor.common import (
    DOCS_DIR, REPO_ROOT, write_frontmatter, read_frontmatter, merge_metadata
)

# (relpath, type, extras dict)
RACE_SKELETONS = [
    ("Races/Humans/Elasi/Elasi.md",                "race",  {"lineage": "Human"}),
    ("Races/Humans/Terran/Terran.md",              "race",  {"lineage": "Human"}),
    ("Races/Kyojin/Leonin/Leonin.md",              "race",  {"lineage": "Kyojin"}),
    ("Races/Kyojin/Orcs/Orcs.md",                  "race",  {"lineage": "Kyojin"}),
    ("Races/Grundthains/Dwarves/Dwarves.md",       "race",  {"lineage": "Grundthain"}),
]

PROMOTED_PLANES = [
    "Solirion", "Nihilum", "Thargrun", "Veltharyn",
    "Woudum", "Sigmora", "Infernum", "Imperium",
]

# Heavy-impact event stubs that other notes reference; create as type: event,
# status: stub. Existing files (if any) get only their frontmatter updated.
HEAVY_EVENTS = [
    # (relpath_under_docs, year, era_link)
    ("History/Age of Forging/AF0000 Hexweave Binding.md",
     0, "[[Age of Forging]]"),
    ("History/Age of Forging/AF0000 The Forge Wars.md",
     0, "[[Age of Forging]]"),
    ("History/Age of Stagnation/AS0000 Breaking of the Hexweave Seal.md",
     0, "[[Age of Stagnation]]"),
]

MACHINERY_OF_DEATH = "Cosmology/Creation/Machinery of Death.md"


def create_skeleton(relpath: str, type_: str, extras: dict, title_override: str = None) -> None:
    path = DOCS_DIR / relpath
    title = title_override or path.stem
    metadata = {"type": type_, "status": "stub", "tags": []}
    metadata.update(extras)
    if path.exists():
        existing, body = read_frontmatter(path)
        merged = merge_metadata(existing, metadata)
        write_frontmatter(path, merged, body)
        print("Updated: {}".format(relpath))
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        write_frontmatter(path, metadata, "\n# {}\n".format(title))
        print("Created: {}".format(relpath))


def main() -> None:
    # Race summaries
    for rel, type_, extras in RACE_SKELETONS:
        create_skeleton(rel, type_, extras)

    # Promote single-file plane stubs into their own folders
    for plane in PROMOTED_PLANES:
        old_file = DOCS_DIR / "Realms" / "{}.md".format(plane)
        new_folder = DOCS_DIR / "Realms" / plane
        new_file = new_folder / "{}.md".format(plane)
        if old_file.exists() and not new_file.exists():
            new_folder.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                ["git", "mv",
                 str(old_file.relative_to(REPO_ROOT)),
                 str(new_file.relative_to(REPO_ROOT))],
                cwd=REPO_ROOT, check=True,
            )
            print("Promoted: Realms/{}.md -> Realms/{}/{}.md".format(plane, plane, plane))
        elif not new_file.exists():
            create_skeleton("Realms/{}/{}.md".format(plane, plane), "landmark", {})
        # Ensure typed frontmatter exists either way
        if new_file.exists():
            existing, body = read_frontmatter(new_file)
            updated = merge_metadata(existing, {"type": "landmark", "status": "stub", "tags": []})
            write_frontmatter(new_file, updated, body)

    # Heavy-impact event stubs
    for rel, year, era_link in HEAVY_EVENTS:
        create_skeleton(rel, "event", {"era": era_link, "year": year, "year-display": ""})

    # Machinery of Death — referenced widely, no page exists
    create_skeleton(MACHINERY_OF_DEATH, "cosmic-force", {})


if __name__ == "__main__":
    main()
