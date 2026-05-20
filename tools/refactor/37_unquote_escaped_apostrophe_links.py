"""Unquote remaining frontmatter wikilinks that contain escaped apostrophes.

PyYAML escapes a straight apostrophe inside a single-quoted string by
doubling it: 'Magnus' Rest' becomes 'Magnus'' Rest'. Layer 32's
unquoter rejected these. Result: characters like Brenna whose
affiliation is The Flamebound of Magnus' Rest still have their value
quoted, breaking Dataview link queries.

This script handles the escaped-apostrophe case:
    key: '[[Magnus'' Rest]]'   ->  key: [[Magnus' Rest]]
    - '[[Magnus'' Rest]]'       ->  - [[Magnus' Rest]]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from refactor.common import DOCS_DIR, REPO_ROOT


FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

# Match `key: '[[...some content with possibly '' inside...]]'`
# Capture the inner wikilink. Group 2 includes the [[...]] with escaped apostrophes intact.
SINGLE_LINE_RE = re.compile(
    r"""^([ \t]*[A-Za-z_][\w-]*:[ \t]*)'(\[\[(?:[^'\[\]]|'')*\]\])'(\s*)$""",
    re.MULTILINE,
)
LIST_ITEM_RE = re.compile(
    r"""^([ \t]*-[ \t]+)'(\[\[(?:[^'\[\]]|'')*\]\])'(\s*)$""",
    re.MULTILINE,
)


def _unescape_apos(s: str) -> str:
    """'' -> ' (YAML single-quote unescape)."""
    return s.replace("''", "'")


def unquote_frontmatter(text: str) -> tuple:
    m = FRONTMATTER_RE.match(text)
    if not m:
        return text, 0

    fm = m.group(1)
    body = text[m.end():]
    changed = 0

    def _sub_single(match):
        nonlocal changed
        changed += 1
        return match.group(1) + _unescape_apos(match.group(2)) + match.group(3)

    def _sub_list(match):
        nonlocal changed
        changed += 1
        return match.group(1) + _unescape_apos(match.group(2)) + match.group(3)

    new_fm = SINGLE_LINE_RE.sub(_sub_single, fm)
    new_fm = LIST_ITEM_RE.sub(_sub_list, new_fm)

    if changed == 0:
        return text, 0
    return "---\n{}\n---\n{}".format(new_fm, body), changed


def main() -> None:
    files_changed = 0
    total = 0
    targets = list(DOCS_DIR.rglob("*.md"))
    templates_dir = REPO_ROOT / "templates"
    if templates_dir.exists():
        targets.extend(sorted(templates_dir.glob("*.md")))
    for path in targets:
        text = path.read_text(encoding="utf-8")
        new_text, n = unquote_frontmatter(text)
        if n == 0:
            continue
        with path.open("w", encoding="utf-8", newline="\n") as fh:
            fh.write(new_text)
        files_changed += 1
        total += n
    print("Files changed: {}".format(files_changed))
    print("Wikilink values unquoted: {}".format(total))


if __name__ == "__main__":
    main()
