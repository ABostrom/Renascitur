---
type: index
status: canon
tags:
- view
view: People of Mokoweri — Dashboard
---
# People of Mokoweri — Dashboard

*Members, sub-factions, organisations, and events of People of Mokoweri.*

## Members
```dataview
TABLE WITHOUT ID
  file.link AS "Name",
  race AS "Race",
  role AS "Role",
  living_status AS "Status"
FROM ""
WHERE type = "character" AND affiliation = [[People of Mokoweri]]
SORT file.name ASC
```

## Sub-factions
```dataview
LIST FROM "" WHERE type = "faction" AND parent_faction = [[People of Mokoweri]]
SORT file.name ASC
```

## Organisations within
```dataview
LIST FROM "" WHERE type = "organisation" AND parent_faction = [[People of Mokoweri]]
SORT file.name ASC
```

## Events involving
```dataview
TABLE WITHOUT ID file.link AS "Event", era AS "Era", year_display AS "When"
FROM "" WHERE type = "event" AND contains(participants, [[People of Mokoweri]])
SORT year ASC
```

## Everything else referencing
```dataview
LIST WHERE contains(file.inlinks, [[People of Mokoweri]])
SORT file.name ASC
LIMIT 30
```
