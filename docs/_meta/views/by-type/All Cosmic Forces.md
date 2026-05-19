---
type: index
status: canon
tags:
- view
view: All Cosmic Forces
---
# All Cosmic Forces

*Abstract cosmic forces and eldritch entities.*

```dataview
TABLE WITHOUT ID
  file.link AS "Force",
  nature AS "Nature",
  opposed_by AS "Opposes",
  importance AS "Importance"
FROM ""
WHERE type = "cosmic-force"
SORT importance ASC, file.name ASC
```
