"""Create the Dataview-driven index pages under docs/_meta/."""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running as a script from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from refactor.common import DOCS_DIR, write_frontmatter

META = DOCS_DIR / "_meta"


PAGES = {
    "Stub Backlog.md": {
        "metadata": {"type": "index", "status": "canon", "tags": ["meta"]},
        "body": '''
# Stub Backlog

All notes with `status: stub`. Pick one when inspiration strikes.

```dataview
TABLE WITHOUT ID
  file.link AS "Note",
  type AS "Type",
  file.folder AS "Folder"
FROM ""
WHERE status = "stub"
SORT type ASC, file.name ASC
```
''',
    },
    "NPCs by Faction.md": {
        "metadata": {"type": "index", "status": "canon", "tags": ["meta"]},
        "body": '''
# NPCs by Faction

```dataview
TABLE WITHOUT ID
  file.link AS "Character",
  race AS "Race",
  location AS "Location"
FROM ""
WHERE type = "character"
GROUP BY affiliation
SORT affiliation ASC, file.name ASC
```
''',
    },
    "Locations by Realm.md": {
        "metadata": {"type": "index", "status": "canon", "tags": ["meta"]},
        "body": '''
# Locations by Realm

```dataview
TABLE WITHOUT ID
  file.link AS "Place",
  type AS "Kind"
FROM ""
WHERE contains(list("settlement","landmark","region","range","waterway","continent"), type)
GROUP BY continent
SORT continent ASC, type ASC, file.name ASC
```
''',
    },
    "Factions of Renascita.md": {
        "metadata": {"type": "index", "status": "canon", "tags": ["meta"]},
        "body": '''
# Factions of Renascita

```dataview
TABLE WITHOUT ID
  file.link AS "Faction",
  alignment AS "Alignment",
  status AS "Status"
FROM ""
WHERE type = "faction"
SORT file.name ASC
```
''',
    },
    "Campaign Reference.md": {
        "metadata": {"type": "index", "status": "canon", "tags": ["meta"]},
        "body": '''
# Campaign Reference

Quick-lookup dashboard for live sessions.

## Recently edited

```dataview
LIST FROM "" WHERE file.mtime SORT file.mtime DESC LIMIT 15
```

## Major factions

```dataview
LIST FROM "" WHERE type = "faction" SORT file.name ASC
```

## All canonical characters

```dataview
TABLE WITHOUT ID
  file.link AS "Name",
  race AS "Race",
  affiliation AS "Faction"
FROM ""
WHERE type = "character" AND status = "canon"
SORT affiliation ASC, file.name ASC
```
''',
    },
    "Timeline.md": {
        "metadata": {"type": "index", "status": "canon", "tags": ["meta"]},
        "body": '''
# Timeline

All events sorted chronologically.

```dataview
TABLE WITHOUT ID
  file.link AS "Event",
  era AS "Era",
  year AS "Year"
FROM ""
WHERE type = "event"
SORT era ASC, year ASC, file.name ASC
```
''',
    },
}


def main() -> None:
    META.mkdir(parents=True, exist_ok=True)
    for filename, content in PAGES.items():
        path = META / filename
        if path.exists():
            print("Skip (exists): {}".format(filename))
            continue
        write_frontmatter(path, content["metadata"], content["body"])
        print("Created: _meta/{}".format(filename))


if __name__ == "__main__":
    main()
