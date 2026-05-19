---
type: index
status: canon
tags:
- view
view: Saurian Enclave — Dashboard
---
# Saurian Enclave — Dashboard

*Members, sub-factions, organisations, and events of Saurian Enclave.*

## Members
```dataview
TABLE WITHOUT ID
  file.link AS "Name",
  race AS "Race",
  role AS "Role",
  living_status AS "Status"
FROM ""
WHERE type = "character" AND affiliation = [[Saurian Enclave]]
SORT file.name ASC
```

## Sub-factions
```dataview
LIST FROM "" WHERE type = "faction" AND parent_faction = [[Saurian Enclave]]
SORT file.name ASC
```

## Organisations within
```dataview
LIST FROM "" WHERE type = "organisation" AND parent_faction = [[Saurian Enclave]]
SORT file.name ASC
```

## Events involving
```dataview
TABLE WITHOUT ID file.link AS "Event", era AS "Era", year_display AS "When"
FROM "" WHERE type = "event" AND contains(participants, [[Saurian Enclave]])
SORT year ASC
```

## Everything else referencing
```dataview
LIST WHERE contains(file.inlinks, [[Saurian Enclave]])
SORT file.name ASC
LIMIT 30
```
