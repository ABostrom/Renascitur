"""Repair the mess Layer 40 left behind on triple-nested wikilink lists.

For a frontmatter field that started as a list of wikilinks:
    allies: ['[[Firebrand Empire]]', '[[Dwarven Holds]]']
PyYAML wrote (after Layer 32's unquote) as triple-nested block:
    allies:
    - - - Firebrand Empire
    - - - Dwarven Holds
Layer 40's regex only captured two dashes and produced garbage:
    allies: [[- Firebrand Empire]]
    - - Dwarven Holds

This script:
  1. Finds frontmatter values of the form `field: [[- VALUE]]`
     (invalid flow sequence) and re-emits as a proper list.
  2. Cleans up orphan `- - - X` block sequence remnants.
  3. Re-writes the file with proper list-of-wikilinks frontmatter.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from refactor.common import DOCS_DIR


FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

# Match: `field: [[- VALUE]]` (the broken inline form)
BROKEN_INLINE_RE = re.compile(
    r"^([ \t]*[A-Za-z_][\w-]*):\s*\[\[-\s*(.+?)\]\]\s*$",
    re.MULTILINE,
)

# Match: orphan line `- - - VALUE` (the broken block-list remnant)
ORPHAN_BLOCK_RE = re.compile(
    r"^([ \t]*)-\s*-\s*-\s*(.+?)\s*$",
    re.MULTILINE,
)

# Pure triple-nested list:
#   field:
#   - - - X
#   - - - Y
# Capture the field + all its triple-nested items
TRIPLE_LIST_RE = re.compile(
    r"^([ \t]*[A-Za-z_][\w-]*):\s*\n((?:[ \t]*-\s*-\s*-\s*.+?\s*\n)+)",
    re.MULTILINE,
)


def repair_frontmatter(fm: str) -> tuple:
    """Return (new_fm, repair_count)."""
    count = 0

    # First handle pure triple-nested lists (when the broken inline didn't happen)
    def _sub_triple(m):
        nonlocal count
        field = m.group(1)
        items_text = m.group(2)
        items = []
        for line in items_text.splitlines():
            mi = re.match(r"[ \t]*-\s*-\s*-\s*(.+?)\s*$", line)
            if mi:
                value = mi.group(1).strip()
                items.append(value)
        if not items:
            return m.group(0)
        count += 1
        lines = ["{}:".format(field)]
        for v in items:
            lines.append("- [[{}]]".format(v))
        return "\n".join(lines) + "\n"

    new_fm = TRIPLE_LIST_RE.sub(_sub_triple, fm)

    # Now reconstruct broken-inline + orphan-block combinations:
    #   field: [[- X]]
    #   - - - Y
    # -> field:
    #    - [[X]]
    #    - [[Y]]
    lines = new_fm.split("\n")
    out_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        m = BROKEN_INLINE_RE.match(line + "\n")
        if m:
            field = m.group(1)
            first_value = m.group(2).strip()
            items = [first_value]
            # Collect following orphan-block lines
            j = i + 1
            while j < len(lines):
                m2 = ORPHAN_BLOCK_RE.match(lines[j] + "\n")
                if m2:
                    items.append(m2.group(2).strip())
                    j += 1
                else:
                    break
            count += 1
            out_lines.append("{}:".format(field))
            for v in items:
                out_lines.append("- [[{}]]".format(v))
            i = j
        else:
            out_lines.append(line)
            i += 1
    new_fm = "\n".join(out_lines)
    return new_fm, count


def main() -> None:
    files_changed = 0
    total = 0
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
        total += n
        print("Repaired {} value(s) in {}".format(n, md.relative_to(DOCS_DIR.parent)))
    print("---")
    print("Files changed: {}".format(files_changed))
    print("Repairs: {}".format(total))


if __name__ == "__main__":
    main()
