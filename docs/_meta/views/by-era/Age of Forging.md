---
type: index
status: canon
tags:
- view
view: Age of Forging — Era Dashboard
---
# Age of Forging — Era Dashboard

*Events, chronicles, myths, deities, and characters of the Age of Forging.*

## Events in this era
```dataview
TABLE WITHOUT ID
  file.link AS "Event",
  year_display AS "When",
  location AS "Where",
  importance AS "Importance",
  status AS "Status"
FROM ""
WHERE type = "event" AND contains(file.outlinks, [[Age of Forging]])
SORT year ASC
```

## Chronicles
```dataview
LIST FROM "" WHERE type = "chronicle" AND contains(file.outlinks, [[Age of Forging]])
SORT file.name ASC
```

## Myths from this era
```dataview
LIST FROM "" WHERE type = "myth" AND contains(file.outlinks, [[Age of Forging]])
SORT file.name ASC
```

## Deities emerging
```dataview
LIST FROM "" WHERE type = "deity" AND contains(file.outlinks, [[Age of Forging]])
SORT file.name ASC
```

## Characters living in this era
```dataview
LIST FROM "" WHERE type = "character" AND contains(file.outlinks, [[Age of Forging]])
SORT file.name ASC
```
