"""Extract relational frontmatter from the deep folder structure.

The folder hierarchy currently encodes a LOT of relationships that aren't
in frontmatter:
  - `.../Geography/<C>/Cities/<city>/Locations/X.md` -> X is inside <city>, on <C>
  - `.../Geography/<C>/Provinces/<region>/X.md` -> X is in region <region>
  - `.../Societies/<society>/Characters/X.md` -> X is affiliated with <society>
  - `.../Societies/<society>/Clans/X.md` -> X has parent_faction <society>
  - `.../Cosmology/Gods/<age>/<pantheon>/X.md` -> X's pantheon is <pantheon>,
    emerged in the canonical era for <age>
  - `.../Races/<lineage>/<race>/Variants/X.md` -> X's parent_race is <race>,
    lineage is <lineage>
  - etc.

This script extracts those implications and adds them as frontmatter, so
the Dataview blocks injected in 08 can actually find related notes.

Merge-only: never overwrites existing values. Idempotent.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Tuple

# Allow running as a script from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from refactor.common import iter_md_files, read_frontmatter, write_frontmatter, rel_to_docs, merge_metadata


AGE_FROM_OLD_NAME = {
    "First Age":  "[[Age of the Endless Sun]]",
    "Second Age": "[[Age of Forging]]",
    "Third Age":  "[[Age of Stagnation]]",
    "Fourth Age": "[[Age of Night]]",
}

SOCIETY_CONTAINER_FOLDERS = {
    "Characters", "Clans", "Orders", "Traditions",
    "Locations", "Religions", "Cults",
}

# Folders that are "categorizer" buckets, not subdivisions of their parent type.
RACE_CONTAINER_FOLDERS = {"Variants"}


def _wikilink(name: str) -> str:
    """Wrap a plain name in Obsidian wikilink syntax."""
    return "[[{}]]".format(name)


def infer_fields(relpath: str) -> Dict:
    """Return a dict of frontmatter fields implied by the file's folder path."""
    parts = relpath.split("/")
    fields: Dict = {}

    if not parts:
        return fields

    # =====================================================================
    # Realms/Renascita/...
    # =====================================================================
    if len(parts) >= 2 and parts[0] == "Realms" and parts[1] == "Renascita":
        fields["realm"] = _wikilink("Renascita")

        # -------------------------------------------------------------
        # Geography
        # -------------------------------------------------------------
        if len(parts) >= 4 and parts[2] == "Geography":
            continent_token = parts[3]

            # Islands/<island>/... — the island IS the continent in the taxonomy
            if continent_token == "Islands" and len(parts) >= 5:
                island = parts[4]
                # Don't add continent to the island's own self-named summary
                is_self = (len(parts) == 6 and parts[5] == "{}.md".format(island))
                if not is_self:
                    fields["continent"] = _wikilink(island)
                # Cities inside an island? Probably not in current data, skip.
                # Locations under island
                if len(parts) >= 6 and parts[5] == "Locations":
                    pass  # already has continent set above
            elif continent_token == "Islands":
                pass  # bare Realms/Renascita/Geography/Islands/ — unlikely
            else:
                # Normal continent
                is_continent_self = (
                    len(parts) == 5 and parts[4] == "{}.md".format(continent_token)
                )
                if not is_continent_self:
                    fields["continent"] = _wikilink(continent_token)

                # Cities subtree
                if len(parts) >= 6 and parts[4] == "Cities":
                    city = parts[5]
                    if len(parts) == 7:
                        # Cities/<city>/<file>.md — file inside city's own folder
                        filename = parts[6]
                        if filename != "{}.md".format(city):
                            # Not the city's self-summary, so it's inside the city
                            fields["inside"] = _wikilink(city)
                    elif len(parts) >= 8 and parts[6] == "Locations":
                        # Cities/<city>/Locations/<landmark>.md
                        fields["inside"] = _wikilink(city)

                # Provinces subtree
                if len(parts) >= 6 and parts[4] == "Provinces":
                    region_name = parts[5]
                    if len(parts) == 7:
                        # Provinces/<region>/<file>.md
                        filename = parts[6]
                        if filename != "{}.md".format(region_name):
                            fields["region"] = _wikilink(region_name)

        # -------------------------------------------------------------
        # Societies
        # -------------------------------------------------------------
        elif len(parts) >= 4 and parts[2] == "Societies":
            # Walk parts to find the first SOCIETY_CONTAINER_FOLDER, then the
            # part just before it is the society. Anything between Societies/
            # and the container is a chain of (potentially nested) societies.
            container_idx = None
            for i in range(3, len(parts)):
                if parts[i] in SOCIETY_CONTAINER_FOLDERS:
                    container_idx = i
                    break

            if container_idx is not None and container_idx > 3:
                society = parts[container_idx - 1]
                container = parts[container_idx]

                if container == "Characters":
                    fields["affiliation"] = _wikilink(society)
                elif container == "Clans":
                    fields["parent_faction"] = _wikilink(society)
                elif container == "Orders":
                    fields["parent_faction"] = _wikilink(society)
                elif container == "Traditions":
                    fields["culture"] = _wikilink(society)
                elif container == "Locations":
                    fields["controlled_by"] = _wikilink(society)
                elif container == "Religions":
                    fields["parent_faction"] = _wikilink(society)

                # If the society is itself nested under a parent grouping
                # (e.g., Societies/Dwarven Holds/The Tidebound of Draumhavn/Characters/...)
                # then container_idx - 2 is the grouping.
                if container_idx >= 5:
                    grouping = parts[container_idx - 2]
                    if grouping != "Societies":
                        # The intermediate society has the grouping as its parent
                        # (We don't add fields here for the deeper file — only the
                        # intermediate society's own self-summary; handled below.)
                        pass

            # Society self-named files (the society's own page)
            # Societies/<society>/<society>.md  or
            # Societies/<grouping>/<society>/<society>.md
            if len(parts) == 5 and parts[4] == "{}.md".format(parts[3]):
                # Top-level society self-summary; no parent in path
                pass
            elif len(parts) == 6 and parts[5] == "{}.md".format(parts[4]):
                # Nested society self-summary; parts[3] is grouping
                fields["parent_faction"] = _wikilink(parts[3])

        # -------------------------------------------------------------
        # Legendarium
        # -------------------------------------------------------------
        elif len(parts) >= 4 and parts[2] == "Legendarium":
            section = parts[3]
            if section == "Natural Resources" and len(parts) >= 6:
                # Legendarium/Natural Resources/<category>/<file>.md
                fields["category"] = parts[4]
            elif section == "Magic" and len(parts) >= 6:
                fields["discipline"] = parts[4]

        # -------------------------------------------------------------
        # Factions
        # -------------------------------------------------------------
        elif len(parts) >= 4 and parts[2] == "Factions":
            faction_section = parts[3]
            if faction_section == "Cults":
                fields["kind"] = "cult"
            elif faction_section == "Religions" and len(parts) >= 5:
                religion = parts[4]
                if len(parts) > 5:
                    fields["parent_faction"] = _wikilink(religion)

    # =====================================================================
    # Cosmology/...
    # =====================================================================
    elif len(parts) >= 1 and parts[0] == "Cosmology":
        if len(parts) >= 4 and parts[1] == "Gods":
            # Gods/<Age>/<pantheon>/<deity>.md  (or just Gods/<Age>/<file>.md)
            age = parts[2]
            if len(parts) == 5:
                # Gods/<Age>/<pantheon>/<deity>.md
                pantheon = parts[3]
                fields["pantheon"] = _wikilink(pantheon)
            if age in AGE_FROM_OLD_NAME:
                fields["era_of_emergence"] = AGE_FROM_OLD_NAME[age]

        elif len(parts) >= 3 and parts[1] == "Creation":
            if parts[2] == "The God Hand" and len(parts) >= 4:
                fields["pantheon"] = _wikilink("The God Hand")

        elif len(parts) >= 3 and parts[1] == "Elementals":
            fields["pantheon"] = "Elementals"

    # =====================================================================
    # Races/<lineage>/...
    # =====================================================================
    elif len(parts) >= 2 and parts[0] == "Races":
        lineage = parts[1]
        fields["lineage"] = lineage

        # Races/<lineage>/<race>/Variants/<variant>.md  -> parent_race
        if len(parts) >= 5 and parts[3] == "Variants":
            parent_race = parts[2]
            fields["parent_race"] = _wikilink(parent_race)

    # =====================================================================
    # Languages/<kind>/...
    # =====================================================================
    elif len(parts) >= 2 and parts[0] == "Languages":
        kind = parts[1]
        if kind in ("Ancient", "Modern"):
            fields["kind"] = kind.lower()

    # =====================================================================
    # History/<age>/<event>.md  -> era_of_emergence isn't right for events;
    # `era:` was already set by the original migration via era_from_history_path.
    # Nothing to add here.
    # =====================================================================

    return fields


def main() -> None:
    files_changed = 0
    fields_added = 0
    fields_by_type: Dict[str, int] = {}

    for md in iter_md_files():
        rel = rel_to_docs(md)
        inferred = infer_fields(rel)
        if not inferred:
            continue
        meta, body = read_frontmatter(md)

        # merge_metadata preserves existing values, so this is safe.
        merged = merge_metadata(meta, inferred)
        changed_keys = [k for k in inferred if merged.get(k) == inferred[k] and meta.get(k) != inferred[k]]

        if not changed_keys:
            continue

        write_frontmatter(md, merged, body)
        files_changed += 1
        fields_added += len(changed_keys)
        for k in changed_keys:
            fields_by_type[k] = fields_by_type.get(k, 0) + 1

    print("Files changed: {}".format(files_changed))
    print("Fields added: {}".format(fields_added))
    print("Fields by type:")
    for k, n in sorted(fields_by_type.items(), key=lambda kv: -kv[1]):
        print("  {:20s} {:5d}".format(k, n))


if __name__ == "__main__":
    main()
