"""Unquote wikilinks in frontmatter.

Root cause of Aaron's 'data views show nothing': PyYAML's safe_dump
quotes any string containing brackets, so values became
  era: '[[Age of Forging]]'
With quotes, some Obsidian/Dataview versions treat them as plain
strings rather than Link objects, so the values never enter
file.outlinks and link-based queries return empty.

Obsidian's YAML parser is permissive and supports unquoted wikilinks:
  era: [[Age of Forging]]
This form is reliably detected as a Link.

This script walks every .md under docs/ + templates/, and for each
frontmatter line of the shape
  <key>: '[[X]]'        ->  <key>: [[X]]
  - '[[X]]'             ->  - [[X]]
strips the quotes. Idempotent.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from refactor.common import DOCS_DIR, REPO_ROOT, iter_md_files


FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

# Match a wikilink value on its own line within frontmatter:
#   key: '[[Foo]]'           ->  key: [[Foo]]
#   key: '[[Foo|Bar]]'       ->  key: [[Foo|Bar]]
#   - '[[Foo]]'              ->  - [[Foo]]
# We're conservative: only unquote VALUES that are pure wikilinks
# (no quotes inside, no extra text). And only single-quoted (PyYAML default).
SINGLE_LINE_RE = re.compile(
    r"""^([ \t]*[A-Za-z_][\w-]*:[ \t]*)'(\[\[[^'\[\]]+\]\])'(\s*)$""",
    re.MULTILINE,
)
LIST_ITEM_RE = re.compile(
    r"""^([ \t]*-[ \t]+)'(\[\[[^'\[\]]+\]\])'(\s*)$""",
    re.MULTILINE,
)


def unquote_frontmatter(text: str) -> tuple:
    """Return (new_text, changed_count)."""
    m = FRONTMATTER_RE.match(text)
    if not m:
        return text, 0

    frontmatter = m.group(1)
    body = text[m.end():]

    changed = 0

    def _sub_single(match):
        nonlocal changed
        changed += 1
        return match.group(1) + match.group(2) + match.group(3)

    def _sub_list(match):
        nonlocal changed
        changed += 1
        return match.group(1) + match.group(2) + match.group(3)

    new_fm = SINGLE_LINE_RE.sub(_sub_single, frontmatter)
    new_fm = LIST_ITEM_RE.sub(_sub_list, new_fm)

    if changed == 0:
        return text, 0

    return "---\n{}\n---\n{}".format(new_fm, body), changed


def main() -> None:
    files_changed = 0
    total_unquoted = 0

    targets = list(iter_md_files())
    # also include templates
    templates_dir = REPO_ROOT / "templates"
    if templates_dir.exists():
        targets.extend(sorted(templates_dir.glob("*.md")))

    for path in targets:
        text = path.read_text(encoding="utf-8")
        new_text, changed = unquote_frontmatter(text)
        if changed == 0:
            continue
        with path.open("w", encoding="utf-8", newline="\n") as fh:
            fh.write(new_text)
        files_changed += 1
        total_unquoted += changed

    print("Files changed: {}".format(files_changed))
    print("Wikilink values unquoted: {}".format(total_unquoted))


if __name__ == "__main__":
    main()
