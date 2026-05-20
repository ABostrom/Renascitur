"""Remove hierarchical pseudo-tags (`category/value` form) that were
shadowing property data.

The Layer-12 tag extraction (commit df387e82) lifted folder-implied
categories into hierarchical tags like `continent/pyrosia`,
`faction/saurian-enclave`, `pantheon/noxar-gods`. On reflection these
are not tags at all — they duplicate properties (`continent:`,
`affiliation:`, `pantheon:`, etc.) that already exist on the same
files. Tags should be reserved for thematic/motif labels.

This script:
  - Strips any tag matching `<word>/<words>` where the word looks
    like a category prefix from the Layer-12 set.
  - Preserves all flat tags (Aaron's pre-existing categorization)
    and any non-Layer-12 hierarchical tag.

Idempotent.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List

# Allow running as a script from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from refactor.common import iter_md_files, read_frontmatter, write_frontmatter


# The exact set of category prefixes Layer-12 introduced.
LAYER12_PREFIXES = {
    "realm",
    "continent",
    "region",
    "place",
    "faction",
    "faction-kind",
    "pantheon",
    "era",
    "lineage",
    "race",
    "kind",
    "category",
    "discipline",
}


def is_pseudo_tag(t: str) -> bool:
    if not isinstance(t, str):
        return False
    if "/" not in t:
        return False
    prefix = t.split("/", 1)[0]
    return prefix in LAYER12_PREFIXES


def clean_tags(tags) -> tuple:
    """Return (new_tags_list, removed_count). Handles list/string/None."""
    if tags is None:
        return None, 0
    if isinstance(tags, str):
        if is_pseudo_tag(tags):
            return [], 1
        return tags, 0
    if not isinstance(tags, list):
        return tags, 0
    kept = []
    removed = 0
    for t in tags:
        if is_pseudo_tag(t):
            removed += 1
        else:
            kept.append(t)
    return kept, removed


def main() -> None:
    files_changed = 0
    tags_removed = 0
    for md in iter_md_files():
        meta, body = read_frontmatter(md)
        if "tags" not in meta:
            continue
        new_tags, removed = clean_tags(meta["tags"])
        if removed == 0:
            continue
        meta["tags"] = new_tags
        write_frontmatter(md, meta, body)
        files_changed += 1
        tags_removed += removed

    print("Files changed: {}".format(files_changed))
    print("Pseudo-tags removed: {}".format(tags_removed))


if __name__ == "__main__":
    main()
