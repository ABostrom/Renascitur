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
WHERE type = "event" AND string(era) = "[[Age of Forging]]"
SORT year ASC
```

## Chronicles
```dataview
LIST FROM "" WHERE type = "chronicle" AND string(era_of_composition) = "[[Age of Forging]]"
SORT file.name ASC
```

## Myths from this era
```dataview
LIST FROM "" WHERE type = "myth" AND string(era) = "[[Age of Forging]]"
SORT file.name ASC
```

## Deities emerging
```dataview
LIST FROM "" WHERE type = "deity" AND string(era_of_emergence) = "[[Age of Forging]]"
SORT file.name ASC
```

## Characters living in this era
```dataview
LIST FROM "" WHERE type = "character" AND string(era) = "[[Age of Forging]]"
SORT file.name ASC
```
