"""Rename Dwarven sub-faction files to include their leading 'The'.

Aaron's original folder names had 'The' in them (The Tidebound of
Draumhavn, etc.) and character affiliations point to '[[The ...]]'.
My Layer 11 sub-faction self-summary stripped the 'The' from the
filename, breaking the linkage:

  factions/Tidebound of Draumhavn.md      <- file
  affiliation: [[The Tidebound of Draumhavn]]   <- character points here

Wikilink resolution fails because the target file doesn't exist.

Rename via two-step git mv (case-sensitive systems are happy with a
single rename, but on Windows we use temp paths for safety).
"""

from __future__ import annotations

import subprocess
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from refactor.common import DOCS_DIR, REPO_ROOT


RENAMES = [
    ("factions/Tidebound of Draumhavn.md",     "factions/The Tidebound of Draumhavn.md"),
    ("factions/Icebound of Uftine.md",         "factions/The Icebound of Uftine.md"),
    ("factions/Stormbound of Thundrakar.md",   "factions/The Stormbound of Thundrakar.md"),
    ("factions/Flamebound of Magnus' Rest.md", "factions/The Flamebound of Magnus' Rest.md"),
    ("factions/Blackiron Collective.md",       "factions/The Blackiron Collective.md"),
    ("factions/Solaran Federation of Worlds.md", "factions/The Solaran Federation of Worlds.md"),
]


def main() -> None:
    moved = 0
    for src, dst in RENAMES:
        src_p = DOCS_DIR / src
        dst_p = DOCS_DIR / dst
        if dst_p.exists():
            print("Skip (dst exists): {}".format(dst))
            continue
        if not src_p.exists():
            print("Skip (src missing): {}".format(src))
            continue
        try:
            subprocess.run(
                ["git", "mv",
                 str(src_p.relative_to(REPO_ROOT)),
                 str(dst_p.relative_to(REPO_ROOT))],
                cwd=REPO_ROOT, check=True, capture_output=True, text=True,
            )
            print("Renamed: {} -> {}".format(src, dst))
            moved += 1
        except subprocess.CalledProcessError as e:
            print("FAIL: {} -> {} :: {}".format(src, dst, e.stderr.strip()))

    print("---")
    print("Moved: {}".format(moved))


if __name__ == "__main__":
    main()
