"""Walk docs/ and produce inference_preview.csv.

Output columns: relpath, size_bytes, has_frontmatter, current_type,
inferred_type, inferred_status, inferred_extras, matched_rule.

Aaron reviews the CSV before running 01_apply_frontmatter.py.
He may edit `inference_overrides.csv` (next to this script) to override
the type for specific files; the apply script reads both.
"""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path

# Allow running as a script from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from refactor.common import DOCS_DIR, iter_md_files, read_frontmatter, rel_to_docs
from refactor.rules import classify

OUTPUT = (Path(__file__).resolve().parent / "inference_preview.csv")
STUB_THRESHOLD_BYTES = 200


def main() -> None:
    rows = []
    for md_path in iter_md_files(DOCS_DIR):
        rel = rel_to_docs(md_path)
        size = md_path.stat().st_size
        meta, _body = read_frontmatter(md_path)
        current_type = meta.get("type", "")

        inferred_type, extras, rule = classify(rel)
        status = "stub" if size < STUB_THRESHOLD_BYTES else "draft"
        # If a file already has frontmatter with status, prefer that
        if "status" in meta:
            status = meta["status"]

        rows.append({
            "relpath": rel,
            "size_bytes": size,
            "has_frontmatter": "yes" if meta else "no",
            "current_type": current_type,
            "inferred_type": inferred_type,
            "inferred_status": status,
            "inferred_extras": json.dumps(extras, ensure_ascii=False),
            "matched_rule": rule,
        })

    with OUTPUT.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    # Quick summary to stdout
    counts = Counter(r["inferred_type"] for r in rows)
    try:
        print("Wrote {}".format(OUTPUT.relative_to(DOCS_DIR.parent)))
    except ValueError:
        print("Wrote {}".format(OUTPUT))
    print("Total notes: {}".format(len(rows)))
    print("By inferred type:")
    for t, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        print("  {:20s} {:5d}".format(t, n))


if __name__ == "__main__":
    main()
