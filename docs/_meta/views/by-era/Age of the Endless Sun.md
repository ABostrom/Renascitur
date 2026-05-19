---
type: index
status: canon
tags:
- view
view: Age of the Endless Sun — Era Dashboard
---
# Age of the Endless Sun — Era Dashboard

*Events, chronicles, myths, deities, and characters of the Age of the Endless Sun.*

## Events in this era
```dataview
TABLE WITHOUT ID
  file.link AS "Event",
  year_display AS "When",
  location AS "Where",
  importance AS "Importance",
  status AS "Status"
FROM ""
WHERE type = "event" AND string(era) = "[[Age of the Endless Sun]]"
SORT year ASC
```

## Chronicles
```dataview
LIST FROM "" WHERE type = "chronicle" AND string(era_of_composition) = "[[Age of the Endless Sun]]"
SORT file.name ASC
```

## Myths from this era
```dataview
LIST FROM "" WHERE type = "myth" AND string(era) = "[[Age of the Endless Sun]]"
SORT file.name ASC
```

## Deities emerging
```dataview
LIST FROM "" WHERE type = "deity" AND string(era_of_emergence) = "[[Age of the Endless Sun]]"
SORT file.name ASC
```

## Characters living in this era
```dataview
LIST FROM "" WHERE type = "character" AND string(era) = "[[Age of the Endless Sun]]"
SORT file.name ASC
```
