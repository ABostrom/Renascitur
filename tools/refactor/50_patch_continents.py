#!/usr/bin/env python3
"""50_patch_continents.py — Complete continent geographic frontmatter.

Fills terrain, inhabited_by, provinces, cities, mountains, rivers on the 4
continent files that are missing them (Draumhavn, Aquaria, Renascita, The World Beneath).
Also fixes the malformed '- - -' YAML list items in Mokoweri.

Run with --apply to write changes; default is --dry-run.
"""
from __future__ import annotations
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import DOCS_DIR, read_frontmatter, write_frontmatter

CONTINENTS_DIR = DOCS_DIR / "continents"

# ── Geographic patches ─────────────────────────────────────────────────────
PATCHES: dict[str, dict] = {
    "Draumhavn": {
        "terrain": ["volcanic isles", "sea cliffs", "underground tunnels", "ocean"],
        "inhabited_by": [
            "[[The Tidebound of Draumhavn|Tidebound Dwarves]]",
            "[[The Stormbound of Thundrakar|Stormbound Dwarves]]",
        ],
        "cities": ["[[Thundrakar]]"],
        "provinces": ["[[Salt Cradle]]", "[[Stormgates]]", "[[The Wakened Trench]]"],
        "mountains": [],   # volcanic but no named range
        "rivers": [],      # island — no rivers
    },
    "Aquaria": {
        "terrain": ["ocean depths", "coral reefs", "underwater caverns", "abyssal trenches"],
        "inhabited_by": [],   # no known inhabitants yet — stub
        "provinces": ["[[Coral Reef Bay]]", "[[Crystal Caverns]]", "[[Leviathan's Trench]]"],
        "cities": [],
        "mountains": [],
        "rivers": [],
    },
    "Renascita": {
        # World-plane container — geographic fields not applicable
        "kind": "world",
    },
    "The World Beneath": {
        "terrain": ["underground caverns", "abyssal tunnels", "fungal forests", "obsidian plains"],
        "inhabited_by": ["[[Weavers of Agony]]"],
        "provinces": ["[[The Hollowed Warrens]]"],
        "cities": [],
        "mountains": [],
        "rivers": [],
    },
}

# Fields that are skipped when the existing value is non-empty and non-empty-list
FILL_ONLY_EMPTY = {"terrain", "inhabited_by", "provinces", "cities", "mountains", "rivers", "kind"}


def _is_empty(v) -> bool:
    if v is None:
        return True
    if isinstance(v, str) and v.strip() == "":
        return True
    if isinstance(v, list) and len(v) == 0:
        return True
    return False


def patch_continent(path: Path, patches: dict, apply: bool) -> list[str]:
    meta, body = read_frontmatter(path)
    changes: list[str] = []

    for key, new_val in patches.items():
        existing = meta.get(key)
        if _is_empty(existing) and not _is_empty(new_val):
            changes.append(f"  + {key}: {new_val!r}")
            meta[key] = new_val

    if changes and apply:
        write_frontmatter(path, meta, body)

    return changes


def fix_mokoweri_yaml(apply: bool) -> list[str]:
    """Fix malformed '- - - Foo' entries in Mokoweri.md frontmatter."""
    path = CONTINENTS_DIR / "Mokoweri.md"
    content = path.read_text(encoding="utf-8")

    # Pattern: a malformed nested list item "- - - Some Text" (spaces between dashes).
    # This is distinct from the "---" frontmatter delimiter (no spaces).
    # Replace with "- Some Text".
    fixed, n = re.subn(r'^( *)- +- +- +', r'\1- ', content, flags=re.MULTILINE)
    if n == 0:
        return []

    changes = [f"  fix: {n} malformed '- - -' list item(s) → plain strings"]
    if apply:
        path.write_text(fixed, encoding="utf-8")
    return changes


def main() -> None:
    parser = argparse.ArgumentParser(description="Patch continent frontmatter.")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    total = 0

    # Fix Mokoweri YAML corruption first
    changes = fix_mokoweri_yaml(apply=args.apply)
    if changes:
        label = "APPLY" if args.apply else "DRY"
        print(f"[{label}] Mokoweri (YAML fix)")
        for c in changes:
            print(c)
        total += len(changes)
    else:
        print("[SKIP]  Mokoweri — no malformed entries found")

    # Patch the 4 stub continents
    for stem, patches in PATCHES.items():
        path = CONTINENTS_DIR / f"{stem}.md"
        if not path.exists():
            print(f"[MISSING] {stem}.md — skipping")
            continue

        changes = patch_continent(path, patches, apply=args.apply)
        if changes:
            total += len(changes)
            label = "APPLY" if args.apply else "DRY"
            print(f"[{label}] {stem}")
            for c in changes:
                print(c)
        else:
            print(f"[SKIP]  {stem} — nothing to add")

    mode = "Applied" if args.apply else "Dry-run"
    print(f"\n{mode}: {total} change(s).")


if __name__ == "__main__":
    main()
