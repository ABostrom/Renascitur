"""Extract hierarchical tags from folder paths.

The current folder structure is acting as a pseudo-tag system; the goal
is to lift that categorization into explicit `tags:` frontmatter so the
information survives the upcoming folder flattening, and is queryable
in the Tag pane / Tag-Wrangler / Dataview.

Tag scheme: `<category>/<value>` (Obsidian's hierarchical-tag syntax).
The category prefix gives Tag-Wrangler a clean tree.

Categories produced:
  realm/         from Realms/<X>/
  continent/     from Geography/<X>/ (incl. Islands/<X>/)
  region/        from Geography/.../Provinces/<X>/
  place/         from Geography/.../Cities/<X>/
  faction/       from Societies/<X>/ (every nesting level produces a tag)
  pantheon/      from Cosmology/Gods/<age>/<pantheon>/, plus Elementals,
                 plus Cosmology/Creation/The God Hand
  era/           from History/<age>/ and Cosmology/Gods/<old-age>/
  lineage/       from Races/<lineage>/
  race/          from Races/<lineage>/<race>/[Variants/]<file>
  kind/          from Languages/Ancient/ and Languages/Modern/
  category/      from Legendarium/Natural Resources/<category>/ +
                 Cosmology/Creation/Corruption
  discipline/    from Legendarium/Magic/<discipline>/
  faction-kind/  from Factions/Cults/

Merge-only: never removes or rewrites existing tags. Idempotent.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Dict, List

# Allow running as a script from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from refactor.common import iter_md_files, read_frontmatter, write_frontmatter, rel_to_docs


# Folder names that are "container" folders — type-info, not categorical content.
# When walking Societies/<...>, anything in this set ends the recursion.
SOCIETY_CONTAINER_FOLDERS = {
    "Characters", "Clans", "Orders", "Traditions", "Locations",
    "Religions", "Cults", "Elders", "Emperors", "Great Houses",
    "Guilds", "Ships", "Technology", "Tyrannosaurs of Mokoweri",
}

# Map from old Age folder name to the canonical era slug.
OLD_AGE_TO_ERA_SLUG = {
    "First Age":  "age-of-the-endless-sun",
    "Second Age": "age-of-forging",
    "Third Age":  "age-of-stagnation",
    "Fourth Age": "age-of-night",
    # Idempotency: already-canonical forms map to themselves.
    "Age of the Endless Sun": "age-of-the-endless-sun",
    "Age of Forging":         "age-of-forging",
    "Age of Stagnation":      "age-of-stagnation",
    "Age of Night":           "age-of-night",
}


def slugify(s: str) -> str:
    """Convert a folder-style name into a tag-safe lowercase-hyphen slug."""
    s = s.lower()
    if s.startswith("the "):
        s = s[4:]
    # Smart quotes -> straight then strip
    s = s.replace("’", "").replace("‘", "").replace("'", "")
    s = s.replace(" ", "-")
    s = re.sub(r"[^a-z0-9-]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s


def extract_tags(relpath: str) -> List[str]:
    """Return the list of derived tags for a docs-relative path."""
    parts = relpath.split("/")
    tags: List[str] = []

    if not parts:
        return tags

    # =====================================================================
    # Realms/<realm>/...
    # =====================================================================
    if parts[0] == "Realms" and len(parts) >= 2:
        realm = parts[1]
        # Realms/Foo.md (a flat realm stub like Realms/Planes.md): treat the
        # name minus .md as the realm value, since there's no folder for it.
        if realm.endswith(".md"):
            realm = realm[:-3]
        tags.append("realm/" + slugify(realm))

        # ------- Geography ------------------------------------------------
        if len(parts) >= 4 and parts[2] == "Geography":
            geo = parts[3]
            if geo == "Islands" and len(parts) >= 5:
                tags.append("continent/" + slugify(parts[4]))
            elif geo != "Islands":
                tags.append("continent/" + slugify(geo))

            # Inside a city
            if len(parts) >= 6 and parts[4] == "Cities":
                tags.append("place/" + slugify(parts[5]))
            # Inside a province
            elif len(parts) >= 6 and parts[4] == "Provinces":
                tags.append("region/" + slugify(parts[5]))

        # ------- Societies -----------------------------------------------
        elif len(parts) >= 4 and parts[2] == "Societies":
            # Each non-container folder between Societies/ and the file
            # contributes a faction tag.
            for i in range(3, len(parts) - 1):
                seg = parts[i]
                if seg in SOCIETY_CONTAINER_FOLDERS:
                    break
                tags.append("faction/" + slugify(seg))

        # ------- Legendarium ---------------------------------------------
        elif len(parts) >= 4 and parts[2] == "Legendarium":
            section = parts[3]
            if section == "Natural Resources" and len(parts) >= 6:
                tags.append("category/" + slugify(parts[4]))
            elif section == "Magic" and len(parts) >= 6:
                tags.append("discipline/" + slugify(parts[4]))

        # ------- Factions ------------------------------------------------
        elif len(parts) >= 4 and parts[2] == "Factions":
            ftype = parts[3]
            if ftype == "Cults":
                tags.append("faction-kind/cult")
            elif ftype == "Religions" and len(parts) >= 5:
                tags.append("faction/" + slugify(parts[4]))

    # =====================================================================
    # Cosmology/...
    # =====================================================================
    elif parts[0] == "Cosmology":
        if len(parts) >= 4 and parts[1] == "Gods":
            old_age = parts[2]
            if old_age in OLD_AGE_TO_ERA_SLUG:
                tags.append("era/" + OLD_AGE_TO_ERA_SLUG[old_age])
            if len(parts) >= 5:
                tags.append("pantheon/" + slugify(parts[3]))
        elif len(parts) >= 3 and parts[1] == "Elementals":
            tags.append("pantheon/elementals")
        elif len(parts) >= 3 and parts[1] == "Creation":
            if parts[2] == "The God Hand" and len(parts) >= 4:
                tags.append("pantheon/the-god-hand")
            elif parts[2] == "Corruption" and len(parts) >= 4:
                tags.append("category/corruption")
            elif parts[2] == "Aeternum" and len(parts) >= 4:
                tags.append("category/aeternum")

    # =====================================================================
    # Races/<lineage>/...
    # =====================================================================
    elif parts[0] == "Races":
        if len(parts) >= 2:
            tags.append("lineage/" + slugify(parts[1]))
        # Races/<lineage>/<race>/[Variants/]<file>
        if len(parts) >= 4 and parts[2] != "Variants":
            tags.append("race/" + slugify(parts[2]))

    # =====================================================================
    # Languages/<kind>/...
    # =====================================================================
    elif parts[0] == "Languages":
        if len(parts) >= 2 and parts[1] in ("Ancient", "Modern"):
            tags.append("kind/" + parts[1].lower())

    # =====================================================================
    # History/<age>/...
    # =====================================================================
    elif parts[0] == "History":
        if len(parts) >= 2:
            age = parts[1]
            slug = OLD_AGE_TO_ERA_SLUG.get(age)
            if slug:
                tags.append("era/" + slug)

    # Dedupe while preserving order
    seen = set()
    deduped = []
    for t in tags:
        if t not in seen:
            seen.add(t)
            deduped.append(t)
    return deduped


def merge_tags(existing, new: List[str]) -> List[str]:
    """Merge new tags into existing tags list (preserve order, dedupe)."""
    if existing is None:
        existing = []
    if isinstance(existing, str):
        existing = [existing]
    if not isinstance(existing, list):
        return existing  # don't try to merge non-list weirdness
    seen = set(existing)
    out = list(existing)
    for t in new:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def main() -> None:
    files_changed = 0
    tags_added = 0
    tags_by_category: Dict[str, int] = {}

    for md in iter_md_files():
        rel = rel_to_docs(md)
        derived = extract_tags(rel)
        if not derived:
            continue
        meta, body = read_frontmatter(md)
        existing = meta.get("tags", [])
        merged = merge_tags(existing, derived)
        if merged == existing:
            continue
        meta["tags"] = merged
        write_frontmatter(md, meta, body)
        added_here = [t for t in derived if not isinstance(existing, list) or t not in existing]
        files_changed += 1
        tags_added += len(added_here)
        for t in added_here:
            cat = t.split("/", 1)[0]
            tags_by_category[cat] = tags_by_category.get(cat, 0) + 1

    print("Files changed: {}".format(files_changed))
    print("Tags added: {}".format(tags_added))
    print("By category:")
    for cat, n in sorted(tags_by_category.items(), key=lambda kv: -kv[1]):
        print("  {:18s} {:5d}".format(cat, n))


if __name__ == "__main__":
    main()
