"""The big folder restructure.

Moves every .md file under docs/ to a type-rooted flat-ish structure
(max depth 3). The current deep nesting is replaced; semantic meaning
is now carried by frontmatter properties (continent, region, affiliation,
parent_faction, parent_race, pantheon, era, etc.), which were populated
in earlier passes (Layers 9-22).

Target layout:

    docs/
    ├── index.md                          (stays)
    ├── _meta/                            (stays)
    ├── eras/                  [flat]
    ├── events/                [depth 2 — by era folder]
    │   └── Age of <X>/
    ├── chronicles/            [flat]
    ├── myths/                 [flat]
    ├── prophecies/            [flat]
    ├── continents/            [flat]
    ├── regions/               [flat]
    ├── settlements/           [flat]
    ├── landmarks/             [flat]
    ├── ranges/                [flat]
    ├── waterways/             [flat]
    ├── planes/                [flat]    (single-file plane stubs + Elementis)
    ├── characters/            [flat]
    ├── races/                 [depth 3 — by lineage / parent-race / variant]
    ├── cultures/              [flat]
    ├── factions/              [flat]
    ├── houses/                [flat]
    ├── organisations/         [flat]
    ├── deities/               [depth 2 — by pantheon]
    │   └── Noxar/, Luxar/, God Hand/, Elementals/
    ├── pantheons/             [flat]    (created by skeleton script next)
    ├── cosmic-forces/         [flat]
    ├── artifacts/             [flat]
    ├── items/                 [flat]
    ├── resources/             [depth 2 — by category]
    ├── technologies/          [depth 2 — by discipline]
    ├── languages/             [depth 2 — by kind]
    ├── traditions/            [flat]
    └── essays/                [flat]

Filename collisions are resolved by appending the disambiguating
realm/continent in parentheses, e.g., 'Eversoul Grove.md' becomes
'Eversoul Grove (Mokoweri).md' if there's already an 'Eversoul Grove.md'
elsewhere.

Idempotent — re-running after a partial move continues where it left
off (existing destinations are detected and skipped).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Dict, Optional, Tuple

# Allow running as a script from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from refactor.common import (
    DOCS_DIR, REPO_ROOT, iter_md_files, read_frontmatter, rel_to_docs,
)


# Pantheon wikilink -> subfolder name under deities/
PANTHEON_FOLDER: Dict[str, str] = {
    "[[Noxar Gods]]":     "Noxar",
    "[[Luxar Gods]]":     "Luxar",
    "[[The God Hand]]":   "God Hand",
    "[[Elementals]]":     "Elementals",
    "Elementals":         "Elementals",
}

# Era wikilink -> subfolder name under events/
ERA_FOLDER: Dict[str, str] = {
    "[[Age of the Endless Sun]]": "Age of the Endless Sun",
    "[[Age of Forging]]":         "Age of Forging",
    "[[Age of Stagnation]]":      "Age of Stagnation",
    "[[Age of Night]]":           "Age of Night",
}

# Files that should be left in place (not restructured).
PROTECTED_PATHS = {"index.md"}
PROTECTED_PREFIXES = ("_meta/",)


def _strip_wikilink(s: str) -> str:
    if not isinstance(s, str):
        return ""
    s = s.strip()
    if s.startswith("[[") and s.endswith("]]"):
        inner = s[2:-2]
        if "|" in inner:
            inner = inner.split("|", 1)[0]
        return inner
    return s


def destination_for(rel: str, meta: dict) -> Optional[Path]:
    """Return the new docs-relative path for a file, or None if it should stay."""
    if rel in PROTECTED_PATHS:
        return None
    for prefix in PROTECTED_PREFIXES:
        if rel.startswith(prefix):
            return None

    type_ = meta.get("type")
    name = rel.split("/")[-1]  # filename with extension

    # ----- planes: single-file realm stubs + Elementis tree -----
    # Realms/<plane>/<plane>.md  OR  Realms/Elementis/...
    parts = rel.split("/")
    if len(parts) >= 2 and parts[0] == "Realms":
        realm = parts[1]
        # Skip Renascita; it gets normal type-based routing
        if realm != "Renascita":
            # Anything under a non-Renascita realm goes into planes/ flat
            return Path("planes") / name

    # ----- type-based routing -----
    if type_ == "era":
        return Path("eras") / name
    if type_ == "event":
        era = _strip_wikilink(meta.get("era", ""))
        era_folder = "Uncategorized"
        for k, v in ERA_FOLDER.items():
            if _strip_wikilink(k) == era:
                era_folder = v
                break
        return Path("events") / era_folder / name
    if type_ == "chronicle":
        return Path("chronicles") / name
    if type_ == "myth":
        return Path("myths") / name
    if type_ == "prophecy":
        return Path("prophecies") / name
    if type_ == "continent":
        return Path("continents") / name
    if type_ == "region":
        return Path("regions") / name
    if type_ == "settlement":
        return Path("settlements") / name
    if type_ == "landmark":
        return Path("landmarks") / name
    if type_ == "range":
        return Path("ranges") / name
    if type_ == "waterway":
        return Path("waterways") / name
    if type_ == "character":
        return Path("characters") / name
    if type_ == "race":
        # depth 3: lineage/<parent_race>/<file>.md  or lineage/<file>.md
        raw_lineage = meta.get("lineage") or ""
        # Strip wikilink syntax if present (some lineage values are wikilinks).
        lineage = _strip_wikilink(raw_lineage) if isinstance(raw_lineage, str) else ""
        lineage = lineage.strip() if lineage else "Uncategorized"
        # Also sanitise any stray special chars
        lineage = lineage.replace("[", "").replace("]", "").replace("|", "-")
        if not lineage:
            lineage = "Uncategorized"
        parent_race = _strip_wikilink(meta.get("parent_race", ""))
        if parent_race:
            return Path("races") / lineage / parent_race / name
        return Path("races") / lineage / name
    if type_ == "culture":
        return Path("cultures") / name
    if type_ == "faction":
        return Path("factions") / name
    if type_ == "house":
        return Path("houses") / name
    if type_ == "organisation":
        return Path("organisations") / name
    if type_ == "deity":
        pantheon = meta.get("pantheon", "")
        sub = PANTHEON_FOLDER.get(pantheon, "Other")
        return Path("deities") / sub / name
    if type_ == "cosmic-force":
        return Path("cosmic-forces") / name
    if type_ == "artifact":
        return Path("artifacts") / name
    if type_ == "item":
        return Path("items") / name
    if type_ == "resource":
        category = meta.get("category") or "Uncategorized"
        if isinstance(category, str):
            category = category.strip() or "Uncategorized"
        return Path("resources") / category / name
    if type_ == "technology":
        discipline = meta.get("discipline") or "Uncategorized"
        if isinstance(discipline, str):
            discipline = discipline.strip() or "Uncategorized"
        return Path("technologies") / discipline / name
    if type_ == "language":
        kind = meta.get("kind") or "Uncategorized"
        if isinstance(kind, str):
            kind = kind.strip().capitalize() or "Uncategorized"
        return Path("languages") / kind / name
    if type_ == "tradition":
        return Path("traditions") / name
    if type_ == "essay":
        return Path("essays") / name
    if type_ == "index":
        return None  # _meta/ files stay
    # Unknown / untyped: leave in place
    return None


def detect_parent_races_with_variants() -> set:
    """Return set of race-name strings that are parent races (have at least
    one variant referencing them via parent_race).
    """
    parents = set()
    for md in iter_md_files():
        meta, _ = read_frontmatter(md)
        if meta.get("type") != "race":
            continue
        pr = _strip_wikilink(meta.get("parent_race", ""))
        if pr:
            parents.add(pr)
    return parents


def main() -> None:
    # Pass 0: detect parent races with variants
    parents_with_variants = detect_parent_races_with_variants()

    # Pass 1: build full move plan
    plan = []  # list of (src_path, dest_relpath_string)
    used_destinations: Dict[str, Path] = {}
    skipped_protected = 0
    skipped_no_route = 0

    for md in iter_md_files():
        rel = rel_to_docs(md)
        meta, _ = read_frontmatter(md)
        dest = destination_for(rel, meta)
        if dest is None:
            if rel in PROTECTED_PATHS or any(rel.startswith(p) for p in PROTECTED_PREFIXES):
                skipped_protected += 1
            else:
                skipped_no_route += 1
            continue
        dest = Path(*dest.parts)  # normalize

        # Special: parent races that have variants get their own subfolder
        if meta.get("type") == "race":
            own_name = md.stem
            parent_race = _strip_wikilink(meta.get("parent_race", ""))
            if own_name in parents_with_variants and not parent_race:
                # Parent race itself goes inside a subfolder with the same name
                raw_lineage = meta.get("lineage") or ""
                lineage = _strip_wikilink(raw_lineage) if isinstance(raw_lineage, str) else ""
                lineage = lineage.strip() if lineage else "Uncategorized"
                lineage = lineage.replace("[", "").replace("]", "").replace("|", "-")
                if not lineage:
                    lineage = "Uncategorized"
                dest = Path("races") / lineage / own_name / md.name

        # Skip if already at target
        if rel == dest.as_posix():
            continue

        # Collision resolution: if another file is already moving to this
        # destination, append a disambiguator (realm or continent).
        dest_key = dest.as_posix()
        if dest_key in used_destinations:
            disambig = (
                _strip_wikilink(meta.get("continent", ""))
                or _strip_wikilink(meta.get("realm", ""))
                or "alt"
            )
            stem = md.stem
            new_name = "{} ({}){}".format(stem, disambig, md.suffix)
            dest = dest.parent / new_name
            dest_key = dest.as_posix()
            if dest_key in used_destinations:
                # Still colliding — append a numeric suffix
                i = 2
                while True:
                    candidate = dest.parent / "{} ({}-{}){}".format(stem, disambig, i, md.suffix)
                    if candidate.as_posix() not in used_destinations:
                        dest = candidate
                        dest_key = dest.as_posix()
                        break
                    i += 1

        # Also check if a real existing file is at the destination (from
        # a previous partial run). git mv will refuse to overwrite.
        if (DOCS_DIR / dest).exists():
            # Already moved; nothing to do
            continue

        used_destinations[dest_key] = md
        plan.append((md, dest))

    print("Plan summary:")
    print("  Files to move: {}".format(len(plan)))
    print("  Protected (unchanged): {}".format(skipped_protected))
    print("  No type route: {}".format(skipped_no_route))

    # Pass 2: execute the moves
    moved = 0
    failed = 0
    for src, dest in plan:
        target = DOCS_DIR / dest
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            subprocess.run(
                ["git", "mv",
                 str(src.relative_to(REPO_ROOT)),
                 str(target.relative_to(REPO_ROOT))],
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            moved += 1
        except subprocess.CalledProcessError as e:
            print("FAIL: {} -> {} :: {}".format(src.name, dest, e.stderr.strip()))
            failed += 1

    print()
    print("Moved: {}".format(moved))
    print("Failed: {}".format(failed))


if __name__ == "__main__":
    main()
