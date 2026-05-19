"""Inject per-type "Contents" Dataview blocks into container-type notes.

Each container type gets a tailored set of queries scoped via this.file.link
so the same blocks adapt to whatever file they live in. Open Pyrosia.md
and you see Pyrosia's contents; open Arcturia.md and you see Arcturia's.

Idempotent + refresh-capable:
- Without --refresh: skip files that already have the marker.
- With --refresh: replace the existing AUTO-INJECTED section with the
  current snippet content. Used when the snippet definitions change.

Container types covered:
  - continent: regions, settlements, ranges, waterways, landmarks, characters, events
  - region: settlements, landmarks, characters, events
  - settlement: landmarks inside, characters here, events here
  - era: events, chronicles, myths, characters of era
  - faction: members, organisations, seats, events
  - culture: characters, traditions, languages, settlements
  - race: variants, characters, languages, cultures
  - house: members, events, seat
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running as a script from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from refactor.common import iter_md_files, read_frontmatter, write_frontmatter

MARKER = "<!-- AUTO-INJECTED-DYNAMIC-CONTENTS — delete this comment and everything below to opt out; safe to edit otherwise -->"

# The full preamble used when appending: `---` separator + heading + marker.
SECTION_PREAMBLE = "\n\n---\n\n## Contents\n\n" + MARKER


# ---------------------------------------------------------------------------
# Per-type snippets. Each is appended to the file body, after existing prose,
# preceded by an `## Contents` header and the MARKER.
# ---------------------------------------------------------------------------

CONTINENT = """
### Regions

```dataview
LIST FROM ""
WHERE type = "region" AND continent = this.file.link
SORT file.name ASC
```

### Settlements

```dataview
TABLE WITHOUT ID
  file.link AS "Settlement",
  size AS "Size",
  controlled_by AS "Held by",
  status AS "Status"
FROM ""
WHERE type = "settlement" AND continent = this.file.link
SORT file.name ASC
```

### Mountain ranges

```dataview
LIST FROM ""
WHERE type = "range" AND continent = this.file.link
SORT file.name ASC
```

### Rivers & waterways

```dataview
LIST FROM ""
WHERE type = "waterway" AND continent = this.file.link
SORT file.name ASC
```

### Landmarks

```dataview
LIST FROM ""
WHERE type = "landmark" AND continent = this.file.link
SORT file.name ASC
```

### Characters located here

```dataview
TABLE WITHOUT ID
  file.link AS "Name",
  race AS "Race",
  affiliation AS "Affiliation"
FROM ""
WHERE type = "character" AND location = this.file.link
SORT file.name ASC
```

### Events here

```dataview
TABLE WITHOUT ID
  file.link AS "Event",
  era AS "Era",
  year_display AS "When"
FROM ""
WHERE type = "event" AND location = this.file.link
SORT year ASC
```

### Other notes referencing this place

```dataview
LIST WHERE contains(file.inlinks, this.file.link)
  AND !contains(string(file.path), "_meta/")
SORT file.name ASC
```
"""

REGION = """
### Settlements

```dataview
TABLE WITHOUT ID
  file.link AS "Settlement",
  size AS "Size",
  controlled_by AS "Held by"
FROM ""
WHERE type = "settlement" AND region = this.file.link
SORT file.name ASC
```

### Landmarks

```dataview
LIST FROM ""
WHERE type = "landmark" AND region = this.file.link
SORT file.name ASC
```

### Characters located here

```dataview
TABLE WITHOUT ID
  file.link AS "Name",
  race AS "Race",
  affiliation AS "Affiliation"
FROM ""
WHERE type = "character" AND location = this.file.link
SORT file.name ASC
```

### Events here

```dataview
TABLE WITHOUT ID
  file.link AS "Event",
  era AS "Era",
  year_display AS "When"
FROM ""
WHERE type = "event" AND location = this.file.link
SORT year ASC
```

### Other notes referencing this region

```dataview
LIST WHERE contains(file.inlinks, this.file.link)
  AND !contains(string(file.path), "_meta/")
SORT file.name ASC
```
"""

SETTLEMENT = """
### Districts and landmarks inside

```dataview
LIST FROM ""
WHERE type = "landmark" AND inside = this.file.link
SORT file.name ASC
```

### Characters here

```dataview
TABLE WITHOUT ID
  file.link AS "Name",
  race AS "Race",
  affiliation AS "Affiliation"
FROM ""
WHERE type = "character" AND location = this.file.link
SORT file.name ASC
```

### Events here

```dataview
TABLE WITHOUT ID
  file.link AS "Event",
  era AS "Era",
  year_display AS "When"
FROM ""
WHERE type = "event" AND location = this.file.link
SORT year ASC
```

### Other notes referencing this settlement

```dataview
LIST WHERE contains(file.inlinks, this.file.link)
  AND !contains(string(file.path), "_meta/")
SORT file.name ASC
```
"""

ERA = """
### Events in this era

```dataview
TABLE WITHOUT ID
  file.link AS "Event",
  year_display AS "When",
  location AS "Where",
  status AS "Status"
FROM ""
WHERE type = "event" AND era = this.file.link
SORT year ASC
```

### Chronicles

```dataview
LIST FROM ""
WHERE type = "chronicle" AND era_of_composition = this.file.link
SORT file.name ASC
```

### Myths from this era

```dataview
LIST FROM ""
WHERE type = "myth" AND era = this.file.link
SORT file.name ASC
```

### Characters who lived in this era

```dataview
LIST FROM ""
WHERE type = "character" AND era = this.file.link
SORT file.name ASC
```

### Settlements founded in this era

```dataview
LIST FROM ""
WHERE type = "settlement" AND era_founded = this.file.link
SORT file.name ASC
```

### Other notes referencing this era

```dataview
LIST WHERE contains(file.inlinks, this.file.link)
  AND !contains(string(file.path), "_meta/")
SORT file.name ASC
```
"""

FACTION = """
### Sub-factions

```dataview
LIST FROM ""
WHERE type = "faction" AND parent_faction = this.file.link
SORT file.name ASC
```

### Members

```dataview
TABLE WITHOUT ID
  file.link AS "Name",
  race AS "Race",
  location AS "Location"
FROM ""
WHERE type = "character" AND affiliation = this.file.link
SORT file.name ASC
```

### Organisations within

```dataview
LIST FROM ""
WHERE type = "organisation" AND parent_faction = this.file.link
SORT file.name ASC
```

### Events involving this faction

```dataview
TABLE WITHOUT ID
  file.link AS "Event",
  era AS "Era",
  year_display AS "When"
FROM ""
WHERE type = "event" AND contains(participants, this.file.link)
SORT year ASC
```

### Other notes referencing this faction

```dataview
LIST WHERE contains(file.inlinks, this.file.link)
  AND !contains(string(file.path), "_meta/")
SORT file.name ASC
```
"""

CULTURE = """
### Characters of this culture

```dataview
TABLE WITHOUT ID
  file.link AS "Name",
  race AS "Race",
  affiliation AS "Affiliation"
FROM ""
WHERE type = "character" AND culture = this.file.link
SORT file.name ASC
```

### Traditions

```dataview
LIST FROM ""
WHERE type = "tradition" AND culture = this.file.link
SORT file.name ASC
```

### Languages spoken

```dataview
LIST FROM ""
WHERE type = "language" AND contains(spoken_by, this.file.link)
SORT file.name ASC
```

### Other notes referencing this culture

```dataview
LIST WHERE contains(file.inlinks, this.file.link)
  AND !contains(string(file.path), "_meta/")
SORT file.name ASC
```
"""

RACE = """
### Variants

```dataview
LIST FROM ""
WHERE type = "race" AND parent_race = this.file.link
SORT file.name ASC
```

### Characters of this race

```dataview
TABLE WITHOUT ID
  file.link AS "Name",
  culture AS "Culture",
  affiliation AS "Affiliation"
FROM ""
WHERE type = "character" AND race = this.file.link
SORT file.name ASC
```

### Languages spoken

```dataview
LIST FROM ""
WHERE type = "language" AND contains(spoken_by, this.file.link)
SORT file.name ASC
```

### Cultures associated with this race

```dataview
LIST FROM ""
WHERE type = "culture" AND contains(races, this.file.link)
SORT file.name ASC
```

### Other notes referencing this race

```dataview
LIST WHERE contains(file.inlinks, this.file.link)
  AND !contains(string(file.path), "_meta/")
SORT file.name ASC
```
"""

HOUSE = """
### Members

```dataview
LIST FROM ""
WHERE type = "character" AND affiliation = this.file.link
SORT file.name ASC
```

### Events involving this house

```dataview
TABLE WITHOUT ID
  file.link AS "Event",
  era AS "Era",
  year_display AS "When"
FROM ""
WHERE type = "event" AND contains(participants, this.file.link)
SORT year ASC
```

### Other notes referencing this house

```dataview
LIST WHERE contains(file.inlinks, this.file.link)
  AND !contains(string(file.path), "_meta/")
SORT file.name ASC
```
"""

SNIPPETS = {
    "continent": CONTINENT,
    "region": REGION,
    "settlement": SETTLEMENT,
    "era": ERA,
    "faction": FACTION,
    "culture": CULTURE,
    "race": RACE,
    "house": HOUSE,
}


def _strip_existing_section(body: str) -> str:
    """Remove any previously injected `## Contents` section.

    Detects via the SECTION_PREAMBLE prefix; if found, truncates the body
    at that point. Returns the body unchanged if no marker is present.
    """
    idx = body.find(SECTION_PREAMBLE)
    if idx == -1:
        # Fallback: look for the marker alone in case the preamble shape drifted.
        idx = body.find(MARKER)
        if idx == -1:
            return body
        # Walk back to the `---` separator or `## Contents` header preceding it.
        prefix = body[:idx]
        sep = prefix.rfind("\n---\n")
        if sep != -1:
            return body[:sep].rstrip() + "\n"
        return body[:idx].rstrip() + "\n"
    return body[:idx].rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Replace existing AUTO-INJECTED sections with the current snippet.",
    )
    args = parser.parse_args()

    injected = 0
    refreshed = 0
    skipped_marker = 0
    skipped_wrong_type = 0
    for md in iter_md_files():
        meta, body = read_frontmatter(md)
        type_ = meta.get("type")
        if type_ not in SNIPPETS:
            skipped_wrong_type += 1
            continue
        already = MARKER in body
        if already and not args.refresh:
            skipped_marker += 1
            continue

        if already:
            body = _strip_existing_section(body)

        snippet = SNIPPETS[type_]
        addition = "{}\n{}".format(SECTION_PREAMBLE, snippet)
        new_body = body.rstrip() + addition + "\n"
        write_frontmatter(md, meta, new_body)
        label = "Refreshed" if already else "Injected"
        rel = md.relative_to(md.parent.parent.parent.parent)
        print("{} ({}): {}".format(label, type_, rel))
        if already:
            refreshed += 1
        else:
            injected += 1

    print("---")
    print("Injected: {}".format(injected))
    print("Refreshed: {}".format(refreshed))
    print("Skipped (marker already present, --refresh not set): {}".format(skipped_marker))
    print("Skipped (non-container type): {}".format(skipped_wrong_type))


if __name__ == "__main__":
    main()
