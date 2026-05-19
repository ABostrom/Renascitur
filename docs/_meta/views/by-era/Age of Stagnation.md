---
type: index
status: canon
tags:
- view
view: Age of Stagnation — Era Dashboard
---
# Age of Stagnation — Era Dashboard

*Events, chronicles, myths, deities, and characters of the Age of Stagnation.*

## Events in this era
```dataview
TABLE WITHOUT ID
  file.link AS "Event",
  year_display AS "When",
  location AS "Where",
  importance AS "Importance",
  status AS "Status"
FROM ""
WHERE type = "event" AND contains(file.outlinks, [[Age of Stagnation]])
SORT year ASC
```

## Chronicles
```dataview
LIST FROM "" WHERE type = "chronicle" AND contains(file.outlinks, [[Age of Stagnation]])
SORT file.name ASC
```

## Myths from this era
```dataview
LIST FROM "" WHERE type = "myth" AND contains(file.outlinks, [[Age of Stagnation]])
SORT file.name ASC
```

## Deities emerging
```dataview
LIST FROM "" WHERE type = "deity" AND contains(file.outlinks, [[Age of Stagnation]])
SORT file.name ASC
```

## Characters living in this era
```dataview
LIST FROM "" WHERE type = "character" AND contains(file.outlinks, [[Age of Stagnation]])
SORT file.name ASC
```
