---
type: index
status: canon
tags:
- view
view: Age of Night — Era Dashboard
---
# Age of Night — Era Dashboard

*Events, chronicles, myths, deities, and characters of the Age of Night.*

## Events in this era
```dataview
TABLE WITHOUT ID
  file.link AS "Event",
  year_display AS "When",
  location AS "Where",
  importance AS "Importance",
  status AS "Status"
FROM ""
WHERE type = "event" AND era = [[Age of Night]]
SORT year ASC
```

## Chronicles
```dataview
LIST FROM "" WHERE type = "chronicle" AND era_of_composition = [[Age of Night]]
SORT file.name ASC
```

## Myths from this era
```dataview
LIST FROM "" WHERE type = "myth" AND era = [[Age of Night]]
SORT file.name ASC
```

## Deities emerging
```dataview
LIST FROM "" WHERE type = "deity" AND era_of_emergence = [[Age of Night]]
SORT file.name ASC
```

## Characters living in this era
```dataview
LIST FROM "" WHERE type = "character" AND era = [[Age of Night]]
SORT file.name ASC
```
