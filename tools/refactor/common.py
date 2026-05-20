"""Shared helpers for the typed-vault refactor scripts.

This module provides:
- REPO_ROOT, DOCS_DIR: project paths anchored to this file's location
- read_frontmatter(path): returns (metadata_dict, body_str)
- write_frontmatter(path, metadata, body): writes file atomically
- iter_md_files(): yields every .md path under DOCS_DIR
- ensure_list(value): coerces scalar-or-list to list
- merge_metadata(existing, new): merges dicts, preserving existing keys
- git_mv(src, dst): runs `git mv` and raises on failure
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, Iterator, List, Tuple

import yaml

# Anchor: tools/refactor/common.py -> repo root is two levels up.
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DOCS_DIR = REPO_ROOT / "docs"

FRONTMATTER_RE = re.compile(
    r"^---\s*\n(.*?)\n---\s*\n",
    re.DOTALL,
)


def _wikilink_from_nested(value):
    """PyYAML parses `field: [[Foo]]` as a nested flow sequence
    [['Foo']]. Detect that pattern and recover the string form '[[Foo]]'.
    Applied recursively for lists.
    """
    # Single-element list of single-element list of string: [['Foo']] -> '[[Foo]]'
    if (
        isinstance(value, list)
        and len(value) == 1
        and isinstance(value[0], list)
        and len(value[0]) == 1
        and isinstance(value[0][0], str)
    ):
        return "[[{}]]".format(value[0][0])
    # List of such structures (rare but possible)
    if isinstance(value, list):
        out = []
        any_converted = False
        for item in value:
            new_item = _wikilink_from_nested(item)
            if new_item is not item:
                any_converted = True
            out.append(new_item)
        if any_converted:
            return out
    return value


def _normalize_frontmatter(meta: Dict) -> Dict:
    """Recursively convert PyYAML-mangled nested-list wikilinks back to strings."""
    if not isinstance(meta, dict):
        return meta
    return {k: _wikilink_from_nested(v) for k, v in meta.items()}


def read_frontmatter(path: Path) -> Tuple[Dict, str]:
    """Return (metadata_dict, body_string) for a markdown file.

    Files without frontmatter return ({}, full_content).
    Recovers Obsidian-style unquoted wikilinks (`field: [[Foo]]`) that
    PyYAML otherwise misparses as nested flow sequences.
    """
    text = path.read_text(encoding="utf-8")
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    raw = m.group(1)
    body = text[m.end():]
    try:
        metadata = yaml.safe_load(raw) or {}
    except yaml.YAMLError as e:
        print("WARN: YAML error in {}: {}".format(path, e), file=sys.stderr)
        return {}, text
    if not isinstance(metadata, dict):
        # e.g. file starts with --- but content is a list at top level; bail out safely
        return {}, text
    metadata = _normalize_frontmatter(metadata)
    return metadata, body


_WIKILINK_QUOTED_LINE_RE = re.compile(
    r"""^([ \t]*[A-Za-z_][\w-]*:[ \t]*)'(\[\[(?:[^'\[\]]|'')*\]\])'(\s*)$""",
    re.MULTILINE,
)
_WIKILINK_QUOTED_LIST_RE = re.compile(
    r"""^([ \t]*-[ \t]+)'(\[\[(?:[^'\[\]]|'')*\]\])'(\s*)$""",
    re.MULTILINE,
)


def _unescape_yaml_apos(inner: str) -> str:
    return inner.replace("''", "'")


def _unquote_wikilinks(yaml_text: str) -> str:
    """Post-process PyYAML output to unquote wikilink-only values.

    Obsidian/Dataview requires unquoted wikilinks in frontmatter to be
    auto-detected as Link objects (and thus appear in file.outlinks).
    PyYAML defaults to single-quoting any string with brackets.
    """
    def _sub_single(m):
        return m.group(1) + _unescape_yaml_apos(m.group(2)) + m.group(3)

    def _sub_list(m):
        return m.group(1) + _unescape_yaml_apos(m.group(2)) + m.group(3)

    out = _WIKILINK_QUOTED_LINE_RE.sub(_sub_single, yaml_text)
    out = _WIKILINK_QUOTED_LIST_RE.sub(_sub_list, out)
    return out


def write_frontmatter(path: Path, metadata: Dict, body: str) -> None:
    """Write a markdown file with the given frontmatter and body.

    Empty metadata writes the body alone (no frontmatter block).
    Wikilink-only string values are post-processed to be unquoted so
    Obsidian/Dataview parses them as Link objects.
    """
    if metadata:
        # Preserve wikilink quoting; default_flow_style=False for block style.
        front = yaml.safe_dump(
            metadata,
            sort_keys=False,
            default_flow_style=False,
            allow_unicode=True,
            width=10**9,  # don't line-wrap long strings
        )
        # Unquote pure-wikilink values so Obsidian recognises them as Links.
        front = _unquote_wikilinks(front)
        # Ensure exactly one blank line between body and frontmatter.
        if not body.startswith("\n"):
            body = "\n" + body
        text = "---\n{}---{}".format(front, body)
    else:
        text = body
    # Path.write_text gained newline= in 3.10; for 3.7+ compatibility use open().
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def iter_md_files(root: Path = DOCS_DIR) -> Iterator[Path]:
    """Yield every .md file under root, sorted for deterministic output."""
    for p in sorted(root.rglob("*.md")):
        yield p


def ensure_list(value) -> List:
    """Coerce a scalar, None, or list into a list."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def merge_metadata(existing: Dict, new: Dict) -> Dict:
    """Merge new into existing without overwriting existing keys.

    Lists are extended (deduplicated, order-preserving).
    Returns a new dict.
    """
    out = dict(existing)
    for key, val in new.items():
        if key not in out:
            out[key] = val
        elif isinstance(out[key], list) and isinstance(val, list):
            seen = set()
            merged = []
            for item in out[key] + val:
                key_for_set = repr(item)
                if key_for_set not in seen:
                    seen.add(key_for_set)
                    merged.append(item)
            out[key] = merged
    return out


def git_mv(src: Path, dst: Path) -> None:
    """Run `git mv` from the repo root. Raises CalledProcessError on failure."""
    rel_src = src.relative_to(REPO_ROOT)
    rel_dst = dst.relative_to(REPO_ROOT)
    subprocess.run(
        ["git", "mv", str(rel_src), str(rel_dst)],
        cwd=REPO_ROOT,
        check=True,
    )


def rel_to_docs(path: Path) -> str:
    """Path relative to DOCS_DIR, as a forward-slash POSIX string."""
    return path.relative_to(DOCS_DIR).as_posix()
