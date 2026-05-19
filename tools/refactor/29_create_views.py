"""Generate the view library under _meta/views/.

Aaron's ask: 'create views in the left hand pane of obsidian' for
all regions, all cultures, all cities, etc.

Each .md file under _meta/views/ is a Dataview-driven page that
renders a filtered/sorted/typed list. Once created, Aaron right-clicks
each in the file explorer to bookmark it; the Bookmarks pane in the
left sidebar then becomes his custom view menu.

Categories:
  1. By-type views (one per major type)
  2. By-realm views (per major realm/region/continent)
  3. By-faction views (per major faction)
  4. By-era views (per Age)
  5. Workflow views (stubs, drafts, recently edited, etc.)
  6. Cross-cutting views (magic disciplines, character roles, etc.)
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from refactor.common import DOCS_DIR, write_frontmatter


VIEWS_DIR = DOCS_DIR / "_meta" / "views"


def _make(filename: str, title: str, desc: str, body: str,
          metadata_extra: Dict[str, Any] = None) -> None:
    """Write a single view file."""
    path = VIEWS_DIR / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    metadata = {
        "type": "index",
        "status": "canon",
        "tags": ["view"],
        "view": title,
    }
    if metadata_extra:
        metadata.update(metadata_extra)
    full_body = "\n# {}\n\n*{}*\n\n{}\n".format(title, desc, body.strip())
    write_frontmatter(path, metadata, full_body)


# ---------------------------------------------------------------------------
# 1. By-type views
# ---------------------------------------------------------------------------

BY_TYPE = [
    ("continent",      "All Continents",
     "Major landmasses across all realms.",
     '''```dataview
TABLE WITHOUT ID
  file.link AS "Continent",
  realm AS "Realm",
  climate AS "Climate",
  status AS "Status"
FROM ""
WHERE type = "continent"
SORT realm ASC, file.name ASC
```'''),

    ("region",         "All Regions",
     "Provinces and political subdivisions, grouped by continent.",
     '''```dataview
TABLE WITHOUT ID
  file.link AS "Region",
  continent AS "Continent",
  climate AS "Climate",
  status AS "Status"
FROM ""
WHERE type = "region"
SORT continent ASC, file.name ASC
```'''),

    ("settlement",     "All Settlements",
     "Cities, towns, holds, and villages.",
     '''```dataview
TABLE WITHOUT ID
  file.link AS "Settlement",
  continent AS "Continent",
  region AS "Region",
  size AS "Size",
  controlled_by AS "Controlled by",
  importance AS "Importance"
FROM ""
WHERE type = "settlement"
SORT continent ASC, file.name ASC
```'''),

    ("landmark",       "All Landmarks",
     "Points of interest, ruins, sacred sites, in-city districts.",
     '''```dataview
TABLE WITHOUT ID
  file.link AS "Landmark",
  continent AS "Continent",
  region AS "Region",
  inside AS "Inside",
  nature AS "Nature"
FROM ""
WHERE type = "landmark"
SORT continent ASC, file.name ASC
```'''),

    ("range",          "All Mountain Ranges", "Mountain ranges and named peaks.",
     '''```dataview
TABLE WITHOUT ID file.link AS "Range", continent AS "Continent", kind AS "Kind"
FROM "" WHERE type = "range" SORT continent ASC, file.name ASC
```'''),

    ("waterway",       "All Waterways", "Rivers, lakes, seas, and coasts.",
     '''```dataview
TABLE WITHOUT ID file.link AS "Waterway", continent AS "Continent", kind AS "Kind"
FROM "" WHERE type = "waterway" SORT continent ASC, file.name ASC
```'''),

    ("plane",          "All Planes",
     "Non-Renascita realms (outer planes, elemental planes, etc.).",
     '''```dataview
TABLE WITHOUT ID
  file.link AS "Plane",
  type AS "Type",
  status AS "Status"
FROM "planes"
SORT file.name ASC
```'''),

    ("character",      "All Characters",
     "Every named NPC across the world.",
     '''```dataview
TABLE WITHOUT ID
  file.link AS "Name",
  race AS "Race",
  culture AS "Culture",
  affiliation AS "Faction",
  location AS "Location",
  gender AS "Gender",
  living_status AS "Status"
FROM ""
WHERE type = "character"
SORT affiliation ASC, file.name ASC
```'''),

    ("race",           "All Races",
     "Races and variants, grouped by lineage.",
     '''```dataview
TABLE WITHOUT ID
  file.link AS "Race",
  lineage AS "Lineage",
  parent_race AS "Parent",
  nature AS "Nature",
  importance AS "Importance"
FROM ""
WHERE type = "race"
SORT lineage ASC, file.name ASC
```'''),

    ("culture",        "All Cultures",
     "Cultural identities, distinct from races (a culture may span races).",
     '''```dataview
TABLE WITHOUT ID
  file.link AS "Culture",
  homeland AS "Homeland",
  society_form AS "Form"
FROM ""
WHERE type = "culture"
SORT file.name ASC
```'''),

    ("faction",        "All Factions",
     "Political and organized groups. Includes Houses (kind: house).",
     '''```dataview
TABLE WITHOUT ID
  file.link AS "Faction",
  realm AS "Realm",
  society_form AS "Form",
  government AS "Government",
  seat AS "Seat",
  size AS "Scale",
  importance AS "Importance"
FROM ""
WHERE type = "faction"
SORT realm ASC, importance ASC, file.name ASC
```'''),

    ("house",          "Firebrand Great Houses",
     "The 12 Great Houses of the Firebrand Empire.",
     '''```dataview
TABLE WITHOUT ID
  file.link AS "House",
  current_head AS "Head",
  seat AS "Seat",
  sigil AS "Sigil",
  importance AS "Importance"
FROM ""
WHERE type = "house" OR kind = "house"
SORT file.name ASC
```'''),

    ("organisation",   "All Organisations",
     "Orders, guilds, clans, cults — any organized sub-group.",
     '''```dataview
TABLE WITHOUT ID
  file.link AS "Organisation",
  parent_faction AS "Parent",
  realm AS "Realm",
  era_founded AS "Founded"
FROM ""
WHERE type = "organisation"
SORT parent_faction ASC, file.name ASC
```'''),

    ("deity",          "All Deities",
     "Gods, grouped by pantheon.",
     '''```dataview
TABLE WITHOUT ID
  file.link AS "Deity",
  pantheon AS "Pantheon",
  domain AS "Domain",
  alignment AS "Alignment",
  era_of_emergence AS "Emerged"
FROM ""
WHERE type = "deity"
SORT pantheon ASC, file.name ASC
```'''),

    ("cosmic-force",   "All Cosmic Forces",
     "Abstract cosmic forces and eldritch entities.",
     '''```dataview
TABLE WITHOUT ID
  file.link AS "Force",
  nature AS "Nature",
  opposed_by AS "Opposes",
  importance AS "Importance"
FROM ""
WHERE type = "cosmic-force"
SORT importance ASC, file.name ASC
```'''),

    ("artifact",       "All Artifacts",
     "Named magical items and legendary objects.",
     '''```dataview
TABLE WITHOUT ID
  file.link AS "Artifact",
  era_of_creation AS "Created",
  current_bearer AS "Bearer",
  cursed AS "Cursed",
  divine AS "Divine",
  importance AS "Importance"
FROM ""
WHERE type = "artifact"
SORT importance ASC, file.name ASC
```'''),

    ("resource",       "All Resources",
     "Materials, substances, ores, herbs — grouped by category.",
     '''```dataview
TABLE WITHOUT ID
  file.link AS "Resource",
  category AS "Category",
  realm AS "Realm"
FROM ""
WHERE type = "resource"
SORT category ASC, file.name ASC
```'''),

    ("technology",     "All Technologies & Magic Schools",
     "Techniques, inventions, magic disciplines.",
     '''```dataview
TABLE WITHOUT ID
  file.link AS "Technology",
  discipline AS "Discipline",
  era_of_invention AS "Invented",
  invented_by AS "By"
FROM ""
WHERE type = "technology"
SORT discipline ASC, file.name ASC
```'''),

    ("language",       "All Languages",
     "Spoken languages, grouped by Ancient/Modern.",
     '''```dataview
TABLE WITHOUT ID
  file.link AS "Language",
  kind AS "Kind",
  era_bloom AS "Bloomed",
  still_spoken AS "Living",
  parent_language AS "Parent"
FROM ""
WHERE type = "language"
SORT kind ASC, file.name ASC
```'''),

    ("tradition",      "All Traditions",
     "Rituals, practices, customs.",
     '''```dataview
TABLE WITHOUT ID
  file.link AS "Tradition",
  culture AS "Culture",
  realm AS "Realm",
  era AS "Era"
FROM ""
WHERE type = "tradition"
SORT culture ASC, file.name ASC
```'''),

    ("event",          "All Events (Chronological)",
     "Historical events across all four Ages.",
     '''```dataview
TABLE WITHOUT ID
  file.link AS "Event",
  era AS "Era",
  year_display AS "When",
  location AS "Where",
  importance AS "Importance",
  status AS "Status"
FROM ""
WHERE type = "event"
SORT era ASC, year ASC, file.name ASC
```'''),

    ("era",            "All Eras", "The Four Ages.",
     '''```dataview
TABLE WITHOUT ID file.link AS "Era", code AS "Code", aliases AS "Also known as"
FROM "" WHERE type = "era" SORT code ASC
```'''),

    ("chronicle",      "All Chronicles", "In-world source texts.",
     '''```dataview
TABLE WITHOUT ID file.link AS "Chronicle", attributed_to AS "By", era_of_composition AS "Era", housed_in AS "Housed in"
FROM "" WHERE type = "chronicle" SORT era_of_composition ASC, file.name ASC
```'''),

    ("myth",           "All Myths", "Mythological accounts of cosmic and historical events.",
     '''```dataview
TABLE WITHOUT ID file.link AS "Myth", cultures_of_origin AS "From", era AS "Era"
FROM "" WHERE type = "myth" SORT file.name ASC
```'''),

    ("prophecy",       "All Prophecies", "Prophecies, omens, dreams.",
     '''```dataview
TABLE WITHOUT ID file.link AS "Prophecy", kind AS "Kind", attributed_to AS "By", era AS "Era"
FROM "" WHERE type = "prophecy" SORT file.name ASC
```'''),
]


# ---------------------------------------------------------------------------
# 2. By-realm / by-continent views
# ---------------------------------------------------------------------------

REALMS = [
    ("Pyrosia", "[[Pyrosia]]"),
    ("Mokoweri", "[[Mokoweri]]"),
    ("Arcturia", "[[Arcturia]]"),
    ("Qethusiyya", "[[Qethusiyya]]"),
    ("Aquaria", "[[Aquaria]]"),
    ("Draumhavn", "[[Draumhavn]]"),
    ("Thundrakar", "[[Thundrakar]]"),
    ("The World Beneath", "[[The World Beneath]]"),
]


def realm_view_body(continent_wikilink: str) -> str:
    # Use contains(file.outlinks, [[X]]) — robustly handles whether the
    # frontmatter value was parsed as a Link object or a quoted string,
    # because file.outlinks always lists outgoing links from the file
    # (frontmatter + body) as Link objects.
    L = continent_wikilink
    return '''## Regions
```dataview
LIST FROM "" WHERE type = "region" AND contains(file.outlinks, ''' + L + ''')
SORT file.name ASC
```

## Settlements
```dataview
TABLE WITHOUT ID
  file.link AS "Settlement",
  size AS "Size",
  controlled_by AS "Held by"
FROM ""
WHERE type = "settlement" AND contains(file.outlinks, ''' + L + ''')
SORT file.name ASC
```

## Landmarks
```dataview
LIST FROM "" WHERE type = "landmark" AND contains(file.outlinks, ''' + L + ''')
SORT file.name ASC
```

## Ranges
```dataview
LIST FROM "" WHERE type = "range" AND contains(file.outlinks, ''' + L + ''')
SORT file.name ASC
```

## Waterways
```dataview
LIST FROM "" WHERE type = "waterway" AND contains(file.outlinks, ''' + L + ''')
SORT file.name ASC
```

## Characters located here
```dataview
TABLE WITHOUT ID
  file.link AS "Name",
  race AS "Race",
  affiliation AS "Faction"
FROM ""
WHERE type = "character" AND contains(file.outlinks, ''' + L + ''')
SORT file.name ASC
```

## Events here
```dataview
TABLE WITHOUT ID file.link AS "Event", era AS "Era", year_display AS "When"
FROM "" WHERE type = "event" AND contains(file.outlinks, ''' + L + ''')
SORT year ASC
```'''


# ---------------------------------------------------------------------------
# 3. By-faction views
# ---------------------------------------------------------------------------

MAJOR_FACTIONS = [
    ("Firebrand Empire", "[[Firebrand Empire]]"),
    ("Dwarven Holds", "[[Dwarven Holds]]"),
    ("Saurian Enclave", "[[Saurian Enclave]]"),
    ("Thraysian Magocracy", "[[Thraysian Magocracy]]"),
    ("Rahalan Nomads", "[[Rahalan Nomads]]"),
    ("The Blackiron Collective", "[[The Blackiron Collective]]"),
    ("People of Mokoweri", "[[People of Mokoweri]]"),
    ("The Solaran Federation of Worlds", "[[The Solaran Federation of Worlds]]"),
    ("Velkhar Dominion", "[[Velkhar Dominion]]"),
]


def faction_view_body(wlink: str) -> str:
    L = wlink
    return '''## Members
```dataview
TABLE WITHOUT ID
  file.link AS "Name",
  race AS "Race",
  role AS "Role",
  living_status AS "Status"
FROM ""
WHERE type = "character" AND contains(file.outlinks, ''' + L + ''')
SORT file.name ASC
```

## Sub-factions
```dataview
LIST FROM "" WHERE type = "faction" AND contains(file.outlinks, ''' + L + ''')
SORT file.name ASC
```

## Organisations within
```dataview
LIST FROM "" WHERE type = "organisation" AND contains(file.outlinks, ''' + L + ''')
SORT file.name ASC
```

## Events involving
```dataview
TABLE WITHOUT ID file.link AS "Event", era AS "Era", year_display AS "When"
FROM "" WHERE type = "event" AND contains(file.outlinks, ''' + L + ''')
SORT year ASC
```

## Everything else referencing
```dataview
LIST WHERE contains(file.outlinks, ''' + L + ''')
  AND !contains(string(file.path), "_meta/views/")
SORT file.name ASC
LIMIT 30
```'''


# ---------------------------------------------------------------------------
# 4. By-era views
# ---------------------------------------------------------------------------

ERAS = [
    ("Age of the Endless Sun", "[[Age of the Endless Sun]]"),
    ("Age of Forging",         "[[Age of Forging]]"),
    ("Age of Stagnation",      "[[Age of Stagnation]]"),
    ("Age of Night",           "[[Age of Night]]"),
]


def era_view_body(wlink: str) -> str:
    L = wlink
    return '''## Events in this era
```dataview
TABLE WITHOUT ID
  file.link AS "Event",
  year_display AS "When",
  location AS "Where",
  importance AS "Importance",
  status AS "Status"
FROM ""
WHERE type = "event" AND contains(file.outlinks, ''' + L + ''')
SORT year ASC
```

## Chronicles
```dataview
LIST FROM "" WHERE type = "chronicle" AND contains(file.outlinks, ''' + L + ''')
SORT file.name ASC
```

## Myths from this era
```dataview
LIST FROM "" WHERE type = "myth" AND contains(file.outlinks, ''' + L + ''')
SORT file.name ASC
```

## Deities emerging
```dataview
LIST FROM "" WHERE type = "deity" AND contains(file.outlinks, ''' + L + ''')
SORT file.name ASC
```

## Characters living in this era
```dataview
LIST FROM "" WHERE type = "character" AND contains(file.outlinks, ''' + L + ''')
SORT file.name ASC
```'''


# ---------------------------------------------------------------------------
# 5. Workflow / quality views
# ---------------------------------------------------------------------------

WORKFLOW = [
    ("Stub Backlog", "Notes whose structure is in place but prose unwritten.",
     '''```dataview
TABLE WITHOUT ID file.link AS "Note", type AS "Type", file.folder AS "Folder"
FROM ""
WHERE status = "stub" AND !contains(string(file.path), "_meta/")
SORT type ASC, file.name ASC
```'''),

    ("Drafts", "Notes in draft (typed but not yet canonical).",
     '''```dataview
TABLE WITHOUT ID file.link AS "Note", type AS "Type", file.mtime AS "Last edit"
FROM ""
WHERE status = "draft" AND !contains(string(file.path), "_meta/")
SORT file.mtime DESC
```'''),

    ("Canon", "Notes marked canonical.",
     '''```dataview
TABLE WITHOUT ID file.link AS "Note", type AS "Type"
FROM "" WHERE status = "canon" AND !contains(string(file.path), "_meta/")
SORT type ASC, file.name ASC
```'''),

    ("Recently Edited", "30 most-recently-modified notes.",
     '''```dataview
TABLE WITHOUT ID file.link AS "Note", type AS "Type", file.mtime AS "When"
FROM "" WHERE !contains(string(file.path), "_meta/")
SORT file.mtime DESC
LIMIT 30
```'''),

    ("Legendary Things", "Anything tagged as legendary in importance.",
     '''```dataview
TABLE WITHOUT ID file.link AS "Note", type AS "Type", era AS "Era"
FROM "" WHERE importance = "legendary"
SORT type ASC, file.name ASC
```'''),
]


# ---------------------------------------------------------------------------
# 6. Cross-cutting views
# ---------------------------------------------------------------------------

CROSS_CUTTING = [
    ("Magic Disciplines", "Magic schools and the entities that wield them.",
     '''## All magic disciplines
```dataview
TABLE WITHOUT ID file.link AS "Discipline", discipline AS "School", era_of_invention AS "Invented"
FROM "" WHERE type = "technology" AND discipline != null
SORT discipline ASC, file.name ASC
```

## Practitioners
```dataview
LIST FROM ""
WHERE (type = "character" OR type = "faction" OR type = "culture")
  AND magic != null AND length(magic) > 0
SORT file.name ASC
```'''),

    ("Notable NPCs", "Characters with importance: major or legendary.",
     '''```dataview
TABLE WITHOUT ID
  file.link AS "Name",
  race AS "Race",
  affiliation AS "Faction",
  role AS "Role",
  importance AS "Tier"
FROM ""
WHERE type = "character" AND (importance = "major" OR importance = "legendary")
SORT importance ASC, file.name ASC
```'''),

    ("Characters by Role", "NPCs grouped by what they do.",
     '''```dataview
TABLE WITHOUT ID file.link AS "Name", race AS "Race", affiliation AS "Faction"
FROM "" WHERE type = "character" AND role != null AND length(role) > 0
GROUP BY role
```'''),

    ("Saurian Elders", "The current Saurian Enclave council.",
     '''```dataview
TABLE WITHOUT ID file.link AS "Elder", living_status AS "Status", role AS "Role"
FROM "" WHERE type = "character" AND affiliation = "[[Saurian Enclave]]"
SORT file.name ASC
```'''),

    ("Firebrand Emperors", "All Emperors and Empresses of Firebrand (historical and current).",
     '''```dataview
TABLE WITHOUT ID
  file.link AS "Name",
  race AS "Race",
  living_status AS "Status",
  era AS "Era"
FROM "" WHERE type = "character" AND affiliation = "[[Firebrand Empire]]" AND contains(role, "ruler")
SORT file.name ASC
```'''),

    ("All Dwarven Sub-factions", "The 4 Dwarven holds + their characters.",
     '''## The four holds
```dataview
LIST FROM "" WHERE type = "faction" AND parent_faction = "[[Dwarven Holds]]"
SORT file.name ASC
```

## All Dwarven characters
```dataview
TABLE WITHOUT ID
  file.link AS "Name",
  affiliation AS "Hold",
  role AS "Role"
FROM "" WHERE type = "character" AND race = "[[Dwarf]]"
SORT affiliation ASC, file.name ASC
```'''),

    ("Aberrations and Corruption", "Aberrant and corrupted entities.",
     '''```dataview
TABLE WITHOUT ID file.link AS "Entity", type AS "Type", nature AS "Nature"
FROM "" WHERE nature = "aberrant" OR nature = "corrupted"
SORT type ASC, file.name ASC
```'''),
]


# ---------------------------------------------------------------------------
# Generate everything
# ---------------------------------------------------------------------------

def main() -> None:
    VIEWS_DIR.mkdir(parents=True, exist_ok=True)
    count = 0

    # 1. By type
    for type_key, title, desc, body in BY_TYPE:
        _make("by-type/{}.md".format(title), title, desc, body)
        count += 1

    # 2. By realm
    for label, wlink in REALMS:
        _make("by-realm/{}.md".format(label), "{} — Overview".format(label),
              "Everything inside the {} continent.".format(label),
              realm_view_body(wlink))
        count += 1

    # 3. By faction
    for label, wlink in MAJOR_FACTIONS:
        _make("by-faction/{}.md".format(label), "{} — Dashboard".format(label),
              "Members, sub-factions, organisations, and events of {}.".format(label),
              faction_view_body(wlink))
        count += 1

    # 4. By era
    for label, wlink in ERAS:
        _make("by-era/{}.md".format(label), "{} — Era Dashboard".format(label),
              "Events, chronicles, myths, deities, and characters of the {}.".format(label),
              era_view_body(wlink))
        count += 1

    # 5. Workflow
    for title, desc, body in WORKFLOW:
        _make("workflow/{}.md".format(title), title, desc, body)
        count += 1

    # 6. Cross-cutting
    for title, desc, body in CROSS_CUTTING:
        _make("cross-cutting/{}.md".format(title), title, desc, body)
        count += 1

    # Index of all views
    index_body = '''*Bookmark any of these for one-click access in the Bookmarks sidebar pane.*

## By type — pick a category, see everything in it

```dataview
LIST FROM "_meta/views/by-type" SORT file.name ASC
```

## By realm — see everything inside a continent

```dataview
LIST FROM "_meta/views/by-realm" SORT file.name ASC
```

## By faction — culture-specific dashboards

```dataview
LIST FROM "_meta/views/by-faction" SORT file.name ASC
```

## By era — temporal dashboards

```dataview
LIST FROM "_meta/views/by-era" SORT file.name ASC
```

## Workflow — for writing and curating

```dataview
LIST FROM "_meta/views/workflow" SORT file.name ASC
```

## Cross-cutting — themes spanning multiple types

```dataview
LIST FROM "_meta/views/cross-cutting" SORT file.name ASC
```

---

### How to bookmark for the sidebar

1. Enable the **Bookmarks** core plugin (already on by default).
2. Right-click any view file in the file explorer.
3. Choose **"Bookmark"** (or **"Bookmark and rename..."**).
4. The view appears in the Bookmarks pane in the left sidebar.

You can group bookmarks: select multiple, right-click, **"Bookmark together in group..."**.
'''
    _make("Views.md", "Views",
          "Index of all view files. Bookmark these for sidebar navigation.",
          index_body)
    count += 1

    print("Created {} view files under _meta/views/".format(count))


if __name__ == "__main__":
    main()
