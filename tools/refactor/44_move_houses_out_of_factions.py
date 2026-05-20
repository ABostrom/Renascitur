"""Move Houses from factions/ to their own houses/ folder.

Aaron: 'I don't really think the Imperial Houses should be listed as a
faction, because they're sort of a cultural faction.'

Houses are a Firebrand-Empire-specific dynastic concept distinct from
political factions. Restore their own top-level folder so they don't
muddy the factions/ list (and the factions/ view).

The previous Layer 28 folded houses/ -> factions/. This reverses that
specifically for the 12 named Houses (kind: house). Type stays as
'house' so the House.md template's dynamic Contents still works.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from refactor.common import DOCS_DIR, REPO_ROOT, read_frontmatter


def main() -> None:
    factions_dir = DOCS_DIR / "factions"
    houses_dir = DOCS_DIR / "houses"
    houses_dir.mkdir(exist_ok=True)

    moved = 0
    for md in sorted(factions_dir.glob("*.md")):
        meta, _ = read_frontmatter(md)
        if meta.get("type") != "house":
            continue
        target = houses_dir / md.name
        if target.exists():
            print("Skip (target exists): {}".format(md.name))
            continue
        subprocess.run(
            ["git", "mv",
             str(md.relative_to(REPO_ROOT)),
             str(target.relative_to(REPO_ROOT))],
            cwd=REPO_ROOT, check=True, capture_output=True, text=True,
        )
        print("Moved: factions/{} -> houses/{}".format(md.name, md.name))
        moved += 1

    print("---")
    print("Houses moved: {}".format(moved))


if __name__ == "__main__":
    main()
