#!/usr/bin/env python3
"""52_quote_frontmatter_wikilinks.py — Ensure every [[wikilink]] in frontmatter is double-quoted.

In YAML, bare [[Foo]] is parsed as a nested flow sequence, not a string.
All wikilinks must be wrapped in double-quotes.

Transforms:
  key: [[Foo]]          →  key: "[[Foo]]"
  - [[Foo]]             →  - "[[Foo]]"
  key: '[[Foo]]'        →  key: "[[Foo]]"
  - '[[Foo]]'           →  - "[[Foo]]"
  key: "[[Foo]]"        →  (unchanged — already correct)

Run with --apply to write changes; default is --dry-run.
"""
from __future__ import annotations
import argparse, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import DOCS_DIR, iter_md_files

FRONTMATTER_RE = re.compile(r'\A(---[ \t]*\n)(.*?)(---[ \t]*\n)', re.DOTALL)

# Matches unquoted [[...]] or single-quoted '[[...]]'
# Does NOT match already-double-quoted "[[...]]"
WIKILINK_FIX_RE = re.compile(
    r"""'(\[\[[^\]]+\]\])'"""                       # group 1: single-quoted
    r"""|"""
    r"""(?<!["'])(\[\[[^\]]+\]\])(?!["'])"""        # group 2: unquoted
)


def fix_match(m: re.Match) -> str:
    inner = m.group(1) or m.group(2)
    return f'"{inner}"'


def fix_file(path: Path, apply: bool) -> int:
    """Returns number of wikilinks fixed in this file."""
    text = path.read_text(encoding='utf-8')

    fm = FRONTMATTER_RE.match(text)
    if not fm:
        return 0

    open_delim  = fm.group(1)
    frontmatter = fm.group(2)
    close_delim = fm.group(3)
    body        = text[fm.end():]

    fixed_fm, count = WIKILINK_FIX_RE.subn(fix_match, frontmatter)
    if count == 0:
        return 0

    if apply:
        path.write_text(open_delim + fixed_fm + close_delim + body, encoding='utf-8')

    return count


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()

    total_files = total_links = 0

    for md in sorted(iter_md_files()):
        count = fix_file(md, apply=args.apply)
        if count:
            total_files += 1
            total_links += count
            label = 'APPLY' if args.apply else 'DRY'
            rel = md.relative_to(DOCS_DIR)
            print(f'[{label}] {rel}  ({count})')

    mode = 'Applied' if args.apply else 'Dry-run'
    print(f'\n{mode}: {total_links} wikilink(s) quoted across {total_files} file(s).')


if __name__ == '__main__':
    main()
