"""Audit broken wikilinks across the corpus.

For every `[[X]]` reference in any file (frontmatter or body),
determine whether X resolves to:
  - An existing file (by stem match)
  - An alias on some file
  - Nothing -- broken link

Outputs `tools/refactor/broken_links.csv` with columns:
  source, target, count, occurrences (paths)

Helps identify the missing anchor files that should exist to make
the dataview views and Obsidian wikilinks fully connect.
"""

from __future__ import annotations

import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from refactor.common import DOCS_DIR, iter_md_files, read_frontmatter, rel_to_docs


WIKILINK_RE = re.compile(r"\[\[([^\]|]+?)(?:\|[^\]]+?)?\]\]")


def main() -> None:
    # Build the resolution table: every filename stem + every alias
    resolvable = set()
    alias_map = {}
    for md in iter_md_files():
        stem = md.stem
        resolvable.add(stem.lower())
        meta, _ = read_frontmatter(md)
        aliases = meta.get("aliases") or []
        if not isinstance(aliases, list):
            aliases = [aliases]
        for a in aliases:
            if isinstance(a, str) and a.strip():
                resolvable.add(a.strip().lower())
                alias_map[a.strip().lower()] = stem

    # Walk every file, count broken-link occurrences
    broken = defaultdict(lambda: {"count": 0, "sources": []})
    total_links = 0
    for md in iter_md_files():
        text = md.read_text(encoding="utf-8")
        rel = rel_to_docs(md)
        for m in WIKILINK_RE.finditer(text):
            target = m.group(1).strip()
            # Strip leading folder paths (Obsidian path-prefixed links)
            target = target.split("/")[-1]
            if target.endswith(".md"):
                target = target[:-3]
            total_links += 1
            if target.lower() not in resolvable:
                key = target
                broken[key]["count"] += 1
                if rel not in broken[key]["sources"]:
                    broken[key]["sources"].append(rel)

    # Sort by frequency
    rows = sorted(broken.items(), key=lambda kv: -kv[1]["count"])

    output = Path(__file__).resolve().parent / "broken_links.csv"
    with output.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["target", "broken_count", "example_sources"])
        for target, info in rows:
            writer.writerow([target, info["count"], " | ".join(info["sources"][:5])])

    print("Total wikilinks scanned: {}".format(total_links))
    print("Distinct broken targets: {}".format(len(broken)))
    print()
    print("Top 30 broken targets by frequency:")
    for target, info in rows[:30]:
        srcs = ", ".join(info["sources"][:3])
        print("  {:5d}  {:35s} from: {}".format(info["count"], target[:35], srcs[:80]))
    print()
    print("Full list: {}".format(output))


if __name__ == "__main__":
    main()
