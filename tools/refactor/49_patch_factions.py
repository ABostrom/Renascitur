#!/usr/bin/env python3
"""49_patch_factions.py — Fill faction leadership, allies, rivals, era_founded, seat.

Run with --apply to write changes; default is --dry-run.
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import DOCS_DIR, read_frontmatter, write_frontmatter

# ── Patch data ─────────────────────────────────────────────────────────────
# Keys present in PATCHES will be set only if the existing value is empty/missing.
# Exception: leadership/allies/rivals are always overwritten if we have data,
# because they were all initialised to [].

PATCHES: dict[str, dict] = {
    "Dwarven Holds": {
        # No singular leader — federation of 4 holds; era is ancient
        "era_founded": "[[Age of Forging]]",
        # allies already has [[Firebrand Empire]] — leave untouched
    },
    "Firebrand Empire": {
        "leadership": ["[[Unimus - First Emperor]]"],  # founder / patron deity; current emperors tracked per-character
        "allies": ["[[Dwarven Holds]]"],
        "rivals": ["[[Weavers of Agony]]", "[[Souls of the Devourer]]"],
        "era_founded": "[[Age of Night]]",
    },
    "People of Mokoweri": {
        "allies": ["[[Saurian Enclave]]"],
        "era_founded": "[[Age of the Endless Sun]]",
    },
    "Rahalan Nomads": {
        # No character pages for named leaders — leave leadership empty
        "era_founded": "[[Age of Forging]]",
    },
    "Saurian Enclave": {
        "leadership": [
            "[[Elder Kirex]]",
            "[[Elder Marn]]",
            "[[Elder Sylthassi]]",
            "[[Elder Thrasuun]]",
            "[[Elder Vellara]]",
        ],
        "allies": ["[[People of Mokoweri]]"],
        "era_founded": "[[Age of the Endless Sun]]",
    },
    "Souls of the Devourer": {
        "rivals": ["[[Firebrand Empire]]"],
        "era_founded": "[[Age of Stagnation]]",
    },
    "The Blackiron Collective": {
        "leadership": ["[[Kael Durnith]]"],
        "era_founded": "[[Age of Stagnation]]",
    },
    "The Flamebound of Magnus' Rest": {
        "leadership": ["[[Volgrin Flameward]]"],
        "era_founded": "[[Age of Forging]]",
    },
    "The Icebound of Uftine": {
        "leadership": ["[[Gromdir Stillhand]]"],
        "era_founded": "[[Age of Forging]]",
    },
    "The Order of Magnus": {
        # Founded after death of Magnus at 100 AS — Age of Stagnation
        "era_founded": "[[Age of Stagnation]]",
    },
    "The Solaran Federation of Worlds": {
        # era_founded and era_dissolved already set — nothing new to add
    },
    "The Stormbound of Thundrakar": {
        "leadership": ["[[Aundril Voxhammer]]"],
        "era_founded": "[[Age of Forging]]",
    },
    "The Tidebound of Draumhavn": {
        "leadership": ["[[Dagrin Thorne]]"],
        "era_founded": "[[Age of Forging]]",
    },
    "Thraysian Magocracy": {
        "leadership": [
            "[[Aelar Amakiir]]",
            "[[Zariel Mephista]]",
            "[[Farid al-Hakim]]",
        ],
        "era_founded": "[[Age of Stagnation]]",
    },
    "Velkhar Dominion": {
        "leadership": ["[[Vaelira Lyrandar]]"],
        "seat": "[[Calvereth]]",
        "era_founded": "[[Age of Stagnation]]",
        "rivals": ["[[Thraysian Magocracy]]"],
    },
    "Weavers of Agony": {
        "leadership": ["[[Varkhaal Bloodlash]]"],
        "rivals": ["[[Firebrand Empire]]"],
        "era_founded": "[[Age of Stagnation]]",
    },
}

# Fields that are overwritten even when already non-empty (except empty lists)
ALWAYS_OVERWRITE = {"leadership", "allies", "rivals", "seat"}

FACTIONS_DIR = DOCS_DIR / "factions"


def _is_empty(v) -> bool:
    """Return True for None, '', or empty list."""
    if v is None:
        return True
    if isinstance(v, str) and v.strip() == "":
        return True
    if isinstance(v, list) and len(v) == 0:
        return True
    return False


def patch_faction(path: Path, patches: dict, apply: bool) -> list[str]:
    meta, body = read_frontmatter(path)
    changes: list[str] = []

    for key, new_val in patches.items():
        existing = meta.get(key)
        if key in ALWAYS_OVERWRITE:
            if _is_empty(existing) and not _is_empty(new_val):
                changes.append(f"  + {key}: {new_val!r}")
                meta[key] = new_val
        else:
            # era_founded, seat (non-overwrite path) — only fill if missing
            if _is_empty(existing) and not _is_empty(new_val):
                changes.append(f"  + {key}: {new_val!r}")
                meta[key] = new_val

    if changes and apply:
        write_frontmatter(path, meta, body)

    return changes


def main() -> None:
    parser = argparse.ArgumentParser(description="Patch faction frontmatter.")
    parser.add_argument("--apply", action="store_true", help="Write changes to disk.")
    args = parser.parse_args()

    total_changes = 0
    for stem, patches in PATCHES.items():
        path = FACTIONS_DIR / f"{stem}.md"
        if not path.exists():
            print(f"[MISSING] {stem}.md — skipping")
            continue

        changes = patch_faction(path, patches, apply=args.apply)
        if changes:
            total_changes += len(changes)
            label = "APPLY" if args.apply else "DRY"
            print(f"[{label}] {stem}")
            for c in changes:
                print(c)
        else:
            print(f"[SKIP]  {stem} — nothing to add")

    mode = "Applied" if args.apply else "Dry-run"
    print(f"\n{mode}: {total_changes} field(s) across {len(PATCHES)} faction(s).")


if __name__ == "__main__":
    main()
