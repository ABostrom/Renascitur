"""Append the same dynamic-contents Dataview blocks to container-type templates.

When you create a new note from one of these templates via Templater, the
new note inherits the dynamic blocks already wired in — so a freshly-created
Pyrosia2.md would immediately show its contents (if any) once you fill in
the frontmatter.

Reads the SNIPPETS dict from 08_inject_dynamic_blocks.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

# Allow running as a script from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from refactor.common import REPO_ROOT

# Load 08's SNIPPETS (filename starts with a digit so we use importlib).
SPEC = importlib.util.spec_from_file_location(
    "_inject08",
    Path(__file__).resolve().parent / "08_inject_dynamic_blocks.py",
)
INJECT08 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INJECT08)

SNIPPETS = INJECT08.SNIPPETS
MARKER = INJECT08.MARKER

TEMPLATES_DIR = REPO_ROOT / "templates"

# template filename -> type key
TEMPLATE_BY_TYPE = {
    "Continent.md":   "continent",
    "Region.md":      "region",
    "Settlement.md":  "settlement",
    "Era.md":         "era",
    "Faction.md":     "faction",
    "Culture.md":     "culture",
    "Race.md":        "race",
    "House.md":       "house",
}


def main() -> None:
    for filename, type_key in TEMPLATE_BY_TYPE.items():
        path = TEMPLATES_DIR / filename
        if not path.exists():
            print("WARN: missing {}".format(path))
            continue
        text = path.read_text(encoding="utf-8")
        if MARKER in text:
            print("Skip (marker present): {}".format(filename))
            continue
        snippet = SNIPPETS[type_key]
        addition = "\n\n---\n\n## Contents\n\n{}\n{}".format(MARKER, snippet)
        new_text = text.rstrip() + addition + "\n"
        with path.open("w", encoding="utf-8", newline="\n") as fh:
            fh.write(new_text)
        print("Injected: {}".format(filename))


if __name__ == "__main__":
    main()
