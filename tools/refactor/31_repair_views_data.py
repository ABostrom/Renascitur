"""Repair the view-data quality issues Aaron flagged.

Two distinct fixes:

1. Deduplicate `## Contents` sections in 17 files.
   Some files have an orphan `## Contents` header (without marker)
   immediately before the real auto-injected section. This happened
   because earlier passes wrote empty Contents headers, then later
   injection added the real one without recognising the orphan.

   Pattern to strip:
       (---)?
       \n## Contents\n+
       (---)?
       \n## Contents\n\n<MARKER>...

   Keep only the LAST `## Contents` section (the one with MARKER).

2. Settlement schema gap: 17 settlements lack `size`, `controlled_by`,
   `populated_by`, `era_founded` fields. Layer 14's
   SCHEMA_EXTENSIONS["settlement"] missed these. Add empty defaults
   to existing settlement files (merge-only).

   Also adds the missing fields to other types that may have gaps.

3. Field normalisation: rename old field names to canonical:
     - `society` -> `controlled_by` (on settlements)
     - `province` -> `region` (on settlements)
     - `faction_control` -> `controlled_by`
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any, Dict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from refactor.common import iter_md_files, read_frontmatter, write_frontmatter, rel_to_docs


MARKER = "<!-- AUTO-INJECTED-DYNAMIC-CONTENTS"


# ---------------------------------------------------------------------------
# 1. Deduplicate Contents sections
# ---------------------------------------------------------------------------

def dedupe_contents_sections(body: str) -> tuple:
    """If multiple `## Contents` exist, keep only the LAST one
    (the one with the AUTO-INJECTED marker).
    Returns (new_body, changed).
    """
    # Find all positions of `## Contents` headers
    indices = []
    start = 0
    while True:
        i = body.find("## Contents", start)
        if i == -1:
            break
        indices.append(i)
        start = i + len("## Contents")
    if len(indices) <= 1:
        return body, False

    first = indices[0]
    last = indices[-1]

    # The kept block starts at `last`. We need to chop everything from
    # the first Contents header (plus its preceding separator) up to it.
    before_first = body[:first]
    # Strip trailing whitespace and a trailing `---` separator if present
    trimmed = before_first.rstrip()
    if trimmed.endswith("---"):
        trimmed = trimmed[:-3].rstrip()

    new_body = trimmed + "\n\n---\n\n" + body[last:]
    return new_body, True


# ---------------------------------------------------------------------------
# 2. Schema gap fix per type
# ---------------------------------------------------------------------------

SCHEMA_GAPS: Dict[str, Dict[str, Any]] = {
    "settlement": {
        "size": "",
        "controlled_by": "",
        "populated_by": [],
        "era_founded": "",
    },
    "region": {
        "settlements": [],
    },
    "continent": {
        # already had a rich schema
    },
    "faction": {
        "leadership": [],
    },
}


def fill_schema_gaps(meta: dict) -> tuple:
    """Add missing fields per type. Merge-only. Returns (new_meta, changed)."""
    type_ = meta.get("type")
    if type_ not in SCHEMA_GAPS:
        return meta, False
    out = dict(meta)
    changed = False
    for k, v in SCHEMA_GAPS[type_].items():
        if k not in out:
            out[k] = v
            changed = True
    return out, changed


# ---------------------------------------------------------------------------
# 3. Field name normalisation
# ---------------------------------------------------------------------------

FIELD_RENAMES_BY_TYPE: Dict[str, Dict[str, str]] = {
    "settlement": {
        "society":         "controlled_by",
        "province":        "region",
        "faction_control": "controlled_by",
    },
    "continent": {
        "society":         "controlled_by",
    },
    "region": {
        "society":         "controlled_by",
    },
    "landmark": {
        "society":         "controlled_by",
    },
}


def normalise_field_names(meta: dict) -> tuple:
    """Rename old field names to canonical. Returns (new_meta, changed)."""
    type_ = meta.get("type")
    if type_ not in FIELD_RENAMES_BY_TYPE:
        return meta, False
    out = dict(meta)
    changed = False
    for old, new in FIELD_RENAMES_BY_TYPE[type_].items():
        if old in out:
            # If new field already has a value, prefer the old's value only when new is empty
            if new in out and out[new] not in ("", None, [], False):
                # New field already populated; drop the old (it's stale)
                del out[old]
            else:
                out[new] = out[old]
                del out[old]
            changed = True
    return out, changed


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    deduped = 0
    schema_added = 0
    fields_renamed = 0
    total_changed = 0

    for md in iter_md_files():
        meta, body = read_frontmatter(md)
        any_change = False

        # 3. Field name normalisation (before schema gaps so they don't fight)
        meta, c = normalise_field_names(meta)
        if c:
            fields_renamed += 1
            any_change = True

        # 2. Schema gaps
        meta, c = fill_schema_gaps(meta)
        if c:
            schema_added += 1
            any_change = True

        # 1. Deduplicate Contents
        new_body, c = dedupe_contents_sections(body)
        if c:
            deduped += 1
            body = new_body
            any_change = True

        if any_change:
            write_frontmatter(md, meta, body)
            total_changed += 1

    print("Files changed: {}".format(total_changed))
    print("  Contents dedupe: {}".format(deduped))
    print("  Schema gaps filled: {}".format(schema_added))
    print("  Fields renamed: {}".format(fields_renamed))


if __name__ == "__main__":
    main()
