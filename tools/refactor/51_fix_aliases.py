#!/usr/bin/env python3
"""51_fix_aliases.py — Add missing aliases to resolve near-miss broken wikilinks.

These are pages that exist under a longer/different name but are referenced
by a shorter form without an alias entry.

Run with --apply to write changes; default is --dry-run.
"""
from __future__ import annotations
import argparse, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import DOCS_DIR, read_frontmatter, write_frontmatter

# file path (relative to DOCS_DIR) -> list of aliases to add
ALIAS_PATCHES: dict[str, list[str]] = {
    "technologies/Nature/Primal Magic.md":  ["Primal"],
    "technologies/Soul/Divine Magic.md":    ["Divine"],
    "technologies/Arcane/Rune Magic.md":    ["Forge Magic"],   # dwarven forge-craft is a rune sub-discipline
    "landmarks/Eternal Flame.md":           ["the Eternal Flame"],
    "landmarks/The Wakened Trench.md":      ["Wakened Trench"],
    "characters/Zariel Mephista.md":        ["Zariel"],
}


def patch_aliases(path: Path, new_aliases: list[str], apply: bool) -> list[str]:
    meta, body = read_frontmatter(path)
    existing = meta.get("aliases") or []
    if not isinstance(existing, list):
        existing = [existing] if existing else []

    to_add = [a for a in new_aliases if a not in existing]
    if not to_add:
        return []

    meta["aliases"] = existing + to_add
    changes = [f"  + aliases: {to_add}"]
    if apply:
        write_frontmatter(path, meta, body)
    return changes


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    total = 0
    for rel, aliases in ALIAS_PATCHES.items():
        path = DOCS_DIR / rel
        if not path.exists():
            print(f"[MISSING] {rel}")
            continue
        changes = patch_aliases(path, aliases, apply=args.apply)
        label = "APPLY" if args.apply else "DRY"
        if changes:
            total += 1
            print(f"[{label}] {path.name}")
            for c in changes:
                print(c)
        else:
            print(f"[SKIP]  {path.name} — aliases already present")

    mode = "Applied" if args.apply else "Dry-run"
    print(f"\n{mode}: {total} file(s) updated.")


if __name__ == "__main__":
    main()
