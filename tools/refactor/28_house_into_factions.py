"""Fold houses/ into factions/.

Aaron's observation: 'House is a thing that only exists in the Firebrand
Empire.' Top-level folders should reflect UNIVERSAL types, not culture-
specific subtypes. House is a subtype of faction.

This script:
  - Moves every file in houses/ to factions/
  - Keeps type: house in frontmatter (it's still a valid subtype)
  - Removes the empty houses/ folder
  - Adds 'kind: house' frontmatter for future filtering convenience
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# Allow running as a script from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from refactor.common import REPO_ROOT, DOCS_DIR, read_frontmatter, write_frontmatter


def main() -> None:
    houses_dir = DOCS_DIR / "houses"
    factions_dir = DOCS_DIR / "factions"
    if not houses_dir.exists():
        print("No houses/ folder to migrate.")
        return
    factions_dir.mkdir(exist_ok=True)

    moved = 0
    for md in sorted(houses_dir.glob("*.md")):
        target = factions_dir / md.name
        if target.exists():
            print("Skip (target exists): {}".format(md.name))
            continue
        # Add kind: house to frontmatter so the file stays distinguishable
        meta, body = read_frontmatter(md)
        if meta.get("kind") != "house":
            meta["kind"] = "house"
            write_frontmatter(md, meta, body)
        subprocess.run(
            ["git", "mv",
             str(md.relative_to(REPO_ROOT)),
             str(target.relative_to(REPO_ROOT))],
            cwd=REPO_ROOT, check=True, capture_output=True, text=True,
        )
        print("Moved: houses/{} -> factions/{}".format(md.name, md.name))
        moved += 1

    print("---")
    print("Moved: {}".format(moved))


if __name__ == "__main__":
    main()
