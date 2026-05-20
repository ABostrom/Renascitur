"""Repair frontmatter values that got mangled into nested-list format.

PyYAML reads unquoted `[[Foo]]` as a nested flow sequence `[['Foo']]`.
Any script that read + re-wrote frontmatter AFTER my Layer 32 unquote
(notably Layer 35 add-aliases) re-dumped these as broken block format:

    realm:
    - - Renascita

This script:
  1. Finds frontmatter lines matching the broken pattern.
  2. Rewrites them to the unquoted-wikilink form.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from refactor.common import DOCS_DIR, REPO_ROOT


FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

# Match a block-style nested list with exactly one inner string element:
#     field:
#     - - Foo
# Capture: field name, indented inner value.
NESTED_BLOCK_RE = re.compile(
    r"""^([ \t]*[A-Za-z_][\w-]*):\s*\n([ \t]*-\s*-\s*)(.+?)\s*$""",
    re.MULTILINE,
)


def _is_wikilink_safe_name(s: str) -> bool:
    """Return True if s looks like a wikilink target (alphanumeric + spaces + a few punctuation)."""
    if not s:
        return False
    # Strip any leading/trailing whitespace
    s = s.strip()
    # Don't try to wikilink things that look like multi-element flow lists
    if "," in s or "[" in s or "]" in s:
        return False
    return True


def repair_frontmatter(fm: str) -> tuple:
    """Return (new_fm, count_repaired)."""
    count = 0

    def _sub(m):
        nonlocal count
        field = m.group(1)
        # The value after "- - "
        inner = m.group(3).strip()
        if not _is_wikilink_safe_name(inner):
            return m.group(0)
        count += 1
        return "{}: [[{}]]".format(field, inner)

    new_fm = NESTED_BLOCK_RE.sub(_sub, fm)
    return new_fm, count


def main() -> None:
    files_changed = 0
    total_repaired = 0

    for md in DOCS_DIR.rglob("*.md"):
        text = md.read_text(encoding="utf-8")
        m = FRONTMATTER_RE.match(text)
        if not m:
            continue
        fm = m.group(1)
        body = text[m.end():]
        new_fm, n = repair_frontmatter(fm)
        if n == 0:
            continue
        new_text = "---\n{}\n---\n{}".format(new_fm, body)
        with md.open("w", encoding="utf-8", newline="\n") as fh:
            fh.write(new_text)
        files_changed += 1
        total_repaired += n
        print("Repaired {} value(s) in {}".format(n, md.relative_to(REPO_ROOT)))

    print("---")
    print("Files changed: {}".format(files_changed))
    print("Nested-list values repaired: {}".format(total_repaired))


if __name__ == "__main__":
    main()
