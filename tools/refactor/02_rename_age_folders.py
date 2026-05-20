"""Rename History/<numeric age>/ -> History/<canonical name>/ via git mv.

Idempotent: skips already-renamed folders. Also writes era summary
skeleton files if missing.
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

RENAMES = {
    "First Age":  ("Age of the Endless Sun", "ES"),
    "Second Age": ("Age of Forging",         "AF"),
    "Third Age":  ("Age of Stagnation",      "AS"),
    "Fourth Age": ("Age of Night",           "AN"),
}


def ensure_era_summary(new_folder: Path, canonical_name: str, code: str, old_name: str) -> None:
    """Create or update the era summary file at new_folder/<canonical_name>.md."""
    summary = new_folder / "{}.md".format(canonical_name)
    metadata = {
        "type": "era",
        "status": "stub",
        "tags": [],
        "code": code,
        "aliases": [old_name],
    }
    if not summary.exists():
        write_frontmatter(summary, metadata, "\n# {}\n".format(canonical_name))
        print("Created era summary: {}".format(summary.relative_to(REPO_ROOT)))
    else:
        existing, body = read_frontmatter(summary)
        merged = merge_metadata(existing, metadata)
        write_frontmatter(summary, merged, body)
        print("Updated era summary: {}".format(summary.relative_to(REPO_ROOT)))


def main() -> None:
    history = DOCS_DIR / "History"
    for old, (new, code) in RENAMES.items():
        old_path = history / old
        new_path = history / new
        if new_path.exists() and not old_path.exists():
            print("Skip (already renamed): {} -> {}".format(old, new))
            ensure_era_summary(new_path, new, code, old)
            continue
        if not old_path.exists():
            print("WARN: source missing: {}".format(old_path))
            continue
        subprocess.run(
            ["git", "mv",
             str(old_path.relative_to(REPO_ROOT)),
             str(new_path.relative_to(REPO_ROOT))],
            cwd=REPO_ROOT,
            check=True,
        )
        print("Renamed: {} -> {}".format(old, new))
        ensure_era_summary(new_path, new, code, old)


if __name__ == "__main__":
    main()
