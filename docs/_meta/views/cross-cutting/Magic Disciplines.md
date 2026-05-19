---
type: index
status: canon
tags:
- view
view: Magic Disciplines
---
# Magic Disciplines

*Magic schools and the entities that wield them.*

## All magic disciplines
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
```
