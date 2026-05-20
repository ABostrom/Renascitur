"""Verify each faction page would actually display content.

Simulates the dynamic Contents queries by text-grepping the corpus
for the frontmatter linkages that drive them. Reports for each
faction:
  - Members (characters with affiliation: [[Faction]])
  - Sub-factions (factions with parent_faction: [[Faction]])
  - Organisations (organisations with parent_faction: [[Faction]])
  - Events (events with participants containing [[Faction]])
  - Backlinks (any file with [[Faction]] anywhere)

Outputs a per-faction summary so we can spot which ones are still
sparse and need prose-body connections added.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from refactor.common import DOCS_DIR, iter_md_files, rel_to_docs


# Each pattern matches the frontmatter linkage for that relation,
# handling BOTH the unquoted form ([[X]]) and the single-quoted form
# ('[[X]]') in case any escaped to leak through.
def _frontmatter_link_pattern(field: str, target: str) -> re.Pattern:
    # Matches: `field: [[target]]` or `field: '[[target]]'`
    esc_target = re.escape(target)
    # Allow optional quotes and trailing alias/whitespace; require start-of-line
    return re.compile(
        r"^\s*" + re.escape(field) + r"\s*:\s*'?\[\[" + esc_target + r"(\|[^\]]+)?\]\]'?\s*$",
        re.MULTILINE,
    )


def _list_item_link_pattern(target: str) -> re.Pattern:
    """Match a list item containing [[target]] (for fields like
    participants: [...] or magic: [...])."""
    esc_target = re.escape(target)
    return re.compile(
        r"^\s*-\s*'?\[\[" + esc_target + r"(\|[^\]]+)?\]\]'?\s*$",
        re.MULTILINE,
    )


def find_members(target_name: str) -> List[str]:
    """Characters whose affiliation is [[target_name]]."""
    pat = _frontmatter_link_pattern("affiliation", target_name)
    out = []
    for md in iter_md_files():
        text = md.read_text(encoding="utf-8")
        # Restrict to frontmatter
        m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
        if not m:
            continue
        fm = m.group(1)
        if re.search(r"^\s*type\s*:\s*character\s*$", fm, re.MULTILINE) and pat.search(fm):
            out.append(md.stem)
    return out


def find_sub_factions(target_name: str) -> List[str]:
    pat = _frontmatter_link_pattern("parent_faction", target_name)
    out = []
    for md in iter_md_files():
        text = md.read_text(encoding="utf-8")
        m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
        if not m:
            continue
        fm = m.group(1)
        if re.search(r"^\s*type\s*:\s*faction\s*$", fm, re.MULTILINE) and pat.search(fm):
            out.append(md.stem)
    return out


def find_organisations(target_name: str) -> List[str]:
    pat = _frontmatter_link_pattern("parent_faction", target_name)
    out = []
    for md in iter_md_files():
        text = md.read_text(encoding="utf-8")
        m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
        if not m:
            continue
        fm = m.group(1)
        if re.search(r"^\s*type\s*:\s*organisation\s*$", fm, re.MULTILINE) and pat.search(fm):
            out.append(md.stem)
    return out


def find_backlinks(target_name: str) -> int:
    """Count files that reference [[target_name]] anywhere."""
    pat = re.compile(r"\[\[" + re.escape(target_name) + r"(\|[^\]]+)?\]\]")
    count = 0
    for md in iter_md_files():
        text = md.read_text(encoding="utf-8")
        if pat.search(text):
            count += 1
    return count


def main() -> None:
    # Discover all faction self-summaries
    factions_dir = DOCS_DIR / "factions"
    if not factions_dir.exists():
        print("No factions/ folder.")
        return

    faction_files = sorted(factions_dir.glob("*.md"))
    rows = []
    for fp in faction_files:
        name = fp.stem
        members = find_members(name)
        subs = find_sub_factions(name)
        orgs = find_organisations(name)
        backlinks = find_backlinks(name)
        rows.append({
            "name": name,
            "members": len(members),
            "subs": len(subs),
            "orgs": len(orgs),
            "backlinks": backlinks,
            "member_names": members,
            "sub_names": subs,
            "org_names": orgs,
        })

    # Print sorted by total connectivity
    rows.sort(key=lambda r: -(r["members"] + r["subs"] * 5 + r["orgs"] * 2))

    print("Faction connectivity report:")
    print()
    print("  {:42s}  members  subs  orgs  backlinks".format("Faction"))
    print("  " + "-" * 78)
    for r in rows:
        print("  {:42s}  {:4d}     {:4d}  {:4d}  {:4d}".format(
            r["name"][:42],
            r["members"], r["subs"], r["orgs"], r["backlinks"],
        ))

    # Detail for sparse ones (no members AND no subs AND no orgs)
    print()
    print("=== Sparse factions (no direct linkages) ===")
    sparse = [r for r in rows if r["members"] == 0 and r["subs"] == 0 and r["orgs"] == 0]
    for r in sparse:
        print("  {} (backlinks={})".format(r["name"], r["backlinks"]))


if __name__ == "__main__":
    main()
