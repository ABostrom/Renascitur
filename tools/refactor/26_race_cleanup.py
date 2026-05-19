"""Clean up the idiosyncratic race folder structure.

After the restructure, the races/ folder has a few oddly-placed files
due to non-canonical lineage values in their frontmatter:

  races/Elder Races/Kyojin.md          -> races/Kyojin/Kyojin.md
  races/Elder Races/Solaran.md         -> races/Solarans/Solaran.md
  races/Saurian/Slaad.md               -> races/Engineered/Slaad.md
  races/Saurian/                       -> (empty, remove)
  races/Uncategorized/Terran/Mokoweri Human.md  -> races/Humans/Terran/Mokoweri Human.md
  races/Uncategorized/Terran/Thraysian Human.md -> races/Humans/Terran/Thraysian Human.md
  races/Terran/Terran/Imperial Human.md         -> races/Humans/Terran/Imperial Human.md
  races/Terran/Terran/Rahalan.md                -> races/Humans/Terran/Rahalan.md
  races/Terran/Terran/Uftine Human.md           -> races/Humans/Terran/Uftine Human.md
  races/Terran/                        -> (consolidate into Humans/Terran)

Also updates the lineage frontmatter to match the new canonical
location.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import List, Tuple

# Allow running as a script from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from refactor.common import REPO_ROOT, DOCS_DIR, read_frontmatter, write_frontmatter


# (src_relative_to_docs, dst_relative_to_docs, new_lineage_value)
MOVES: List[Tuple[str, str, str]] = [
    ("races/Elder Races/Kyojin.md",                       "races/Kyojin/Kyojin.md",                       "Kyojin"),
    ("races/Elder Races/Solaran.md",                      "races/Solarans/Solaran.md",                    "Solarans"),
    ("races/Saurian/Slaad.md",                            "races/Engineered/Slaad.md",                    "Engineered"),
    ("races/Uncategorized/Terran/Mokoweri Human.md",      "races/Humans/Terran/Mokoweri Human.md",        "Humans"),
    ("races/Uncategorized/Terran/Thraysian Human.md",     "races/Humans/Terran/Thraysian Human.md",       "Humans"),
    ("races/Terran/Terran/Imperial Human.md",             "races/Humans/Terran/Imperial Human.md",        "Humans"),
    ("races/Terran/Terran/Rahalan.md",                    "races/Humans/Terran/Rahalan.md",               "Humans"),
    ("races/Terran/Terran/Uftine Human.md",               "races/Humans/Terran/Uftine Human.md",          "Humans"),
]


def main() -> None:
    moved = 0
    for src, dst, new_lineage in MOVES:
        src_path = DOCS_DIR / src
        dst_path = DOCS_DIR / dst
        if not src_path.exists():
            # Already moved or never existed
            if dst_path.exists():
                print("Skip (already at dst): {}".format(dst))
                # Still update lineage if needed
                meta, body = read_frontmatter(dst_path)
                if meta.get("lineage") != new_lineage:
                    meta["lineage"] = new_lineage
                    write_frontmatter(dst_path, meta, body)
                    print("  updated lineage to {}".format(new_lineage))
            else:
                print("WARN missing: {}".format(src))
            continue
        if dst_path.exists():
            print("WARN dst exists: {}".format(dst))
            continue
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        # Update lineage before move
        meta, body = read_frontmatter(src_path)
        if meta.get("lineage") != new_lineage:
            meta["lineage"] = new_lineage
            write_frontmatter(src_path, meta, body)
        subprocess.run(
            ["git", "mv",
             str(src_path.relative_to(REPO_ROOT)),
             str(dst_path.relative_to(REPO_ROOT))],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        print("Moved: {} -> {}".format(src, dst))
        moved += 1
    print("---")
    print("Moved: {}".format(moved))


if __name__ == "__main__":
    main()
