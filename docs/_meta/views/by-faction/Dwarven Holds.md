---
type: index
status: canon
tags:
- view
view: Dwarven Holds — Dashboard
---
# Dwarven Holds — Dashboard

*Members, sub-factions, organisations, and events of Dwarven Holds.*

## Members
```dataview
TABLE WITHOUT ID
  file.link AS "Name",
  race AS "Race",
  role AS "Role",
  living_status AS "Status"
FROM ""
WHERE type = "character" AND contains(file.outlinks, [[Dwarven Holds]])
SORT file.name ASC
```

## Sub-factions
```dataview
LIST FROM "" WHERE type = "faction" AND contains(file.outlinks, [[Dwarven Holds]])
SORT file.name ASC
```

## Organisations within
```dataview
LIST FROM "" WHERE type = "organisation" AND contains(file.outlinks, [[Dwarven Holds]])
SORT file.name ASC
```

## Events involving
```dataview
TABLE WITHOUT ID file.link AS "Event", era AS "Era", year_display AS "When"
FROM "" WHERE type = "event" AND contains(file.outlinks, [[Dwarven Holds]])
SORT year ASC
```

## Everything else referencing
```dataview
LIST WHERE contains(file.outlinks, [[Dwarven Holds]])
  AND !contains(string(file.path), "_meta/views/")
SORT file.name ASC
LIMIT 30
```
