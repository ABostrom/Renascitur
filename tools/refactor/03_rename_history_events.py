"""Rename History/<age>/<title>.md to <CODE><YYYY> <title>.md.

Year is extracted from frontmatter `year:` if present and integer,
otherwise defaults to 0000 (undated within era). Skips the era
summary file itself (matches "<age folder>/<canonical name>.md").

Adds the old title as an alias in frontmatter so existing
[[Hexweave Binding]] wikilinks still resolve to the renamed file.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Allow running as a script from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from refactor.common import (
    DOCS_DIR, read_frontmatter, write_frontmatter, git_mv, merge_metadata
)

AGE_CODE = {
    "Age of the Endless Sun": "ES",
    "Age of Forging":         "AF",
    "Age of Stagnation":      "AS",
    "Age of Night":           "AN",
}

PREFIX_RE = re.compile(r"^(ES|AF|AS|AN)\d{4} ")


def main() -> None:
    history = DOCS_DIR / "History"
    for age_folder, code in AGE_CODE.items():
        folder = history / age_folder
        if not folder.exists():
            print("WARN: missing {}".format(folder))
            continue
        era_summary = folder / "{}.md".format(age_folder)
        for md in sorted(folder.glob("*.md")):
            if md == era_summary:
                continue
            name = md.name
            if PREFIX_RE.match(name):
                print("Skip (already prefixed): {}".format(name))
                continue
            meta, body = read_frontmatter(md)
            year = meta.get("year", 0)
            if not isinstance(year, int) or year < 0:
                year = 0
            year_str = "{:04d}".format(year)
            stem = md.stem  # filename without .md
            new_name = "{}{} {}.md".format(code, year_str, stem)
            new_path = md.with_name(new_name)
            if new_path.exists():
                print("WARN: target exists, skipping: {}".format(new_name))
                continue

            # Add old title as alias before rename
            existing_aliases = meta.get("aliases", [])
            if not isinstance(existing_aliases, list):
                existing_aliases = [existing_aliases]
            if stem not in existing_aliases:
                existing_aliases.append(stem)
            year_display = "{} {}".format(code, year) if year else "{} (undated)".format(code)
            updated_meta = merge_metadata(meta, {
                "aliases": existing_aliases,
                "year-display": year_display,
            })
            # Force overwrite of aliases/year-display since merge_metadata
            # preserves existing values for non-list keys.
            updated_meta["aliases"] = existing_aliases
            updated_meta["year-display"] = year_display
            write_frontmatter(md, updated_meta, body)

            git_mv(md, new_path)
            print("Renamed: {}/{} -> {}".format(age_folder, name, new_name))


if __name__ == "__main__":
    main()
