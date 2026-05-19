"""Inject per-type "Contents" Dataview blocks into container-type notes.

Each container type gets a tailored set of queries scoped via this.file.link
so the same blocks adapt to whatever file they live in. Open Pyrosia.md
and you see Pyrosia's contents; open Arcturia.md and you see Arcturia's.

Idempotent via a marker comment. Re-running skips files that already
have the marker.

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

import sys
from pathlib import Path

# Allow running as a script from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from refactor.common import iter_md_files, read_frontmatter, write_frontmatter

MARKER = "<!-- AUTO-INJECTED-DYNAMIC-CONTENTS — delete this comment and everything below to opt out; safe to edit otherwise -->"


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
LIST FROM [[]]
WHERE !contains(string(file.path), "_meta/")
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
LIST FROM [[]]
WHERE !contains(string(file.path), "_meta/")
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
LIST FROM [[]]
WHERE !contains(string(file.path), "_meta/")
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
LIST FROM [[]]
WHERE !contains(string(file.path), "_meta/")
SORT file.name ASC
```
"""

FACTION = """
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
LIST FROM [[]]
WHERE !contains(string(file.path), "_meta/")
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
LIST FROM [[]]
WHERE !contains(string(file.path), "_meta/")
SORT file.name ASC
```
"""

RACE = """
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
LIST FROM [[]]
WHERE !contains(string(file.path), "_meta/")
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
LIST FROM [[]]
WHERE !contains(string(file.path), "_meta/")
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


def main() -> None:
    injected = 0
    skipped_marker = 0
    skipped_wrong_type = 0
    for md in iter_md_files():
        meta, body = read_frontmatter(md)
        type_ = meta.get("type")
        if type_ not in SNIPPETS:
            skipped_wrong_type += 1
            continue
        if MARKER in body:
            skipped_marker += 1
            continue
        snippet = SNIPPETS[type_]
        addition = "\n\n---\n\n## Contents\n\n{}\n{}".format(MARKER, snippet)
        new_body = body.rstrip() + addition + "\n"
        write_frontmatter(md, meta, new_body)
        print("Injected ({}): {}".format(type_, md.relative_to(md.parent.parent.parent.parent)))
        injected += 1

    print("---")
    print("Injected: {}".format(injected))
    print("Skipped (marker already present): {}".format(skipped_marker))
    print("Skipped (non-container type): {}".format(skipped_wrong_type))


if __name__ == "__main__":
    main()
