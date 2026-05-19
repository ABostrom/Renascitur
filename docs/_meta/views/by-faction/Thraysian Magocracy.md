---
type: index
status: canon
tags:
- view
view: Thraysian Magocracy — Dashboard
---
# Thraysian Magocracy — Dashboard

*Members, sub-factions, organisations, and events of Thraysian Magocracy.*

## Members
```dataview
TABLE WITHOUT ID
  file.link AS "Name",
  race AS "Race",
  role AS "Role",
  living_status AS "Status"
FROM ""
WHERE type = "character" AND string(affiliation) = "[[Thraysian Magocracy]]"
SORT file.name ASC
```

## Sub-factions
```dataview
LIST FROM "" WHERE type = "faction" AND string(parent_faction) = "[[Thraysian Magocracy]]"
SORT file.name ASC
```

## Organisations within
```dataview
LIST FROM "" WHERE type = "organisation" AND string(parent_faction) = "[[Thraysian Magocracy]]"
SORT file.name ASC
```

## Events involving
```dataview
TABLE WITHOUT ID file.link AS "Event", era AS "Era", year_display AS "When"
FROM "" WHERE type = "event" AND contains(string(participants), "[[Thraysian Magocracy]]")
SORT year ASC
```

## Everything else referencing
```dataview
LIST WHERE contains(file.outlinks, [[Thraysian Magocracy]])
  AND !contains(string(file.path), "_meta/views/")
SORT file.name ASC
LIMIT 30
```
