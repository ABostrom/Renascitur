---
type: index
status: canon
tags:
- view
view: Firebrand Great Houses
---
# Firebrand Great Houses

*The 12 Great Houses of the Firebrand Empire.*

```dataview
TABLE WITHOUT ID
  file.link AS "House",
  current_head AS "Head",
  seat AS "Seat",
  sigil AS "Sigil",
  importance AS "Importance"
FROM ""
WHERE type = "house" OR kind = "house"
SORT file.name ASC
```
