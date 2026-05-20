"""Apply the frontmatter migration to every .md under docs/.

Reads:
- inference_preview.csv  (the agreed type-inference output)
- inference_overrides.csv (Aaron's manual overrides)

For each file:
- If inferred_type == "SKIP" or "UNCLASSIFIED", do not modify.
- Otherwise, merge the inferred type, status, and extras into the
  existing frontmatter without overwriting any field Aaron already set.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Dict, Tuple

# Allow running as a script from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from refactor.common import DOCS_DIR, read_frontmatter, write_frontmatter, merge_metadata

HERE = Path(__file__).resolve().parent
PREVIEW = HERE / "inference_preview.csv"
OVERRIDES = HERE / "inference_overrides.csv"


def load_overrides() -> Dict[str, Tuple[str, str]]:
    out: Dict[str, Tuple[str, str]] = {}
    if not OVERRIDES.exists():
        return out
    with OVERRIDES.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            rel = (row.get("relpath") or "").strip()
            if not rel:
                continue
            t = (row.get("override_type") or "").strip()
            s = (row.get("override_status") or "").strip()
            out[rel] = (t, s)
    return out


def main() -> None:
    overrides = load_overrides()
    applied = 0
    skipped = 0
    with PREVIEW.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            rel = row["relpath"]
            type_ = row["inferred_type"]
            status = row["inferred_status"]
            extras = json.loads(row["inferred_extras"]) if row["inferred_extras"] else {}

            if rel in overrides:
                ovr_t, ovr_s = overrides[rel]
                if ovr_t:
                    type_ = ovr_t
                if ovr_s:
                    status = ovr_s

            if type_ in ("SKIP", "UNCLASSIFIED", ""):
                skipped += 1
                continue

            path = DOCS_DIR / rel
            if not path.exists():
                print("WARN: missing {}".format(rel))
                skipped += 1
                continue

            existing, body = read_frontmatter(path)
            new_fields = {"type": type_, "status": status}
            new_fields.update(extras)
            # tags: ensure list exists
            if "tags" not in existing and "tags" not in new_fields:
                new_fields["tags"] = []
            merged = merge_metadata(existing, new_fields)
            write_frontmatter(path, merged, body)
            applied += 1

    print("Applied: {}".format(applied))
    print("Skipped: {}".format(skipped))


if __name__ == "__main__":
    main()
