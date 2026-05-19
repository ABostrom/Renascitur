"""Rename History/<age>/<title>.md to <CODE><YYYYY> <title>.md.

The numeric portion is the in-world year, sourced in priority order from:
  1. frontmatter `aat-event-start-date` (Advanced Timeline plugin field —
     Aaron's existing per-event dating system)
  2. frontmatter `year`
  3. 0 (undated within era)

Padded to 5 digits to handle the existing absolute-timeline range
(current max ~12000) with headroom up to 99999.

Skips the era summary file itself. Idempotent: re-running after dates
are updated will re-rename to the corrected prefix; existing aliases
are preserved.

Adds the original (pre-prefix) title as an alias in frontmatter so
existing [[Hexweave Binding]] wikilinks still resolve.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Allow running as a script from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from refactor.common import (
    DOCS_DIR, read_frontmatter, write_frontmatter, git_mv
)

AGE_CODE = {
    "Age of the Endless Sun": "ES",
    "Age of Forging":         "AF",
    "Age of Stagnation":      "AS",
    "Age of Night":           "AN",
}

# Matches any of our age codes followed by 4-6 digits and 1+ trailing spaces.
# Tolerates both old 4-digit and new 5-digit padding, and double-space artifacts
# from a prior buggy run, so this script is idempotent.
PREFIX_RE = re.compile(r"^(ES|AF|AS|AN)\d{4,6} +")

PAD_WIDTH = 5


def extract_year(meta: dict) -> int:
    """Return an integer year from frontmatter, in priority order."""
    for key in ("aat-event-start-date", "year"):
        val = meta.get(key)
        if isinstance(val, int) and val >= 0:
            return val
        if isinstance(val, str):
            try:
                n = int(val)
                if n >= 0:
                    return n
            except ValueError:
                pass
    return 0


def strip_prefix(stem: str) -> str:
    """Remove a leading <CODE><digits> + whitespace prefix from a filename stem."""
    m = PREFIX_RE.match(stem)
    if m:
        return stem[m.end():]
    return stem


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
            meta, body = read_frontmatter(md)
            year = extract_year(meta)
            year_str = "{:0{w}d}".format(year, w=PAD_WIDTH)

            # Canonical stem without any existing CODE-digits prefix.
            current_stem = md.stem
            canonical_stem = strip_prefix(current_stem)
            new_name = "{}{} {}.md".format(code, year_str, canonical_stem)

            # Build the cleaned/canonical metadata that should be on the file
            # whether or not we rename.
            raw_aliases = meta.get("aliases", [])
            if not isinstance(raw_aliases, list):
                raw_aliases = [raw_aliases]
            seen = set()
            cleaned_aliases = []
            for a in raw_aliases:
                if isinstance(a, str):
                    cleaned = a.strip()
                    if cleaned and cleaned not in seen:
                        seen.add(cleaned)
                        cleaned_aliases.append(cleaned)
            if canonical_stem not in seen:
                cleaned_aliases.append(canonical_stem)
            year_display = "{} {}".format(code, year) if year else "{} (undated)".format(code)

            metadata_needs_write = (
                meta.get("aliases") != cleaned_aliases
                or meta.get("year") != year
                or meta.get("year-display") != year_display
            )

            if metadata_needs_write:
                meta["aliases"] = cleaned_aliases
                meta["year"] = year
                meta["year-display"] = year_display
                write_frontmatter(md, meta, body)

            if name == new_name:
                if metadata_needs_write:
                    print("Updated metadata: {}".format(name))
                else:
                    print("Skip (already correct): {}".format(name))
                continue

            new_path = md.with_name(new_name)
            if new_path.exists() and new_path != md:
                print("WARN: target exists, skipping: {}".format(new_name))
                continue

            git_mv(md, new_path)
            print("Renamed: {}/{} -> {}".format(age_folder, name, new_name))


if __name__ == "__main__":
    main()
