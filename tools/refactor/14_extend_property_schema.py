"""Expand the property schema with ~30 new typed fields per note type.

Adds attribute properties (the data-asset / structured side of each note)
to existing corpus files AND to the corresponding templates. Merge-only:
never overwrites existing values.

Also performs conservative inference where the answer is certain from
existing data (e.g., every `type: deity` defaults to `nature: divine`).

Idempotent.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict

# Allow running as a script from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from refactor.common import (
    iter_md_files, read_frontmatter, write_frontmatter, REPO_ROOT,
)


# Per-type new properties + empty defaults.
# Strings -> "" ; lists -> [] ; booleans -> False
# Defaults intentionally empty so the field signals "not yet set" until authored.
SCHEMA_EXTENSIONS: Dict[str, Dict[str, Any]] = {
    "character": {
        "nature": "",
        "importance": "",
        "alignment": "",
        "gender": "",
        "role": [],
        "magic": [],
        "living_status": "",
        "era_of_birth": "",
        "era_of_death": "",
    },
    "faction": {
        "nature": "",
        "importance": "",
        "alignment": "",
        "society_form": "",
        "government": "",
        "economy": "",
        "seat": "",
        "size": "",
        "allies": [],
        "rivals": [],
        "magic": [],
    },
    "culture": {
        "nature": "",
        "importance": "",
        "society_form": "",
        "government": "",
        "magic": [],
    },
    "house": {
        "nature": "",
        "importance": "",
        "alignment": "",
        "government": "",
        "size": "",
        "allies": [],
        "rivals": [],
    },
    "organisation": {
        "nature": "",
        "importance": "",
        "alignment": "",
    },
    "settlement": {
        "importance": "",
        "population": "",
        "climate": "",
        "terrain": "",
        "defenses": "",
        "predominant_economy": "",
    },
    "region": {
        "climate": "",
        "terrain": [],
        "dominant_culture": "",
        "population_density": "",
    },
    "continent": {
        "climate": "",
        "dominant_culture": "",
        "population_density": "",
    },
    "landmark": {
        "nature": "",
        "importance": "",
    },
    "waterway": {
        "nature": "",
        "importance": "",
    },
    "range": {
        "nature": "",
        "importance": "",
    },
    "artifact": {
        "nature": "",
        "importance": "",
        "current_bearer": "",
        "cursed": False,
        "divine": False,
        "magic": [],
    },
    "item": {
        "nature": "",
        "importance": "",
    },
    "resource": {
        "nature": "",
        "importance": "",
    },
    "technology": {
        "nature": "",
        "importance": "",
        "magic": [],
    },
    "deity": {
        "nature": "divine",
        "importance": "",
        "alignment": "",
        "worshippers": [],
        "temples": [],
        "holy_day": "",
        "symbol": "",
    },
    "cosmic-force": {
        "nature": "eldritch",
        "importance": "",
        "alignment": "",
    },
    "tradition": {
        "nature": "",
        "importance": "",
        "magic": [],
    },
    "language": {
        "nature": "",
        "importance": "",
    },
    "era": {
        "importance": "",
    },
    "event": {
        "importance": "",
        "victors": [],
        "casualties": [],
        "outcome": "",
    },
    "myth": {
        "nature": "",
        "importance": "",
    },
    "chronicle": {
        "importance": "",
    },
    "prophecy": {
        "importance": "",
        "alignment": "",
    },
    "race": {
        "nature": "",
        "importance": "",
        "lifespan": "",
        "magic_affinity": [],
    },
}


# Map of (filename in templates/, type key).
TEMPLATE_FILES: Dict[str, str] = {
    "Character.md": "character",
    "Faction.md": "faction",
    "Culture.md": "culture",
    "House.md": "house",
    "Organisation.md": "organisation",
    "Settlement.md": "settlement",
    "Region.md": "region",
    "Continent.md": "continent",
    "Landmark.md": "landmark",
    "Waterway.md": "waterway",
    "Range.md": "range",
    "Artifact.md": "artifact",
    "Item.md": "item",
    "Resource.md": "resource",
    "Technology.md": "technology",
    "Deity.md": "deity",
    "CosmicForce.md": "cosmic-force",
    "Tradition.md": "tradition",
    "Language.md": "language",
    "Era.md": "era",
    "Event.md": "event",
    "Myth.md": "myth",
    "Chronicle.md": "chronicle",
    "Prophecy.md": "prophecy",
    "Race.md": "race",
}


def infer_overrides(meta: dict) -> dict:
    """Return additional fields to set based on confident inference.

    All values returned are merged AFTER the schema defaults, so they
    override defaults where appropriate, but still won't overwrite a
    pre-existing user-set value (merge logic handled in main()).
    """
    out: Dict[str, Any] = {}
    type_ = meta.get("type")
    pantheon = meta.get("pantheon", "")
    lineage = meta.get("lineage", "")

    # The God Hand are corrupted Grundthain.
    if pantheon == "[[The God Hand]]":
        out["nature"] = "corrupted"
    # Elementals are elemental.
    if pantheon == "[[Elementals]]" or pantheon == "Elementals":
        out["nature"] = "elemental"
    # Noxar Gods are divine (already default), but darker → unaligned/evil-ish.
    # Skip alignment inference — too judgement-y; leave to author.

    # Engineered lineage races.
    if type_ == "race" and lineage in ("Engineered", "engineered"):
        out["nature"] = "bioengineered"

    return out


def merge_defaults(existing: dict, defaults: dict) -> tuple:
    """Merge defaults into existing without overwriting. Return (new_meta, added_count)."""
    new_meta = dict(existing)
    added = 0
    for k, v in defaults.items():
        if k not in new_meta:
            new_meta[k] = v
            added += 1
    return new_meta, added


def apply_inferred(meta: dict, inferred: dict) -> tuple:
    """Apply inferred values, overriding defaults but NOT pre-existing user values.

    We tell defaults from user values by examining whether the field is the
    default value for that type or differs. Cheap approximation: if the field
    is empty string, empty list, or False → treat as default and overwrite.
    """
    out = dict(meta)
    overrides = 0
    for k, v in inferred.items():
        current = out.get(k)
        if current in ("", None, [], False):
            if current != v:
                out[k] = v
                overrides += 1
    return out, overrides


def process_corpus() -> None:
    files_changed = 0
    fields_added = 0
    inferred_count = 0
    by_type: Dict[str, int] = {}

    for md in iter_md_files():
        meta, body = read_frontmatter(md)
        type_ = meta.get("type")
        if type_ not in SCHEMA_EXTENSIONS:
            continue
        defaults = SCHEMA_EXTENSIONS[type_]
        new_meta, added = merge_defaults(meta, defaults)

        # Inference can override empty defaults.
        inferred = infer_overrides(new_meta)
        new_meta, overrides = apply_inferred(new_meta, inferred)

        if added == 0 and overrides == 0:
            continue

        write_frontmatter(md, new_meta, body)
        files_changed += 1
        fields_added += added
        inferred_count += overrides
        by_type[type_] = by_type.get(type_, 0) + 1

    print("Corpus:")
    print("  Files changed: {}".format(files_changed))
    print("  Fields added: {}".format(fields_added))
    print("  Inferred overrides: {}".format(inferred_count))
    print("  By type:")
    for t, n in sorted(by_type.items(), key=lambda kv: -kv[1]):
        print("    {:18s} {:5d}".format(t, n))


def process_templates() -> None:
    templates_dir = REPO_ROOT / "templates"
    templates_changed = 0
    for filename, type_ in TEMPLATE_FILES.items():
        path = templates_dir / filename
        if not path.exists():
            print("  WARN: missing template {}".format(filename))
            continue
        meta, body = read_frontmatter(path)
        defaults = SCHEMA_EXTENSIONS.get(type_, {})
        new_meta, added = merge_defaults(meta, defaults)
        if added == 0:
            continue
        write_frontmatter(path, new_meta, body)
        templates_changed += 1
        print("  Updated template {}: +{} fields".format(filename, added))
    print("Templates:")
    print("  Templates changed: {}".format(templates_changed))


def main() -> None:
    print("=== Corpus migration ===")
    process_corpus()
    print()
    print("=== Templates ===")
    process_templates()


if __name__ == "__main__":
    main()
