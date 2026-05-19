"""Fix case-conflicted moves from the restructure (Races/->races/, Languages/->languages/).

Windows is case-insensitive, so `git mv Races/Foo races/Foo` is a no-op
filesystem-wise. The restructure script's git mv reported success but
the files stayed in the old (uppercase) folders.

Fix: rename through a temporary intermediate, then to the final target.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

# Allow running as a script from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from refactor.common import REPO_ROOT, read_frontmatter, rel_to_docs


def main() -> None:
    # Get the list of still-misplaced files via git
    result = subprocess.run(
        ["git", "ls-files", "docs/"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    tracked = result.stdout.strip().split("\n")

    # Filter to those still under uppercase Races/ or Languages/
    misplaced = [
        f for f in tracked
        if f.startswith("docs/Races/") or f.startswith("docs/Languages/")
    ]
    print("Misplaced files to fix: {}".format(len(misplaced)))

    fixed = 0
    failed = 0
    for f in misplaced:
        # Determine new path: lowercase the top-level folder
        parts = f.split("/")
        if len(parts) < 3:
            continue
        # docs/Races/... -> docs/races/...
        new_parts = ["docs", parts[1].lower()] + parts[2:]
        new_path = "/".join(new_parts)
        if new_path == f:
            continue

        # Two-step: rename to a temp name first (force case change),
        # then rename to the target.
        temp_name = "docs/__rename_temp_{}.md".format(uuid.uuid4().hex)

        try:
            subprocess.run(
                ["git", "mv", f, temp_name],
                cwd=REPO_ROOT, check=True, capture_output=True, text=True,
            )
        except subprocess.CalledProcessError as e:
            print("FAIL temp: {} -> {} :: {}".format(f, temp_name, e.stderr.strip()))
            failed += 1
            continue

        # Now move from temp to final target. Create target's parent dir.
        target = REPO_ROOT / new_path
        target.parent.mkdir(parents=True, exist_ok=True)

        try:
            subprocess.run(
                ["git", "mv", temp_name, new_path],
                cwd=REPO_ROOT, check=True, capture_output=True, text=True,
            )
            fixed += 1
            print("Fixed: {} -> {}".format(f, new_path))
        except subprocess.CalledProcessError as e:
            print("FAIL final: {} -> {} :: {}".format(temp_name, new_path, e.stderr.strip()))
            failed += 1

    print("---")
    print("Fixed: {}".format(fixed))
    print("Failed: {}".format(failed))


if __name__ == "__main__":
    main()
