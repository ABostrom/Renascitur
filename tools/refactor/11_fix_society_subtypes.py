"""Fix mis-typed files in society subfolders.

The original type-inference rules in `rules.py` only knew about a few
canonical sub-folder names (Characters, Clans, Orders, Traditions,
Locations). Aaron's vault uses several non-canonical containers:
  - Elders, Emperors, Tyrannosaurs of Mokoweri  -> characters
  - Great Houses                                -> houses
  - Guilds                                      -> organisations
  - Ships                                       -> artifacts (named vessels)
  - Technology                                  -> technologies
  - Sub-society folders (The Tidebound of …)    -> sub-faction self-summaries

Files under these folders were caught by the catch-all `essay` rule.
This script reclassifies them and adds the right relational fields.

Conservatively overwrites `type:` ONLY when the current value is `essay`.
Adds affiliation/parent_faction etc. via merge (never overwrites existing).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Callable, Dict, List, Tuple

# Allow running as a script from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from refactor.common import iter_md_files, read_frontmatter, write_frontmatter, rel_to_docs


# Each rule: (compiled regex, target type, extras callable from match -> fields)
RULES: List[Tuple[re.Pattern, str, Callable]] = [
    # Character containers
    (re.compile(r"^Realms/Renascita/Societies/(?P<top>[^/]+)/Elders/[^/]+\.md$"),
     "character",
     lambda m: {"affiliation": "[[{}]]".format(m.group("top"))}),

    (re.compile(r"^Realms/Renascita/Societies/(?P<top>[^/]+)/Emperors/[^/]+\.md$"),
     "character",
     lambda m: {"affiliation": "[[{}]]".format(m.group("top"))}),

    (re.compile(r"^Realms/Renascita/Societies/(?P<top>[^/]+)/Tyrannosaurs of Mokoweri/[^/]+\.md$"),
     "character",
     lambda m: {"affiliation": "[[{}]]".format(m.group("top"))}),

    # Houses
    (re.compile(r"^Realms/Renascita/Societies/(?P<top>[^/]+)/Great Houses/[^/]+\.md$"),
     "house",
     lambda m: {"parent_faction": "[[{}]]".format(m.group("top"))}),

    # Organisations
    (re.compile(r"^Realms/Renascita/Societies/(?P<top>[^/]+)/Guilds/[^/]+\.md$"),
     "organisation",
     lambda m: {"parent_faction": "[[{}]]".format(m.group("top"))}),

    # Artifacts (named ships)
    (re.compile(r"^Realms/Renascita/Societies/(?P<top>[^/]+)/(?:.*/)?Ships/[^/]+\.md$"),
     "artifact",
     lambda m: {}),

    # Technology under a society
    (re.compile(r"^Realms/Renascita/Societies/(?P<top>[^/]+)/Technology/[^/]+\.md$"),
     "technology",
     lambda m: {"realm": "[[Renascita]]"}),

    # Sub-society self-named: e.g. Societies/Dwarven Holds/The Tidebound of Draumhavn/Tidebound of Draumhavn.md
    # (Folder has "The" prefix; file does not.)
    (re.compile(r"^Realms/Renascita/Societies/(?P<top>[^/]+)/The (?P<sub>[^/]+)/(?P=sub)\.md$"),
     "faction",
     lambda m: {"parent_faction": "[[{}]]".format(m.group("top"))}),

    # Also the more-standard self-named pattern without "The " prefix
    (re.compile(r"^Realms/Renascita/Societies/(?P<top>[^/]+)/(?P<sub>[^/]+)/(?P=sub)\.md$"),
     "faction",
     lambda m: {"parent_faction": "[[{}]]".format(m.group("top"))}),

    # "Container summary" pages at top of a category folder (e.g., Emperors.md)
    # — these summarize the category, treat as essay (no change to type if essay,
    # but no relational fields either). Skipped here intentionally.
]


def main() -> None:
    changed = 0
    type_fixed = 0
    relational_added = 0
    by_target_type: Dict[str, int] = {}

    for md in iter_md_files():
        rel = rel_to_docs(md)
        matched_rule = None
        for pattern, target_type, extras in RULES:
            m = pattern.match(rel)
            if m:
                matched_rule = (m, target_type, extras)
                break
        if matched_rule is None:
            continue

        m, target_type, extras = matched_rule
        meta, body = read_frontmatter(md)
        new_fields = extras(m)

        needs_write = False

        # Only overwrite type when current is essay (defensive).
        if meta.get("type") == "essay" and target_type != "essay":
            meta["type"] = target_type
            needs_write = True
            type_fixed += 1
            by_target_type[target_type] = by_target_type.get(target_type, 0) + 1

        # Merge in extras; don't overwrite if already set.
        for k, v in new_fields.items():
            if k not in meta:
                meta[k] = v
                needs_write = True
                relational_added += 1

        if needs_write:
            write_frontmatter(md, meta, body)
            changed += 1
            print("Fixed: {} -> {}".format(rel, target_type))

    print("---")
    print("Files changed: {}".format(changed))
    print("Type fixed: {}".format(type_fixed))
    print("Relational fields added: {}".format(relational_added))
    print("By new type:")
    for t, n in sorted(by_target_type.items(), key=lambda kv: -kv[1]):
        print("  {:15s} {:5d}".format(t, n))


if __name__ == "__main__":
    main()
